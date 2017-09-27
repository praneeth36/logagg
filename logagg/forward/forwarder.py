import json
import time
import Queue
from threading import Thread

import nsq
import pymongo
from pymongo import MongoClient
from basescript import BaseScript

class LogForwarder(BaseScript):
    NAME = "LogForwarder"
    DESC = "Gets all the logs from nsq and stores in MongoDB"

    MAX_IN_FLIGHT = 100 # Number of messages to read from NSQ per shot
    QUEUE_MAX_SIZE = 2000
    SERVER_SELECTION_TIMEOUT = 500 # MongoDB server selection timeout

    SLEEP_TIME = 1
    QUEUE_TIMEOUT = 1
    MAX_SECONDS_TO_PUSH = 2
    MAX_MESSAGES_TO_PUSH = 100

    def run(self):

        # Establish connection to MongoDB to store the nsq messages
        url = 'mongodb://%s:%s@%s:%s' % (self.args.mongodb_user_name, self.args.mongodb_password,
                self.args.mongodb_server_url, self.args.mongodb_port)
        client = MongoClient(url, serverSelectionTimeoutMS=self.SERVER_SELECTION_TIMEOUT)
        self.mongo_database = client[self.args.mongodb_database]
        self.mongo_coll = self.mongo_database[self.args.mongodb_collection]

        # Initialize a queue to carry messages between the
        # producer (nsq_reader) and the consumer (read_from_q)
        self.msgqueue = Queue.Queue(maxsize=self.QUEUE_MAX_SIZE)

        # Establish connection to nsq from where we get the logs
        self.nsq_reader = nsq.Reader(
            topic=self.args.nsqtopic,
            channel=self.args.nsqchannel,
            nsqd_tcp_addresses=self.args.nsqd_tcp_address
        )
        self.nsq_reader.set_message_handler(self.handle_msg)
        self.nsq_reader.set_max_in_flight(self.MAX_IN_FLIGHT)

        th = self.consumer_thread = Thread(target=self.read_from_q)
        th.daemon = True
        th.start()

        nsq.run()

        th.join()
        self.nsq_reader.close()

    def handle_msg(self, msg):
        msg.enable_async()
        self.msgqueue.put(msg)

    def read_from_q(self):
        msgs = []
	last_push_ts = time.time()

        while True:
            try:
                msg = self.msgqueue.get(block=True, timeout=self.QUEUE_TIMEOUT)
                msgs.append(msg)

            except Queue.Empty:
                time.sleep(self.SLEEP_TIME)
                continue

            cur_ts = time.time()
            time_since_last_push = cur_ts - last_push_ts

            is_msg_limit_reached = len(msgs) >= self.MAX_MESSAGES_TO_PUSH
            is_max_time_elapsed = time_since_last_push >= self.MAX_SECONDS_TO_PUSH

            should_push = len(msgs) > 0 and (is_max_time_elapsed or is_msg_limit_reached)

            try:
                if should_push:
                    self._write_messages(msgs)
                    self._ack_messages(msgs)

                    msgs = []
                    last_push_ts = time.time()

            except (SystemExit, KeyboardInterrupt): raise
            except pymongo.errors.ServerSelectionTimeoutError:
                self.log.exception('Push to mongo and ack to nsq failed')

    def _ack_messages(self, msgs):
        for msg in msgs:
            try:
                msg.finish()
                self.log.info('msg ack finished')
            except (SystemExit, KeyboardInterrupt): raise
            except:
                self.log.exception('msg ack failed')

    def _write_messages(self, msgs):
        msgs_list = []
        #TODO: We need to do this by using iteration object.
        for msg in msgs:
            msg_body = json.loads(msg.body)
            msg_body['_id'] = msg_body.pop('id')
            msgs_list.append(msg_body)
        try:
            self.mongo_coll.insert_many([msg for msg in msgs_list], ordered=False)
            self.log.info("inserted the msgs into mongodb %d" % (len(msgs)))
        except pymongo.errors.BulkWriteError as bwe:
            self.log.exception('Write to mongo failed. Details: %s' % bwe.details)

    def define_args(self, parser):

        parser.add_argument('--nsqtopic', help='NSQ topic name to read messages from. Ex: logs_and_metrics')
        parser.add_argument('--nsqchannel', help='channel of nsqd')
        parser.add_argument('--nsqd-tcp-address', help='nsqd tcp address where we get the messages')

        parser.add_argument('--mongodb-server-url', help='DNS of the server where mongo is running')
        parser.add_argument('--mongodb-port', help='port where mongo is running')
        parser.add_argument('--mongodb-user-name', help='username of mongodb')
        parser.add_argument('--mongodb-password', help='password to authenticate mongodb')
        parser.add_argument('--mongodb-database', help='database to store logs')
        parser.add_argument('--mongodb-collection', help='collection to store logs')

def main():
    LogForwarder().start()

if __name__ == '__main__':
    main()

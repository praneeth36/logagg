from setuptools import setup, find_packages

setup(
    name="logagg",
    version="0.1",
    description="Collect all the logs from server and parses"
                "it to get common schema for all the logs and"
                "stores at common location `MongoDB`.",
    keywords="logagg",
    author="Deep Compute, LLC",
    author_email="contact@deepcompute.com",
    url="https://github.com/deep-compute/logagg",
    install_requires=[
        "basescript",
        "pymongo",
        "pynsq"
    ],
    package_dir={'logagg': 'logagg'},
    packages=find_packages('.'),
    include_package_data=True,
    classifiers=[
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [
            "logagg = logagg:main",
        ]
    }
)

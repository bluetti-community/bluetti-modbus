"""Setup for pypi package"""

import codecs
import os

from setuptools import find_packages, setup

here = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
    long_description = "\n" + fh.read()

VERSION = os.getenv("LIB_VERSION")
DESCRIPTION = "Bluetti Modbus"

# Setting up
setup(
    name="bluetti-modbus-lib",
    version=VERSION,
    author="Patrick762",
    author_email="<pip-bluetti-modbus-lib@hosting-rt.de>",
    description=DESCRIPTION,
    long_description_content_type="text/markdown",
    long_description=long_description,
    url="https://github.com/bluetti-community/bluetti-modbus-lib",
    packages=find_packages(),
    install_requires=[
        "async_timeout",
        "asyncio",
        "modbus_connection[pymodbus]",
        "logging",
    ],
    keywords=[],
    entry_points={
        "console_scripts": [
            "bluetti-modread = bluetti_modbus_lib.scripts.bluetti_modread:start",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
    ],
)

"""Package setup – installs the `copilot` command-line tool."""

from setuptools import setup, find_packages

setup(
    name="copilot",
    version="1.0.0",
    description="Copilot driver-assistance system simulation",
    packages=find_packages(),
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "copilot=copilot.__main__:main",
        ],
    },
)

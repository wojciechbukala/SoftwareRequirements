"""Package setup for the Copilot driver-assistance system."""

from setuptools import setup, find_packages

setup(
    name="copilot",
    version="1.0.0",
    description="Copilot autonomous driver-assistance simulation",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "copilot=copilot.cli:main",
        ],
    },
)

"""Setup configuration for FleetRouter."""

from setuptools import setup, find_packages

setup(
    name="fleetrouter",
    version="1.0.0",
    description="Daily route planning for courier companies.",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "fleetrouter=fleetrouter.cli:main",
        ],
    },
)

from setuptools import setup, find_packages

setup(
    name="fleetrouter",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "fleetrouter=fleetrouter.main:main",
        ],
    },
)

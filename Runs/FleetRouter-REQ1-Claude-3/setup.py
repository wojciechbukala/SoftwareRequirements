from setuptools import setup

setup(
    name='fleetrouter',
    version='1.0.0',
    py_modules=['fleetrouter'],
    entry_points={
        'console_scripts': [
            'fleetrouter=fleetrouter:main',
        ],
    },
    python_requires='>=3.8',
)

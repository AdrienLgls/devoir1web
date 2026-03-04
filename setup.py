from setuptools import setup, find_packages

setup(
    name="inf349",
    packages=find_packages(),
    install_requires=[
        "flask",
        "peewee",
    ],
    extras_require={
        "test": [
            "pytest",
            "pytest-flask",
        ],
    },
)

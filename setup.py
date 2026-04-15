from setuptools import setup, find_packages

setup(
    name="api8inf349",
    packages=find_packages(),
    install_requires=[
        "flask",
        "peewee",
        "psycopg2-binary",
        "redis",
        "rq",
    ],
)

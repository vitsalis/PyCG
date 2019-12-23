import os

from setuptools import setup, find_packages
from subprocess import call

def get_long_desc():
    with open("README.md", "r") as readme:
        desc = readme.read()

    return desc

def setup_package():
    setup(
        name='pycg',
        version='0.0.1',
        description='Call graphs for Python code',
        long_description=get_long_desc(),
        url='https://github.com/AUEB-BALab/pycg',
        license='Apache Software License',
        packages=find_packages(),
        install_requires=[],
        entry_points = {
            'console_scripts': [
                'pycg=pycg.__main__:main',
            ],
        },
    )

if __name__ == '__main__':
    setup_package()

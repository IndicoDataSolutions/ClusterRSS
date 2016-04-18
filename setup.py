"""
Run the following at the base of this project:
python setup.py develop
"""
from setuptools import setup, find_packages
import os

if __name__ == "__main__":
    setup(
        name = "indicluster",
        packages = find_packages(),
        install_requires = open(
            os.path.join(
                os.path.dirname(__file__), "requirements.txt"
            ), 'rb').readlines(),
        version = "0.1.0"
    )

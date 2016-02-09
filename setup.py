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
        install_requires = [
            "feedparser==5.1.3",
            "gevent==1.0.2",
            "IndicoIo==0.13.0",
            "newspaper==0.0.9.8",
            # "numpy==1.10.4",
            "requests==2.3.0",
            "scikit-learn==0.17",
            # "scipy==0.17.0",
            "SQLAlchemy==1.0.11",
            "tornado==4.3"
        ],
        version = "0.1.0"
    )

#!/usr/bin/env python

from setuptools import setup,find_packages

setup(
    name="curs",
    version="1.0",
    author="LY.Chen",
    author_email="leaout@163.com",
    description=("a trading algorithmic system"),
    license="GPLv3",
    url="www.fourtrader.com",
    packages=find_packages(),

     install_requires=[
            'pytdx',
    ],
    zip_safe=False
)
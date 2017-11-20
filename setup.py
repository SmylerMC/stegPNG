#!/usr/bin/env python3

from setuptools import setup

setup(
    name="stegpng",
    version="1.0.0b4",
    url="https://github.com/WHGhost/stegPNG",
    description='A python package to make png steganography easier',
    long_description="""A pure python package with the goal to make png steganography and
    analysis easier""",
    author='WHGhost',
    author_email='wghosth@gmail.com',
    license='GPL-3.0',
    classifiers=[
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python :: 3',
    ],
    keywords='png library steganography image analysis ',
    packages=["stegpng"],
    install_requires=['requests'],
    python_requires='>=3',
    package_data={},
    data_files=[],
)

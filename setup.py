#!/usr/bin/env python

from distutils.core import setup

version = '0.0.0'

setup(name='agdc-v2',
      version=version,
      packages=[
          'geophys2netcdf'
      ],
      package_data={
          'geophys2netcdf': ['uuid.csv']
      },
      scripts=[
      ],
      requires=[
          'gdal',
          'numexpr',
          'numpy',
          'h5py',
          'netcdf4',
          'scipy',
          'pytz',
      ],
      url='https://github.com/alex-ip/geophys2netcdf',
      author='Alex Ip - Geoscience Australia',
      maintainer='Alex Ip - Geoscience Australia',
      maintainer_email='alex.ip@ga.gov.au',
      description='Geophysics Data NetCDF Converter',
      long_description='Geophysics Data NetCDF Converter',
      license='Apache License 2.0'
      )

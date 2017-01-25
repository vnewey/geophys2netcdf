#!/usr/bin/env python

from distutils.core import setup

version = '0.0.0'

setup(name='geophys2netcdf',
      version=version,
      packages=[
          'geophys2netcdf',
          'geophys2netcdf.metadata',
          'geophys2netcdf.thredds_catalog',
      ],
      package_data={
          'geophys2netcdf': ['uuid.csv']
      },
      scripts=[
      ],
      requires=[
          'cfunits',
          'collections',
          'datetime',
          'dateutil',
          'errno',
          'gc',
          'glob',
          'itertools',
          'jinja2',
          'json',
          'logging',
          'lxml',
          'math',
          'netCDF4',
          'numpy',
          'os',
          'osgeo',
          'owslib',
          'pickle',
          'pytz',
          're',
          'scipy',
          'shapely',
          'shutil',
          'subprocess',
          'sys',
          'tempfile',
          'unicodedata',
          'urllib',
          'xml',
          'yaml',
      ],
      url='https://github.com/alex-ip/geophys2netcdf',
      author='Alex Ip - Geoscience Australia',
      maintainer='Alex Ip - Geoscience Australia',
      maintainer_email='alex.ip@ga.gov.au',
      description='Geophysics Data NetCDF Converter',
      long_description='Geophysics Data NetCDF Converter',
      license='Apache License 2.0'
      )

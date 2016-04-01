#!/bin/bash

module load python
module load gdal/1.11.1-python
module load hdf5
module load netcdf

export PATH=~/bin:$PATH
export PYTHONPATH=~/lib/python2.7/site-packages:$PYTHONPATH:..

python -m geophys2netcdf $*

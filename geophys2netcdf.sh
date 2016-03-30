#!/bin/bash

module load python
module load gdal/1.11.1-python
module load hdf5
module load netcdf

export PATH=/home/547/iib547/bin:$PATH
export PYTHONPATH=/home/547/iib547/lib/python2.7/site-packages:$PYTHONPATH:~/geophys2netcdf

python -m geophys2netcdf $*

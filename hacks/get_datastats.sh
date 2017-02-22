#!/bin/bash

module load python/2.7.3
module load gdal/1.11.1-python
module load hdf5/1.8.10
module load geos/3.4.2
module load shapely/1.5.13
module load netcdf/4.3.3.1p

python get_datastats.py $1 $2 $3 $4

#!/bin/bash
script_dir=$(readlink -f ${0%/*})
for nc in $(find /g/data1/rr2/National_Coverages/ -name "*.nc" | sort)
do
  echo Updating NetCDF Metadata for file $nc
  $script_dir/geophys2netcdf.sh $nc
done

#!/bin/bash
script_dir=$(readlink -f ${0%/*})
for zip in $(find /g/data1/rr2/National_Coverages/ -name "*.zip" | sort)
do
  echo Translating file $zip to NetCDF
  $script_dir/geophys2netcdf.sh $zip
done

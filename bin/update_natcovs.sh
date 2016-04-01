#!/bin/bash
for nc in $(find /g/data1/rr2/National_Coverages/ -name "*.nc")
do
  echo Updating NetCDF Metadata for file $nc
  ./geophys2netcdf.sh $nc
done

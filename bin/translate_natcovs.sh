#!/bin/bash
for zip in $(find /g/data1/rr2/National_Coverages/ -name "*.zip")
do
  echo Translating file $zip to NetCDF
  ./geophys2netcdf.sh $zip
done

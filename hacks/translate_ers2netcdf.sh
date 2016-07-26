#!/bin/bash
module load netcdf
module load gdal/1.10.1

mkdir temp

for ers in $(ls *.ers)
do
  basename=$(echo $ers | sed s/.ers$//g)
  tmp=temp/$(echo $ers | sed s/.ers$/.tmp/g)
  nc=$(echo $ers | sed s/.ers$/.nc/g)

  gdal_translate -of netCDF -co FORMAT=NC4C -co COMPRESS=DEFLATE -co WRITE_BOTTOMUP=YES $ers $tmp

  # Re-chunking may fail if dataset is smaller than chunk size
  nccopy -u -d 2 -c lat/128,lon/128 $tmp $nc
  if [ $? != 0 ]
  then
    mv $tmp $nc
  fi

  rm $tmp
  echo Finished translating $ers to $nc.

  zip $(for ext in .zip '' .ers .isi; do echo $basename$ext; done)
  echo Finished zipping $(for ext in '' .ers .isi; do echo $basename$ext; done) to $basename.zip

  mv $(for ext in '' .ers .isi; do echo $basename$ext; done) temp
  echo Finished moving $(for ext in '' .ers .isi; do echo $basename$ext; done) to temp directory

  mkdir $basename
  mv $(for ext in .nc .zip ''; do echo $basename$ext; done)
  echo Finished moving $(for ext in .nc .zip; do echo $basename$ext; done) to $basename directory
done

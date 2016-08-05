#!/bin/bash
# A quick and dirty script to find all unique dataset names in a specified directory

dir=$1

for extension in nc ers zip .DIR
do
  find ${dir} -name \*.${extension} | grep -v -e /temp -e shore_seismic/ -e /thredds/ | sed s/\\.\\+[[:alnum:]]\\+$//g
done | sort -u

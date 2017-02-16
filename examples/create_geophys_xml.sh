#!/bin/bash

# Script to create XML metadata records for ALL geophysics survey datasets

# Gridded survey data root directory
grid_root_dir=/g/data2/uc0/rr2_dev/rcb547/AWAGS_Levelled_Grids

# XML output directory
xml_dir=~/temp

rm ${xml_dir}/*.xml

for nc in $(find ${grid_root_dir}/mag_survey_grids_levelled -name '*.nc' | sort); do python ../utils/create_xml_metadata.py ../templates/mag_grid_metadata_text.json survey_metadata_template.xml $nc ${xml_dir}; done | tee create_xml_metadata_mag.log
for nc in $(find ${grid_root_dir}/rad_survey_grids_levelled/potassium/ -name '*.nc' | sort); do python ../utils/create_xml_metadata.py ../templates/rad_k_grid_metadata_text.json survey_metadata_template.xml $nc ${xml_dir}; done | tee create_xml_metadata_rad_k.log
for nc in $(find ${grid_root_dir}/rad_survey_grids_levelled/thorium/ -name '*.nc' | sort); do python ../utils/create_xml_metadata.py ../templates/rad_th_grid_metadata_text.json survey_metadata_template.xml $nc ${xml_dir}; done | tee create_xml_metadata_rad_th.log
for nc in $(find ${grid_root_dir}/rad_survey_grids_levelled/uranium/ -name '*.nc' | sort); do python ../utils/create_xml_metadata.py ../templates/rad_u_grid_metadata_text.json survey_metadata_template.xml $nc ${xml_dir}; done | tee create_xml_metadata_rad_u.log

# Check for failed XML creation (netCDF files with no corresponding XML file)
for nc in $(find ${grid_root_dir} -name '*.nc' | sort); do if [ ! -f ${xml_dir}/$(basename $nc | sed s/\.nc/\.xml/g) ]; then echo $nc $(ncdump -h $nc | grep survey_id | cut -d\" -f2); fi; done | sort | tee failed_xml_creation.txt

# Retry failed XML creation
for nc in $(grep '/mag_survey_grids_levelled' failed_xml_creation.txt | cut -d' ' -f1 | sort); do python ../utils/create_xml_metadata.py ../templates/mag_grid_metadata_text.json survey_metadata_template.xml $nc ${xml_dir}; done >>create_xml_metadata_mag.log
for nc in $(grep '/rad_survey_grids_levelled/potassium/' failed_xml_creation.txt | cut -d' ' -f1 | sort);  do python ../utils/create_xml_metadata.py ../templates/rad_k_grid_metadata_text.json survey_metadata_template.xml $nc ${xml_dir}; done >>create_xml_metadata_rad_k.log
for nc in $(grep '/rad_survey_grids_levelled/thorium/' failed_xml_creation.txt | cut -d' ' -f1 | sort);  do python ../utils/create_xml_metadata.py ../templates/rad_th_grid_metadata_text.json survey_metadata_template.xml $nc ${xml_dir}; done >>create_xml_metadata_rad_th.log
for nc in $(grep '/rad_survey_grids_levelled/uranium/' failed_xml_creation.txt | cut -d' ' -f1 | sort);  do python ../utils/create_xml_metadata.py ../templates/rad_u_grid_metadata_text.json survey_metadata_template.xml $nc ${xml_dir}; done >>create_xml_metadata_rad_u.log

# Check for failed XML creation (netCDF files with no corresponding XML file)
for nc in $(find ${grid_root_dir} -name '*.nc' | sort); do if [ ! -f ${xml_dir}/$(basename $nc | sed s/\.nc/\.xml/g) ]; then echo $nc $(ncdump -h $nc | grep survey_id | cut -d\" -f2); fi; done | sort | tee failed_xml_creation.txt

pushd ${xml_dir}
zip geophysics_survey_grid_metadata.zip *.xml
popd

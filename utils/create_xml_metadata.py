'''
Created on Apr 7, 2016

@author: Alex Ip, Geoscience Australia
'''
import sys
import netCDF4
import subprocess
import re
from pprint import pprint
from geophys2netcdf.metadata import Metadata, JetCatMetadata, SurveyMetadata


def main():
    assert len(
        sys.argv) == 4, 'Usage: %s <jetcat_path> <netcdf_path> <uuid>' % sys.argv[0]
    jetcat_path = sys.argv[1]
    netcdf_path = sys.argv[2]
    uuid = sys.argv[3]

    metadata = Metadata()
    
    jetcat_metadata = JetCatMetadata(netcdf_path, jetcat_path=jetcat_path)
    metadata.merge_root_metadata_from_object(jetcat_metadata)
    
    survey_metadata = SurveyMetadata(netcdf_path)
    metadata.merge_root_metadata_from_object(survey_metadata)
    
    pprint(metadata.metadata_dict)
    
    

if __name__ == '__main__':
    main()

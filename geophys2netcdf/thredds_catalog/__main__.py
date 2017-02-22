'''
Created on 22Feb.,2017

@author: u76345

'''
import sys
import os
import re
from pprint import pprint
from geophys2netcdf.thredds_catalog import THREDDSCatalog

def main():
    assert len(sys.argv) == 2, 'Usage: %s <thredds_catalog_url>|<yaml_file_path>' % sys.argv[0]
    
    if os.path.isfile(sys.argv[1]):
        yaml_file_path = sys.argv[1]
        tc = THREDDSCatalog(yaml_path=yaml_file_path)
    else: 
        thredds_catalog_url = sys.argv[1]
    
        yaml_file_path = os.path.abspath(
            re.sub(
                '\W',
                '_',
                os.path.splitext(
                    re.sub(
                        '^http://dap.*\.nci\.org\.au/thredds/',
                        '',
                        thredds_catalog_url))[0]) +
            '.yaml')
        # print 'yaml_path = %s' % yaml_path
    
        tc = THREDDSCatalog(thredds_catalog_url=thredds_catalog_url)
        tc.dump(yaml_file_path)
        
    pprint(tc.thredds_catalog_dict)

if __name__ == '__main__':
    main()
'''
Created on 22Feb.,2017

@author: u76345

'''
import sys
import os
import re
#from pprint import pprint
from geophys2netcdf.thredds_catalog import THREDDSCatalog

def main():
    assert len(sys.argv) == 2, 'Usage: %s <thredds_catalog_url>|<yaml_file_path>' % sys.argv[0]
    
    if os.path.isfile(sys.argv[1]):
        yaml_file_path = sys.argv[1]
        tc = THREDDSCatalog(yaml_path=yaml_file_path)
    else: 
        thredds_catalog_urls = sys.argv[1]
    
        yaml_file_path = os.path.abspath(
            os.path.splitext(
            re.sub(
                '\W',
                '_',
                
                    re.sub(
                        '^http://dap.*\.nci\.org\.au/thredds/',
                        '',
                        thredds_catalog_urls)))[0] +
            '.yaml')
        # print 'yaml_file_path = %s' % yaml_file_path
    
        tc = THREDDSCatalog(thredds_catalog_urls=thredds_catalog_urls, verbose=True)
        tc.dump(yaml_file_path)
        
    print(tc.indented_text())
    
    #pprint(tc.find_url_list('/g/data1/rr2/National_Coverages/IR_gravity_anomaly_Australia_V1/IR_gravity_anomaly_Australia_V1.nc'))    
    #pprint(tc.find_url_dict('/g/data1/rr2/National_Coverages/IR_gravity_anomaly_Australia_V1/IR_gravity_anomaly_Australia_V1.nc'))

if __name__ == '__main__':
    main()
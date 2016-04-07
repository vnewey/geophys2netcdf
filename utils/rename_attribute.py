'''
Created on Apr 7, 2016

@author: Alex Ip, Geoscience Australia
'''
import sys
import netCDF4
import subprocess
import re
from geophys2netcdf import ERS2NetCDF


def main():
    assert len(sys.argv) == 5, 'Usage: %s <root_dir> <file_template> <old_attribute_name> <new_attribute_name>' % sys.argv[0]
    root_dir = sys.argv[1]
    file_template = sys.argv[2]
    old_attribute_name = sys.argv[3]
    new_attribute_name = sys.argv[4]
    
    nc_path_list = [filename for filename in subprocess.check_output(['find', root_dir, '-name', file_template]).split('\n') if re.search('\.nc$', filename)]
    
    for nc_path in nc_path_list:
        print 'Setting units in %s' % nc_path
        
        nc_dataset = netCDF4.Dataset(nc_path, 'r+')
       
        try:
            # Rename attribute
            value = getattr(nc_dataset, old_attribute_name)
            setattr(nc_dataset, new_attribute_name, value)
            delattr(nc_dataset, old_attribute_name)
            print '%s.%s renamed to %s. (Value = %s)' % (nc_path, old_attribute_name, new_attribute_name, value)
        except Exception, e:
            print 'Unable to rename attribute %s to %s: %s' % (old_attribute_name, new_attribute_name, e.message)
    
        nc_dataset.close()
        
    
        g2n_object = ERS2NetCDF()
        g2n_object.update_nc_metadata(nc_path)
        g2n_object.check_json_metadata(nc_path) # Kind of redundant, but possibly useful for debugging


if __name__ == '__main__':
    main()
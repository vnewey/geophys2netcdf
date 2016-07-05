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
    assert len(sys.argv) == 4, 'Usage: %s <root_dir> <file_template> <attribute_name>' % sys.argv[0]
    root_dir = sys.argv[1]
    file_template = sys.argv[2]
    attribute_name = sys.argv[3]
    
    nc_path_list = [filename for filename in subprocess.check_output(['find', root_dir, '-name', file_template]).split('\n') if re.search('\.nc$', filename)]
    
    for nc_path in nc_path_list:
        print 'Deleting attribute in %s' % nc_path
        
        nc_dataset = netCDF4.Dataset(nc_path, 'r+')
       
        try:
            # Rename attribute
            delattr(nc_dataset, attribute_name)
            print '%s.%s deleted' % (nc_path, attribute_name)
        except Exception, e:
            print 'Unable to delete attribute %s: %s' % (attribute_name, e.message)
    
        # Retrospective fixup
        nc_dataset.Conventions = nc_dataset.Conventions.replace('CF-1.5', 'CF-1.6').replace(', ', ',')

        nc_dataset.close()
        
    
        g2n_object = ERS2NetCDF()
        g2n_object.update_nc_metadata(nc_path)
        g2n_object.check_json_metadata(nc_path) # Kind of redundant, but possibly useful for debugging


if __name__ == '__main__':
    main()
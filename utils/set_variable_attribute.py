'''
Created on Apr 6, 2016

@author: Alex Ip, Geoscience Australia
'''
import sys
import netCDF4
import subprocess
import re
from geophys2netcdf import ERS2NetCDF


def main():
    assert len(sys.argv) == 5, 'Usage: %s <root_dir> <file_template> <attribute_name> <attribute_value>' % sys.argv[0]
    root_dir = sys.argv[1]
    file_template = sys.argv[2]
    attribute_name = sys.argv[3]
    attribute_value = sys.argv[4]

    nc_path_list = [filename for filename in subprocess.check_output(['find', root_dir, '-name', file_template]).split('\n') if re.search('\.nc$', filename)]
    
    for nc_path in nc_path_list:
        print 'Setting units in %s' % nc_path
        
        nc_dataset = netCDF4.Dataset(nc_path, 'r+')
    
        # Find variable name
        variable_name = [key for key in nc_dataset.variables.keys() if key not in ['crs', 'lat', 'lon']][0]
    
        variable = nc_dataset.variables[variable_name]

        try:
            print 'Original %s.%s = %s' % (variable_name, attribute_name, getattr(variable, attribute_name))
        except:
            print 'Original %s.%s not set' % (variable_name, attribute_name)

        setattr(variable, attribute_name, attribute_value)
    
        # Retrospective fixup
        nc_dataset.Conventions = nc_dataset.Conventions.replace('CF-1.5', 'CF-1.6').replace(', ', ',')
    
        print 'Final %s.%s = %s' % (variable_name, attribute_name, getattr(variable, attribute_name))
    
        nc_dataset.close()
        
        g2n_object = ERS2NetCDF()
        g2n_object.update_nc_metadata(nc_path)
        g2n_object.check_json_metadata(nc_path) # Kind of redundant, but possibly useful for debugging


if __name__ == '__main__':
    main()
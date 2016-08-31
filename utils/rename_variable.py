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
    assert len(sys.argv) in [4,5], 'Usage: %s <root_dir> <file_template> <new_variable_name> [<long_variable_name>]' % sys.argv[0]
    root_dir = sys.argv[1]
    file_template = sys.argv[2]
    new_variable_name = re.sub('\W', '_', sys.argv[3]) # Sanitise new name
    
    if len(sys.argv) == 5:
        long_variable_name = sys.argv[4]
    else:
        long_variable_name = None
    
    nc_path_list = [filename for filename in subprocess.check_output(['find', root_dir, '-name', file_template]).split('\n') if re.search('\.nc$', filename)]
    
    for nc_path in nc_path_list:
        print 'Renaming variable in %s' % nc_path
        
        nc_dataset = netCDF4.Dataset(nc_path, 'r+')
    
        # Find variable name
        old_variable_name = [key for key in nc_dataset.variables.keys() if len(nc_dataset.variables[key].dimensions) == 2][0]
    
        if new_variable_name != old_variable_name:
            nc_dataset.renameVariable(old_variable_name, new_variable_name)
            print '%s.variables["%s"] renamed to %s' % (nc_path, old_variable_name, new_variable_name)
        
        variable = nc_dataset.variables[new_variable_name]

        if long_variable_name and (variable.long_name != long_variable_name):
            variable.long_name = long_variable_name
            print '%s.variables["%s"].long_name changed to %s' % (nc_path, new_variable_name, long_variable_name)

        # Retrospective fixupZZ
        nc_dataset.Conventions = nc_dataset.Conventions.replace('CF-1.5', 'CF-1.6').replace(', ', ',')
    
        nc_dataset.close()
        
    
        g2n_object = ERS2NetCDF()
        g2n_object.update_nc_metadata(nc_path)
        g2n_object.check_json_metadata(nc_path) # Kind of redundant, but possibly useful for debugging


if __name__ == '__main__':
    main()

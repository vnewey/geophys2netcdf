'''
Created on Apr 6, 2016

@author: Alex Ip, Geoscience Australia
'''
import sys
import netCDF4
import subprocess
import re
from cfunits import Units
from geophys2netcdf import ERS2NetCDF


def main():
    assert len(sys.argv) == 4, 'Usage: %s <root_dir> <file_template> <units>' % sys.argv[0]
    root_dir = sys.argv[1]
    file_template = sys.argv[2]
    units = Units(sys.argv[3]).units # This will fail for invalid units
    
    nc_path_list = [filename for filename in subprocess.check_output(['find', root_dir, '-name', file_template]).split('\n') if re.search('\.nc$', filename)]
    
    for nc_path in nc_path_list:
        print 'Setting units in %s' % nc_path
        
        nc_dataset = netCDF4.Dataset(nc_path, 'r+')
    
        # Find variable with "grid_mapping" attribute - assumed to be 2D data variable
        try:
            variable = [variable for variable in nc_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
        except:
            raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')

        variable.units = units
    
        # Retrospective fixup
        nc_dataset.Conventions = nc_dataset.Conventions.replace('CF-1.5', 'CF-1.6').replace(', ', ',')
    
        nc_dataset.close()
        
        print '%s.variables["%s"].units = %s' % (nc_path, variable.name, units)
    
        g2n_object = ERS2NetCDF()
        g2n_object.update_nc_metadata(nc_path)
        g2n_object.check_json_metadata(nc_path) # Kind of redundant, but possibly useful for debugging


if __name__ == '__main__':
    main()
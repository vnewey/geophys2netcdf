'''
Utility to updated ACDD global attributes in NetCDF file using metadata sourced from GeoNetwork
Created on Apr 7, 2016

@author: Alex Ip, Geoscience Australia
'''
import sys
import subprocess
import re
from geophys2netcdf import ERS2NetCDF


def main():
    assert len(sys.argv) == 3, 'Usage: %s <root_dir> <file_template>' % sys.argv[0]
    root_dir = sys.argv[1]
    file_template = sys.argv[2]
    
    nc_path_list = [filename for filename in subprocess.check_output(['find', root_dir, '-name', file_template]).split('\n') if re.search('\.nc$', filename)]
    
    for nc_path in nc_path_list:
        print 'Updating metadata in %s' % nc_path
        try:
            g2n_object = ERS2NetCDF()
            g2n_object.update_nc_metadata(nc_path, do_stats=True)
            g2n_object.check_json_metadata() # Kind of redundant, but possibly useful for debugging
        except Exception, e:
            print 'Metadata update failed: %s' % e.message

if __name__ == '__main__':
    main()

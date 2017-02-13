'''
Utility to updated ACDD global attributes in NetCDF file using metadata sourced from GeoNetwork
Created on Apr 7, 2016

@author: Alex Ip, Geoscience Australia
'''
import sys
import subprocess
import re
import os
import netCDF4
from geophys2netcdf import ERS2NetCDF


def main():
    assert len(
        sys.argv) >= 3 and len(sys.argv) <= 4, 'Usage: %s <root_dir> <file_template> [<xml_dir>]' % sys.argv[0]
    root_dir = sys.argv[1]
    file_template = sys.argv[2]
    if len(sys.argv) == 4:
        xml_dir = sys.argv[3]
    else:
        xml_dir = None

    nc_path_list = sorted([filename for filename in subprocess.check_output(
        ['find', root_dir, '-name', file_template]).split('\n') if re.search('\.nc$', filename)])

    for nc_path in nc_path_list:
        print 'Updating metadata in %s' % nc_path
        
        if xml_dir:
            xml_path = os.path.abspath(os.path.join(xml_dir, os.path.splitext(os.path.basename(nc_path))[0] + '.xml'))
        else:
            xml_path = None

        try:
            g2n_object = ERS2NetCDF()
            g2n_object.update_nc_metadata(nc_path, do_stats=True, xml_path=xml_path)

            # Kind of redundant, but possibly useful for debugging
            g2n_object.check_json_metadata()
        except Exception as e:
            print 'Metadata update failed: %s' % e.message

if __name__ == '__main__':
    main()

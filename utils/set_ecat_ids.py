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
    assert len(
        sys.argv) == 4, 'Usage: %s <root_dir> <file_template> <start_id>' % sys.argv[0]
    root_dir = sys.argv[1]
    file_template = sys.argv[2]
    start_id = int(sys.argv[3])  # This will fail for invalid integers

    nc_path_list = sorted([filename for filename in subprocess.check_output(
        ['find', root_dir, '-name', file_template]).split('\n') if re.search('\.nc$', filename)])

    ecat_id = start_id
    for nc_path in nc_path_list:
        print 'Setting eCat ID in %s' % nc_path

        nc_dataset = netCDF4.Dataset(nc_path, 'r+')
        
        try:
            existing_id = int(nc_dataset.ecat_id)
            print '%s already has existing eCat ID %d' % (nc_path, existing_id)
        except Exception as e:
            nc_dataset.ecat_id = ecat_id
            print '%s now has eCat ID set to %d' % (nc_path, ecat_id)
            ecat_id += 1

        nc_dataset.close()

#        print 'Updating metadata in %s' % nc_path
#        try:
#            g2n_object = ERS2NetCDF()
#            g2n_object.update_nc_metadata(nc_path, do_stats=True)
#            # Kind of redundant, but possibly useful for debugging
#            g2n_object.check_json_metadata()
#        except Exception as e:
#            print 'Metadata update failed: %s' % e.message


if __name__ == '__main__':
    main()

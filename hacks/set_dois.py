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
    assert len(
        sys.argv) == 4, 'Usage: %s <root_dir> <file_template> <ecat_id_doi_csv_path>' % sys.argv[0]
    root_dir = sys.argv[1]
    file_template = sys.argv[2]
    ecat_id_doi_csv_path = sys.argv[3]

    ecat_id_doi_csv_file = open(ecat_id_doi_csv_path)
    ecat_id_doi_dict = dict([[value.strip() for value in line.split(',')] for line in ecat_id_doi_csv_file])
    ecat_id_doi_csv_file.close()

    print ecat_id_doi_dict

    nc_path_list = [filename for filename in subprocess.check_output(
        ['find', root_dir, '-name', file_template]).split('\n') if re.search('\.nc$', filename)]

    for nc_path in nc_path_list:
        print 'Setting attribute in %s' % nc_path

        nc_dataset = netCDF4.Dataset(nc_path, 'r+')

        try:
            # Set DOI
            nc_dataset.doi = 'http://dx.doi.org/' + ecat_id_doi_dict[str(nc_dataset.ecat_id)]
            print '%s.doi set to %s' % (nc_path, nc_dataset.doi)
        except Exception as e:
            print 'Unable to set %s.doi to %s: %s' % (nc_path, nc_dataset.doi, e.message)

        nc_dataset.close()

        print 'Updating metadata in %s' % nc_path
        try:
            g2n_object = ERS2NetCDF()
            g2n_object.update_nc_metadata(nc_path, do_stats=True)
            # Kind of redundant, but possibly useful for debugging
            g2n_object.check_json_metadata()
        except Exception as e:
            print 'Metadata update failed: %s' % e.message


if __name__ == '__main__':
    main()

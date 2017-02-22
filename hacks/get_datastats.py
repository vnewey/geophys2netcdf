'''
Created on Feb 22, 2017

@author: Alex Ip, Geoscience Australia
'''
import sys
import subprocess
import re
from geophys_utils import DataStats


def main():
    assert len(sys.argv) == 4 or len(sys.argv) == 5, 'Usage: %s <root_dir> <file_template> <data_stats_csv_path> [<max_bytes>]' % sys.argv[0]
    root_dir = sys.argv[1]
    file_template = sys.argv[2]
    data_stats_csv_path = sys.argv[3]
    max_bytes = int(sys.argv[4]) if len(sys.argv) == 5 else None

    nc_path_list = [filename for filename in subprocess.check_output(
        ['find', root_dir, '-name', file_template]).split('\n') if re.search('\.nc$', filename)]

    data_stats_csv_file = open(data_stats_csv_path, 'w')
    
    data_stats_csv_file.write(','.join(DataStats.key_list) + '\n')
    for nc_path in nc_path_list:
        print 'Computing datastats for %s' % nc_path

        try:
            data_stats = DataStats(netcdf_path=nc_path, max_bytes=max_bytes)
            data_stats_csv_file.write(','.join([str(data_stats.value(key)) for key in DataStats.key_list]) + '\n')
        except Exception as e:
            print 'Unable to compute datastats for %s: %s' % (nc_path, e.message)

    data_stats_csv_file.close()



if __name__ == '__main__':
    main()

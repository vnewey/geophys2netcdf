import sys
import os
import re
from geophys2netcdf import ERS2NetCDF

assert len(sys.argv) == 2, 'Usage: %s <CSV_path>' % sys.argv[0]
csv_path = sys.argv[1]

def update_nc_metadata(nc_path, uuid):
    e2n = ERS2NetCDF()
    e2n._output_path = nc_path
    e2n._uuid = uuid

    e2n.update_nc_metadata(nc_path)

csv_file = open(csv_path, 'r')
field_name_list = csv_file.readline().strip().split(',')

print 'field_name_list = %s' % field_name_list

for field_list in [line.strip().split(',') for line in csv_file]:
    nc_path = re.sub('^"(.*)"$', lambda x: x.group(1), field_list[0]) + '.nc'
    uuid = re.sub('^"(.*)"$', lambda x: x.group(1), field_list[1])

    print 'Checking %s %s' % (nc_path, uuid)

    if (os.path.isfile(nc_path) and uuid
        #and re.search('^/g/data1/rr2/gravity/', nc_path) # Include all datasets in /g/data1/rr2/gravity/
        #and (not re.search('^/g/data1/rr2/gravity/National', nc_path)) # Exclude all datasets in /g/data1/rr2/gravity/National
        and (os.path.splitext(os.path.basename(nc_path))[0] == os.path.basename(os.path.dirname(nc_path))) # Only work with datasets in their own directory
        ):
        print 'Setting metadata in file %s' % nc_path
        #try:
        if True:
            update_nc_metadata(nc_path, uuid)
        #except Exception, e:
        else:
            print '%s failed: %s' % (nc_path, e.message)

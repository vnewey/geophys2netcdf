'''
Created on 15Aug.,2016

@author: Alex
'''
import sys
import gc
import netCDF4
import numpy as np

class DataStats(object):
    '''
    classdocs
    '''
    key_list = ['nc_path', 'nodata_value', 'min', 'max', 'mean', 'median', 'percentile_1', 'percentile_99']

    def __init__(self, netcdf_path):
        '''
        Constructor
        '''
        netcdf_dataset = netCDF4.Dataset(netcdf_path)
        
        # Find variable with "grid_mapping" attribute - assumed to be 2D data variable
        try:
            data_variable = [variable for variable in netcdf_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
        except:
            raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')
        
        self._data_stats = {}        
        self._data_stats['nc_path'] = netcdf_path
        self._data_stats['nodata_value'] = data_variable._FillValue        

        data_array = variable[:].data # This will fail for larger than memory arrays
        data_array = data_array[data_array != self._data_stats['nodata_value']] # Discard all no-data elements
        netcdf_dataset.close()
        del netcdf_dataset
        gc.collect()

        self._data_stats['min'] = np.nanmin(data_array)
        self._data_stats['max'] = np.nanmax(data_array)
        self._data_stats['mean'] = np.nanmean(data_array)
        self._data_stats['median'] = np.nanpercentile(data_array, 50)
        self._data_stats['percentile_1'] = np.nanpercentile(data_array, 1)
        self._data_stats['percentile_99'] = np.nanpercentile(data_array, 99)
        
        del data_array
        gc.collect()
        
    def value(self, key):
        return self._data_stats[key]
        
def main():
    print ','.join(DataStats.key_list)
    for netcdf_path in sys.argv[1:]:
        try:
            datastats = DataStats(netcdf_path)
            print ','.join([str(datastats.value(key)) for key in DataStats.key_list])
        except:
            pass

if __name__ == '__main__':
    main()

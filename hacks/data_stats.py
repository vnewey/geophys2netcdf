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
    key_list = ['nodata_value', 'min', 'max', 'mean', 'median', 'percentile_1', 'percentile_99']

    def __init__(self, netcdf_path):
        '''
        Constructor
        '''
        self._netcdf_path = netcdf_path
        netcdf_dataset = netCDF4.Dataset(self._netcdf_path)
        
        # Find variable with "grid_mapping" attribute - assumed to be 2D data variable
        try:
            data_variable = [variable for variable in netcdf_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
        except:
            raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')
        
        data_array = variable[:].flatten()
        
        self._data_stats = {}        
        self._data_stats['nodata_value'] = data_variable._FillValue        
        self._data_stats['min'] = np.nanmin(data_array)
        self._data_stats['max'] = np.nanmax(data_array)
        self._data_stats['mean'] = np.nanmean(data_array)
        self._data_stats['median'] = np.nanmedian(data_array)
        self._data_stats['percentile_1'] = np.nanpercentile(data_array, 1)
        self._data_stats['percentile_99'] = np.nanpercentile(data_array, 99)
        
        del data_array
        netcdf_dataset.close()
        del netcdf_dataset
        gc.collect()
        
    @property 
    def value(self, key):
        return self._data_stats[key]
        
def main():
    print ','.join(DataStats.key_list)
    for netcdf_path in sys.argv[1:]:
        datastats = DataStats(netcdf_path)
        print ','.join([str(datastats.value[key]) for key in DataStats.key_list])
        
    
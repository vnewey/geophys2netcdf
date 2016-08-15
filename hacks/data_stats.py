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
    CHUNK_MULTIPLE = 4 # How many chunks to grab at a time

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

        try:
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
        except:
            shape = data_variable.shape()
            chunking = [DataStats.CHUNK_MULTIPLE * chunk_size for chunk_size in data_variable.chunking()]
            start_indices = [0,0]
            end_indices = [0,0]
            chunk_counts = [(shape[0] + chunking[0] - 1) / chunking[0], (shape[1] + chunking[1] - 1) / chunking[1]]
            chunk_length = np.zeros(chunk_counts, dtype=np.int16)
            
            length_read = 0
            weighted_mean = 0.0
            for _dimension0_index in range(chunk_counts[0]):
                end_indices[0] = min(start_indices[0] + chunking[0], shape[0])
                start_indices[1] = 0
                for _dimension1_index in range(chunk_counts[1]):
                    end_indices[1] = min(start_indices[1] + chunking[1], shape[1])
                    chunk_array = variable[start_indices[0]:end_indices[0], start_indices[1]:end_indices[1]].data
                    chunk_length = len(chunk_array)
                    chunk_array = chunk_array[chunk_array != self._data_stats['nodata_value']] # Discard all no-data elements
                    
                    self._data_stats['min'] = min(self._data_stats['min'], np.nanmin(chunk_array))
                    self._data_stats['max'] = max(self._data_stats['max'], np.nanmax(chunk_array))
                    weighted_mean = weighted_mean + np.nanmean(data_array) * chunk_length
                    length_read += chunk_length
                    
                    start_indices[1] = end_indices[1]
                start_indices[0] = end_indices[0]
            
            self._data_stats['mean'] = weighted_mean / length_read
            
            #TODO: Implement something clever for these
            self._data_stats['median'] = np.NaN
            self._data_stats['percentile_1'] = np.NaN
            self._data_stats['percentile_99'] = np.NaN
                    
                
        
        del data_array
        gc.collect()
        
    def value(self, key):
        return self._data_stats[key]
        
def main():
    print ','.join(DataStats.key_list)
    for netcdf_path in sys.argv[1:]:
        datastats = DataStats(netcdf_path)
        print ','.join([str(datastats.value(key)) for key in DataStats.key_list])

if __name__ == '__main__':
    main()

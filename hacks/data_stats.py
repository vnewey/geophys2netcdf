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
    CHUNK_MULTIPLE = 32 # How many chunks to grab at a time

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
#            raise Exception('Testing only')
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
        except Exception, e:
            shape = data_variable.shape
#            print 'Whole-array read failed (%s) for array size %s' % (e.message, shape)

            chunking = [DataStats.CHUNK_MULTIPLE * chunk_size for chunk_size in data_variable.chunking()]
#            print'chunking = %s' % chunking

            start_index = [0,0]
            end_index = [0,0]
            chunk_count = [(shape[0] + chunking[0] - 1) / chunking[0], (shape[1] + chunking[1] - 1) / chunking[1]]
#            print'chunk_count = %s' % chunk_count
            
            length_read = 0
            weighted_mean = 0.0
            for _dimension0_index in range(chunk_count[0]):
                end_index[0] = min(start_index[0] + chunking[0], shape[0])
                start_index[1] = 0
                for _dimension1_index in range(chunk_count[1]):
                    end_index[1] = min(start_index[1] + chunking[1], shape[1])
#                    print 'Range = %d:%d, %d:%d' % (start_index[0], end_index[0], start_index[1], end_index[1])
                    chunk_array = variable[start_index[0]:end_index[0], start_index[1]:end_index[1]]
                    if type(chunk_array) == np.ma.core.MaskedArray:
                        chunk_array = chunk_array.data
#                    print 'chunk_array.shape = %s, chunk_array.size = %s' % (chunk_array.shape, chunk_array.size)
                    chunk_array = np.array(chunk_array[chunk_array != self._data_stats['nodata_value']]) # Discard all no-data elements
                    chunk_length = len(chunk_array)

                    if chunk_length:
                        try:
                            self._data_stats['min'] = min(self._data_stats['min'], np.nanmin(chunk_array))
                        except:
                            self._data_stats['min'] = np.nanmin(chunk_array)

                        try:
                            self._data_stats['max'] = max(self._data_stats['max'], np.nanmax(chunk_array))
                        except:
                            self._data_stats['max'] = np.nanmax(chunk_array)

                        weighted_mean = weighted_mean + np.nanmean(chunk_array) * chunk_length
                        length_read += chunk_length
#                    else:
#                        print 'Empty array'

                    del chunk_array
                    gc.collect()
                    start_index[1] = end_index[1]

                start_index[0] = end_index[0]
            
            self._data_stats['mean'] = weighted_mean / length_read
            
            #TODO: Implement something clever for these
            self._data_stats['median'] = np.NaN
            self._data_stats['percentile_1'] = np.NaN
            self._data_stats['percentile_99'] = np.NaN
        
    def value(self, key):
        return self._data_stats[key]
        
def main():
    print ','.join(DataStats.key_list)
    for netcdf_path in sys.argv[1:]:
        datastats = DataStats(netcdf_path)
        print ','.join([str(datastats.value(key)) for key in DataStats.key_list])

if __name__ == '__main__':
    main()

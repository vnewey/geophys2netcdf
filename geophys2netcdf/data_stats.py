'''
Created on 15Aug.,2016

@author: Alex
'''
import sys
import gc
import netCDF4
import math
import numpy as np
from geophys2netcdf.array_pieces import array_pieces

class DataStats(object):
    '''
    DataStats class definition. Obtains statistics for gridded data
    '''
    key_list = ['nc_path', 'data_type', 'nodata_value', 'x_size', 'y_size', 'min', 'max', 'mean'] #, 'median', 'std_dev', 'percentile_1', 'percentile_99']

    def __init__(self, netcdf_path, max_array=500000000):
        '''
        DataStats Constructor
        Parameter:
            netcdf_path - string representing path to NetCDF file or URL for an OPeNDAP endpoint
            max_array - maximum number of bytes to pull into memory
        '''
        netcdf_dataset = netCDF4.Dataset(netcdf_path)
        
        # Find variable with "grid_mapping" attribute - assumed to be 2D data variable
        try:
            data_variable = [variable for variable in netcdf_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
        except:
            raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')
        
        self._data_stats = {}        
        self._data_stats['nc_path'] = netcdf_path
        self._data_stats['data_type'] = str(data_variable.dtype)
        self._data_stats['nodata_value'] = data_variable._FillValue        

        shape = data_variable.shape
        # Array is ordered YX
        self._data_stats['x_size'] = shape[1]
        self._data_stats['y_size'] = shape[0]

        length_read = 0
        weighted_mean = 0.0
        
        for piece_array, _piece_offsets in array_pieces(data_variable, max_array):

            if type(piece_array) == np.ma.core.MaskedArray:
                piece_array = piece_array.data
                
            piece_array = np.array(piece_array[piece_array != data_variable._FillValue]) # Discard all no-data elements
            
            piece_size = len(piece_array)
            
            if piece_size:       
                try:
                    self._data_stats['min'] = min(self._data_stats['min'], np.nanmin(piece_array))
                except:
                    self._data_stats['min'] = np.nanmin(piece_array)
        
                try:
                    self._data_stats['max'] = max(self._data_stats['max'], np.nanmax(piece_array))
                except:
                    self._data_stats['max'] = np.nanmax(piece_array)
        
                weighted_mean += np.nanmean(piece_array) * piece_size
                length_read += piece_size
            #===================================================================
            # else:
            #     print 'Empty array'
            #===================================================================
            
        self._data_stats['mean'] = weighted_mean / length_read
            
        #===================================================================
        # #TODO: Implement something clever for these
        # self._data_stats['median'] = np.NaN
        # self._data_stats['std_dev'] = np.NaN
        # self._data_stats['percentile_1'] = np.NaN
        # self._data_stats['percentile_99'] = np.NaN    
        #===================================================================


def main():
    print ','.join(DataStats.key_list)
    for netcdf_path in sys.argv[1:]:
        datastats = DataStats(netcdf_path)
        print ','.join([str(datastats.value(key)) for key in DataStats.key_list])

if __name__ == '__main__':
    main()

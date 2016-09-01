'''
process_array.py
Created on 1 Sep,2016

@author: Alex Ip
'''
import sys
import netCDF4
import math
import itertools

def array_pieces(nc_data_variable, max_bytes=500000000):
    '''
    Generator to return a series of numpy arrays less than max_bytes in size and the offset within the complete data from a NetCDF variable
    Parameters:
        nc_data_variable: NetCDF array variable
        max_bytes: Maximum number of bytes to retrieve. Defaults to 500,000,000 for NCI's OPeNDAP
        
    Yields:
        piece_array: array subset less than max_bytes in size
        array_offset: start indices of subset in whole array
    '''
    array_shape = nc_data_variable.shape
    array_dimensions = len(array_shape)
    
    # Determine overall array size in bytes
    array_bytes = nc_data_variable.dtype.itemsize * reduce(lambda x, y: x*y, array_shape)

    if array_bytes > max_bytes: # Multiple pieces required
        # Determine number of divisions in each axis required to keep pieces under max_bytes in size
        axis_divisions = int(math.ceil(math.pow(math.ceil(array_bytes / float(max_bytes)), 1.0 / array_dimensions)))
    
        # Determine chunk size for pieces or default to natural divisions if no chunking set
        chunking = nc_data_variable.chunking() or (1, 1) 
    
        # Determine piece shape rounded down to chunk sizes
        piece_shape = [array_shape[index] / axis_divisions / chunking[index] * chunking[index] for index in range(array_dimensions)]
    
        # Determine number of pieces in each axis - all elements should all be the same, so this is probably redundant
        axis_pieces = [array_shape[index] / piece_shape[index] for index in range(array_dimensions)]

        # Iterate over every piece of array
        for piece_indices in itertools.product(*[range(axis_pieces[dimension_index]) for dimension_index in range(array_dimensions)]):
            start_indices = [piece_indices[dimension_index] * piece_shape[dimension_index] for dimension_index in range(array_dimensions)]
            end_indices = [min(start_indices[dimension_index] + piece_shape[dimension_index], array_shape[dimension_index]) for dimension_index in range(array_dimensions)]
            array_slices = [slice(start_indices[dimension_index], end_indices[dimension_index]) for dimension_index in range(array_dimensions)]
            
            piece_array = nc_data_variable[array_slices]
            yield piece_array, tuple(start_indices) 
                 
    else: # Only one piece required
        yield nc_data_variable[:], (0, 0)
          
def main():
    '''
    Main function for testing
    '''
    netcdf_path = sys.argv[1]
    netcdf_dataset = netCDF4.Dataset(netcdf_path)
    
    # Find variable with "grid_mapping" attribute - assumed to be 2D data variable
    try:
        data_variable = [variable for variable in netcdf_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
    except:
        raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')
    
    piece_count = 0
    for piece_array, array_offset in array_pieces(data_variable):
        piece_count += 1
        piece_bytes = data_variable.dtype.itemsize * reduce(lambda x, y: x*y, data_variable.shape)
        print 'piece_array.shape = %s, array_offset = %s, piece_bytes = %d' % (piece_array.shape, array_offset, piece_bytes)
        
    print 'piece_count = %s' % piece_count

if __name__ == '__main__':
    main()

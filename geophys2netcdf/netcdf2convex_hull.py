'''
Functions to obtain edge points and convex hull vertices from a gridded NetCDF dataset

Created on 12Sep.,2016

@author: Alex Ip
'''
import numpy as np
#import netCDF4
from scipy import ndimage
import shapely.geometry as geometry
from geophys2netcdf.array_pieces import array_pieces

def get_edge_points(netcdf_dataset, max_bytes=None):
    '''
    Function to return a list of coordinates corresponding to pixels on the edge of data-containing areas of the NetCDF dataset
    '''
    # Find variable with "grid_mapping" attribute - assumed to be 2D data variable
    try:
        data_variable = [variable for variable in netcdf_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
    except:
        raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')
#    print 'Variable %s has shape %s' % (data_variable.name, data_variable.shape)
    
    assert len(data_variable.dimensions) == 2, '%s is not 2D' % data_variable.name
    dimension_variable = [netcdf_dataset.variables[data_variable.dimensions[dim_index]] for dim_index in range(2)]
    nodata_value = data_variable._FillValue
    
    edge_point_list = [] # Complete list of edge points (unknown length)
    for piece_array, array_offset in array_pieces(data_variable, max_bytes):
        dimension_subset = [dimension_variable[dim_index][array_offset[dim_index]:array_offset[dim_index]+piece_array.shape[dim_index]] for dim_index in range(2)]
        
        # Convert masked array to plain array
        if type(piece_array) == np.ma.core.MaskedArray:
            piece_array = piece_array.data
#        print 'array_offset = %s, piece_array.shape = %s, piece_array.size = %s' % (array_offset, piece_array.shape, piece_array.size)

        piece_array = (piece_array != nodata_value) # Convert to boolean True=data/False=no-data array
        
        # Detect edges
        edge_ordinates = np.where(ndimage.filters.maximum_filter(piece_array, size=2) != 
                         ndimage.filters.minimum_filter(piece_array, size=2))

        if edge_ordinates[0].size:
            piece_edge_points = np.zeros((edge_ordinates[0].size, 2), dtype=netcdf_dataset.variables[data_variable.dimensions[0]].dtype)
            #TODO: Do something more general here to account for YX or XY dimension order
            piece_edge_points[:,1] = dimension_subset[0][edge_ordinates[0]]
            piece_edge_points[:,0] = dimension_subset[1][edge_ordinates[1]]
            edge_point_list += list(piece_edge_points)
#            print '%s edge points found' % piece_edge_points.shape[0]
#        else:
#            print 'No edge points found'

    return edge_point_list


def points2convex_hull(point_list, dilation=0, tolerance=0):
    '''
    Function to return a list of vertex coordinates in the convex hull around data-containing areas of a point list
    Parameters:
        point_list: Iterable containing points from which to compute convex hull
        dilation: distance to dilate convex hull
        tolerance: distance tolerance for the simplification of the convex hull
    '''
    convex_hull = geometry.MultiPoint(point_list).convex_hull
    
    # Offset outward by a full pixel width (instead of half) and simplify with one pixel width tolerance
    convex_hull = convex_hull.buffer(dilation, cap_style=2, join_style=2, mitre_limit=tolerance).simplify(tolerance)
    
    return [coordinates for coordinates in convex_hull.exterior.coords] # Convert generator to list
    
    
def netcdf2convex_hull(netcdf_dataset, max_bytes=None):
    '''
    Function to return a list of vertex coordinates in the convex hull around data-containing areas of the NetCDF dataset
    Parameters:
        netcdf_dataset: netCDF4.Dataset object
        max_bytes: Maximum number of bytes to retrieve in each array piece
    '''
    # Find variable with "GeoTransform" attribute - assumed to be grid mapping variable
    try:
        grid_mapping_variable = [variable for variable in netcdf_dataset.variables.values() if hasattr(variable, 'GeoTransform')][0]
    except:
        raise Exception('Unable to determine grid mapping variable (must have "GeoTransform" attribute')
    GeoTransform = [float(number) for number in grid_mapping_variable.GeoTransform.strip().split(' ')]
    avg_pixel_size = (abs(GeoTransform[1]) + abs(GeoTransform[5])) / 2.0
   
    return points2convex_hull(get_edge_points(netcdf_dataset, max_bytes), avg_pixel_size, avg_pixel_size) 
    

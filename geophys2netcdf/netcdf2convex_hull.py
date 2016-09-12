'''
Created on 12Sep.,2016

@author: Alex Ip
'''
import numpy as np
#import netCDF4
import gc
from scipy import ndimage
import shapely.geometry as geometry
from shapely.ops import polygonize
from geophys2netcdf.array_pieces import array_pieces

def netcdf2convex_hull(netcdf_dataset, max_bytes=None):
    '''
    Function to return a list of vertices in the convex hull around data-containing areas
    '''
    def get_edge_points(netcdf_dataset, max_bytes=None):
        '''
        Function to return a list of points corresponding to pixels on the edge of data-containing areas
        '''
        # Find variable with "grid_mapping" attribute - assumed to be 2D data variable
        try:
            data_variable = [variable for variable in netcdf_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
        except:
            raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')
#        print data_variable.name
        
        assert len(data_variable.dimensions) == 2, '%s is not 2D' % data_variable.name
        dimension_variable = [netcdf_dataset.variables[data_variable.dimensions[dim_index]] for dim_index in range(2)]
        nodata_value = data_variable._FillValue
        
        point_list = [] # Complete list of edge points (unknown length)
        for piece_array, array_offset in array_pieces(data_variable):
            dimension_subset = [dimension_variable[dim_index][array_offset[dim_index]:piece_array.shape[dim_index]] for dim_index in range(2)]
            
            if type(piece_array) == np.ma.core.MaskedArray:
                piece_array = piece_array.data
#            print 'piece_array.shape = %s, piece_array.size = %s' % (piece_array.shape, piece_array.size)
            piece_array = (piece_array != nodata_value)
            
            # Detect edges
            edges = np.where(ndimage.filters.maximum_filter(piece_array, size=2) != 
                             ndimage.filters.minimum_filter(piece_array, size=2))
    
            if edges[0].size:
                piece_points = np.zeros((edges[0].size, 2), dtype=netcdf_dataset.variables[data_variable.dimensions[0]].dtype)
                #TODO: Do something more general here to account for YX or XY dimension order
                piece_points[:,1] = dimension_subset[0][edges[0]]
                piece_points[:,0] = dimension_subset[1][edges[1]]
                point_list += list(piece_points)
#                print '%s edge points found' % piece_points.shape[0]
#            else:
#                print 'No edge points found'

            del piece_array
            del piece_points
            gc.collect()
            
        return point_list
        
    # Start of netcdf2convex_hull function
    GeoTransform = [float(number) for number in netcdf_dataset.variables['crs'].GeoTransform.strip().split(' ')]
    avg_pixel_size = (abs(GeoTransform[1]) + abs(GeoTransform[5])) / 2.0

    convex_hull = geometry.MultiPoint(get_edge_points(netcdf_dataset, max_bytes)).convex_hull
    
    convex_hull = convex_hull.buffer(avg_pixel_size/2.0, cap_style=2, join_style=2, mitre_limit=avg_pixel_size).simplify(avg_pixel_size) # Offset outward by half a pixel width    
    
    #===========================================================================
    # # Perform offsets to (hopefully) simplify shape and take pixel size into account
    # convex_hull = convex_hull.buffer(-avg_pixel_size / 2.0, cap_style=3, join_style=3, mitre_limit=avg_pixel_size) # Offset inward by half a pixel width
    # convex_hull = convex_hull.buffer(avg_pixel_size, cap_style=3, join_style=3, mitre_limit=avg_pixel_size) # Offset outward by a whole pixel width    
    #===========================================================================
    
    return [coordinates for coordinates in convex_hull.exterior.coords] # Convert generator to list
    
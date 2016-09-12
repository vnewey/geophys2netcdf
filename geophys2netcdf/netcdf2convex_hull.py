'''
Created on 12Sep.,2016

@author: Alex Ip
'''
import numpy as np
#import netCDF4
import gc
from scipy import ndimage
from scipy.spatial import ConvexHull
from geophys2netcdf.array_pieces import array_pieces

def netcdf2convex_hull(netcdf_dataset, max_bytes=None):
    '''
    Function to return a numpy array containing coordinates of the vertices of a closed convex hull around data-containing areas
    '''
    def get_edge_points(netcdf_dataset, max_bytes=None):
        # Find variable with "grid_mapping" attribute - assumed to be 2D data variable
        try:
            data_variable = [variable for variable in netcdf_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
        except:
            raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')
#        print data_variable.name
        
        assert len(data_variable.dimensions) == 2, '%s is not 2D' % data_variable.name
        dimension_variable = [netcdf_dataset.variables[data_variable.dimensions[dim_index]] for dim_index in range(2)]
        nodata_value = data_variable._FillValue
        
        piece_point_list = [] # List of point arrays
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
                piece_points[:,1] = dimension_subset[0][edges[0]]
                piece_points[:,0] = dimension_subset[1][edges[1]]
                piece_point_list.append(piece_points)
#                print '%s edge points found' % piece_points.shape[0]
#            else:
#                print 'No edge points found'

            del piece_array
            gc.collect()
            
        # Determine total number of points and create points array
        point_count = 0
        for piece_points in piece_point_list:
            point_count += piece_points.shape[0]
            
        points = np.zeros((point_count, 2), dtype=netcdf_dataset.variables[data_variable.dimensions[0]].dtype)
        
        point_count = 0
        for piece_points in piece_point_list:
            start_index = point_count
            point_count += piece_points.shape[0]
            points[start_index:point_count,:] = piece_points
        
        return points
        
    # Start of netCDF2convex_hull function
    points = get_edge_points(netcdf_dataset, max_bytes)
    
    convex_hull = ConvexHull(points)
    vertex_count = len(convex_hull.vertices)
    
    vertices = np.zeros((vertex_count + 1, 2), dtype=points.dtype) # Allow for repeated start/end point
    
    vertices[0:vertex_count] = points[convex_hull.vertices]
    vertices[-1] = vertices[0] # Close shape by repeating first vertex
    
    return vertices
    
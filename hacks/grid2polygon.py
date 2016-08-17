#!/bin/python
from scipy.spatial import ConvexHull
import scipy.ndimage as ndimage
import numpy as np
import netCDF4
import gc
import sys

CHUNK_MULTIPLE = 256 # Number of chunks to grab in each dimension


netcdf_dataset = netCDF4.Dataset(sys.argv[1])

# Find variable with "grid_mapping" attribute - assumed to be 2D data variable
try:
    data_variable = [variable for variable in netcdf_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
except:
    raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')
#print data_variable.name

shape = data_variable.shape
#print 'shape = %s' % (shape,)

chunking = [CHUNK_MULTIPLE * chunk_size for chunk_size in data_variable.chunking()]
#print 'chunking = %s' % chunking

chunk_count = [(shape[0] + chunking[0] - 1) / chunking[0], (shape[1] + chunking[1] - 1) / chunking[1]]
#print 'chunk_count = %s' % chunk_count

start_index = [0,0]
end_index = [0,0]
segment_points = [] # List of point arrays
for _dimension0_index in range(chunk_count[0]):
    end_index[0] = min(start_index[0] + chunking[0], shape[0])
    start_index[1] = 0
    for _dimension1_index in range(chunk_count[1]):
        end_index[1] = min(start_index[1] + chunking[1], shape[1])
#        print 'Range = %d:%d, %d:%d' % (start_index[0], end_index[0], start_index[1], end_index[1])
        chunk_array = variable[start_index[0]:end_index[0], start_index[1]:end_index[1]]
        if type(chunk_array) == np.ma.core.MaskedArray:
            chunk_array = chunk_array.data
#        print 'chunk_array.shape = %s, chunk_array.size = %s' % (chunk_array.shape, chunk_array.size)
        chunk_array = (chunk_array != data_variable._FillValue)
        edges = np.where(ndimage.filters.maximum_filter(chunk_array, size=2) != 
                         ndimage.filters.minimum_filter(chunk_array, size=2))

        if edges[0].size: # Edges found
            sub_points = np.zeros((edges[0].size, 2), dtype=netcdf_dataset.variables[data_variable.dimensions[0]].dtype)
            sub_points[:,1] = (netcdf_dataset.variables[data_variable.dimensions[0]][start_index[0]:end_index[0]])[edges[0]]
            sub_points[:,0] = (netcdf_dataset.variables[data_variable.dimensions[1]][start_index[1]:end_index[1]])[edges[1]]
            segment_points.append(sub_points)
#            print '%s edge points found' % sub_points.shape[0]
#        else:
#            print 'No edge points found'
        
        del chunk_array
        gc.collect()
        start_index[1] = end_index[1]

    start_index[0] = end_index[0]

point_count = 0
for sub_points in segment_points:
    point_count += sub_points.shape[0]
    
points = np.zeros((point_count, 2), dtype=netcdf_dataset.variables[data_variable.dimensions[0]].dtype)
#print points.shape

point_count = 0
for sub_points in segment_points:
    start_index = point_count
    point_count += sub_points.shape[0]
    points[start_index:point_count,:] = sub_points

del sub_points
gc.collect()

hull = ConvexHull(points)

# Convert array to list of lists
vertices = [list(vertex) for vertex in points[hull.vertices]]
vertices.append(vertices[0]) # Close polygon

print 'POLYGON((' + ','.join([','.join(['%.6f' % ordinate for ordinate in vertex]) for vertex in vertices]) + '))'

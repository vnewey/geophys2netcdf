'''
Created on 14Sep.,2016

@author: Alex
'''
import re
import numpy as np
import netCDF4
from osgeo.osr import SpatialReference, CoordinateTransformation


class NetCDF2DUtils(object):
    '''
    classdocs
    '''
    # Assume WGS84 lat/lon if no CRS is provided
    DEFAULT_CRS = "GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\",SPHEROID[\"WGS 84\",6378137,298.257223563,AUTHORITY[\"EPSG\",\"7030\"]],AUTHORITY[\"EPSG\",\"6326\"]],PRIMEM[\"Greenwich\",0,AUTHORITY[\"EPSG\",\"8901\"]],UNIT[\"degree\",0.0174532925199433,AUTHORITY[\"EPSG\",\"9122\"]],AUTHORITY[\"EPSG\",\"4326\"]]"
    HORIZONTAL_VARIABLE_NAMES = ['lon', 'Easting', 'x', 'longitude']
    
    def __init__(self, netcdf_dataset):
        '''
        NetCDF2DUtils Constructor
        '''
        self.netcdf_dataset = netcdf_dataset
        
#        assert len(self.netcdf_dataset.dimensions) == 2, 'NetCDF dataset must be 2D' # This is not valid
        
        # Find variable with "grid_mapping" attribute - assumed to be 2D data variable
        try:
            self.data_variable = [variable for variable in self.netcdf_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
        except:
            raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')
        
        # Boolean flag indicating YX array ordering
        #TODO: Find a nicer way of dealing with this
        self.YX_order = self.data_variable.dimensions[1] in  NetCDF2DUtils.HORIZONTAL_VARIABLE_NAMES
        
        # Two-element list of dimension varibles. 
        self.dimension_arrays = [self.netcdf_dataset.variables[dimension_name][:] for dimension_name in self.data_variable.dimensions]
        
        self.grid_mapping_variable = netcdf_dataset.variables[self.data_variable.grid_mapping]
        
        self.GeoTransform = [float(number) for number in self.grid_mapping_variable.GeoTransform.strip().split(' ')]
        
        self.pixel_size = [abs(self.GeoTransform[1]), abs(self.GeoTransform[5])]
        if self.YX_order:
            self.pixel_size.reverse()
        
        self.min_extent = tuple([min(self.dimension_arrays[dim_index]) - self.pixel_size[dim_index]/2.0 for dim_index in range(2)])
        self.max_extent = tuple([max(self.dimension_arrays[dim_index]) + self.pixel_size[dim_index]/2.0 for dim_index in range(2)])
        
    
    def get_coordinate_transformation(self, crs=None, to_native=True):
        # Assume native coordinates if no crs given
        if not crs:
            return None
        
        coord_spatial_ref = SpatialReference()
        # Check for EPSG then Well Known Text
        epsg_match = re.match('^EPSG:(\d+)$', crs)
        if epsg_match:
            coord_spatial_ref.ImportFromEPSG(int(epsg_match.group(1)))
        else: # Assume valid WKT definition
            coord_spatial_ref.ImportFromWkt(crs)    
            
        native_spatial_ref = SpatialReference()
        native_spatial_ref.ImportFromWkt(self.grid_mapping_variable.spatial_ref)
        
        if coord_spatial_ref.ExportToWkt() == native_spatial_ref.ExportToWkt(): 
            return None
        
        if to_native:
            return CoordinateTransformation(coord_spatial_ref, native_spatial_ref)
        else:
            return CoordinateTransformation(native_spatial_ref, coord_spatial_ref)
        
    
        
    def get_native_coords(self, coordinates, crs=None):
        coord_trans = self.get_coordinate_transformation(crs, to_native=True)
        
        if not coord_trans:
            return list(coordinates)
        
        try: # Multiple coordinates
            return [coordinate[0:2] for coordinate in coord_trans.TransformPoints(coordinates)]
        except: # Single coordinate
            return coord_trans.TransformPoint(*coordinates)[0:2]
        
    
    def get_indices_from_coords(self, coordinates, crs=None):
        '''
        '''
        native_coordinates = self.get_native_coords(coordinates, crs)
        
        # Convert coordinates to same order as array
        if self.YX_order:
            try:
                for coord_index in range(len(native_coordinates)):
                    if native_coordinates[coord_index] is not None:
                        native_coordinates[coord_index] = list(native_coordinates[coord_index])
                        native_coordinates[coord_index].reverse()
            except:
                native_coordinates = list(native_coordinates)            
                native_coordinates.reverse()
        try: # Multiple coordinates
            indices = [[np.where(abs(self.dimension_arrays[dim_index] - coordinate[dim_index]) <= (self.pixel_size[dim_index] / 2.0))[0][0] for dim_index in range(2)]
                       if not ([True for dim_index in range(2) if coordinate[dim_index] < self.min_extent[dim_index] or coordinate[dim_index] > self.max_extent[dim_index]])
                       else None
                       for coordinate in native_coordinates]
        except: # Single coordinate pair
            indices = ([np.where(abs(self.dimension_arrays[dim_index] - native_coordinates[dim_index]) <= (self.pixel_size[dim_index] / 2.0))[0][0] for dim_index in range(2)]
                       if not [True for dim_index in range(2) if native_coordinates[dim_index] < self.min_extent[dim_index] or native_coordinates[dim_index] > self.max_extent[dim_index]]
                       else None)
            
        return indices
        
        
    def get_value_at_coords(self, coordinates, crs=None, variable_name=None):
        '''
        '''
        if variable_name:
            data_variable = self.netcdf_dataset.variables[variable_name]
        else:
            data_variable = self.data_variable
            
        no_data_value = data_variable._FillValue

        indices = self.get_indices_from_coords(coordinates, crs)
        
        if not indices:
            return None
                
        try:
            # Make this a vectorised operation for speed (one query for all points)
            mask_array = np.array([(index_pair is not None) for index_pair in indices]) # Boolean mask indicating which index pairs are valid
            index_array = np.array([index_pair for index_pair in indices if index_pair is not None]) # Array of valid index pairs only
        
            # N.B: ".diagonal()" is required because NetCDF doesn't do advanced indexing exactly like numpy
            # Ugly hack is required to take values from leading diagonal. Requires n^2 elements retrieved instead of n. Not good
            #TODO: Think of a better way of doing this
            value_array = data_variable[(index_array[:,0], index_array[:,1])].diagonal()
            print value_array
            result_array = np.ones(shape=(len(indices)), dtype=value_array.dtype) * no_data_value
            result_array[mask_array] = value_array
            return list(result_array)
        except:
            return data_variable[indices[0], indices[1]]
        
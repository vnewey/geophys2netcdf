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

    def __init__(self, netcdf_dataset):
        '''
        NetCDF2DUtils Constructor
        '''
        self.netcdf_dataset = netcdf_dataset
        
        assert len(self.netcdf_dataset.dimensions) == 2, 'NetCDF dataset must be 2D'
        
        # Two-element list of dimension varibles. Assumed to be ordered XY
        self.dimension_arrays = [self.netcdf_dataset.variables[dimension_name][:] for dimension_name in self.netcdf_dataset.dimensions.keys()]
        
        # Find variable with "grid_mapping" attribute - assumed to be 2D data variable
        try:
            self.data_variable = [variable for variable in self.netcdf_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
        except:
            raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')
        
        # Set up dict to account for YX array ordering
#        self.array_dim = {dim_index: self.data_variable.dimensions.index(self.netcdf_dataset.dimensions.keys()[dim_index]) for dim_index in range(2)}

        self.YX_order = (self.data_variable.dimensions != self.netcdf_dataset.dimensions.keys())
        
        self.grid_mapping_variable = netcdf_dataset.variables[self.data_variable.grid_mapping]
        
        self.GeoTransform = [float(number) for number in self.grid_mapping_variable.GeoTransform.strip().split(' ')]
        
        self.pixel_size = (abs(self.GeoTransform[1]), abs(self.GeoTransform[5]))
        self.min_extent = tuple([min(self.dimension_arrays[dim_index]) - self.pixel_size[dim_index] for dim_index in range(2)])
        self.max_extent = tuple([max(self.dimension_arrays[dim_index]) + self.pixel_size[dim_index] for dim_index in range(2)])
        
    
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
        
    
        
    def native_coords(self, coordinates, crs=None):
        coord_trans = self.get_coordinate_transformation(crs, to_native=True)
        
        if not coord_trans:
            return coordinates
        
        try: # Multiple coordinates
            return [coordinate[0:2] for coordinate in coord_trans.TransformPoints(coordinates)]
        except: # Single coordinate
            return coord_trans.TransformPoint(*coordinates)[0:2]
        
    
    def indices_from_coord(self, coordinate, crs=None):
        '''
        '''
        native_coordinates = self.native_coords(coordinate, crs)
        
        try: # Multiple coordinates
            indices = [[np.where(abs(self.dimension_arrays[dim_index] - coordinate[dim_index]) <= (self.pixel_size[dim_index] / 2.0))[0][0] for dim_index in range(2)]
                       if not ([True for dim_index in range(2) if coordinate[dim_index] < self.min_extent[dim_index] or coordinate[dim_index] > self.max_extent[dim_index]])
                       else None
                       for coordinate in native_coordinates]
            
            if self.YX_order:
                for index_pair in indices:
                    if index_pair is not None:
                        index_pair.reverse()
        except: # Singlue coordinate pair
            indices = ([np.where(abs(self.dimension_arrays[dim_index] - native_coordinates[dim_index]) <= (self.pixel_size[dim_index] / 2.0))[0][0] for dim_index in range(2)]
                       if not [True for dim_index in range(2) if native_coordinates[dim_index] < self.min_extent[dim_index] or native_coordinates[dim_index] > self.max_extent[dim_index]]
                       else None)
    
            if self.YX_order and indices:
                indices.reverse()
            
        return indices
        
        
    def value_at_coord(self, coordinates, crs=None, variable_name=None):
        '''
        '''
        if variable_name:
            data_variable = self.netcdf_dataset.variables[variable_name]
        else:
            data_variable = self.data_variable
            
        indices = self.indices_from_coord(coordinates, crs)
        
        if not indices:
            return None
        
        try:
            return list([data_variable[index_pair[0], index_pair[1]] if index_pair else None for index_pair in indices])
        except:
            return data_variable[indices[0], indices[1]]
        
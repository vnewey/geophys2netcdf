#!/usr/bin/env python

#===============================================================================
# Copyright (c)  2014 Geoscience Australia
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither Geoscience Australia nor the names of its contributors may be
#       used to endorse or promote products derived from this software
#       without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#===============================================================================
'''
Geophys2NetCDF Class
Created on 29/02/2016

@author: Alex Ip
'''
import os
import re
import sys
from collections import OrderedDict
import logging
import subprocess
from osgeo import gdal, osr
import numpy as np
import netCDF4
from owslib.csw import CatalogueServiceWeb
from owslib.fes import PropertyIsEqualTo, PropertyIsLike, BBox

from metadata import XMLMetadata


# Set handler for root logger to standard output
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
#console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)
logging.root.addHandler(console_handler)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Initial logging level for this module

from gdf._arguments import CommandLineArgs
from gdf._config_file import ConfigFile

class Geophys2NetCDF(object):
    '''
    Class definition for Geophys2NETCDF
    Base class for geophysics conversions
    '''
    NCI_CSW = 'http://geonetworkrr2.nci.org.au/geonetwork/srv/eng/csw'
    GA_CSW = 'http://www.ga.gov.au/geonetwork/srv/en/csw'

    def __init__(self, debug=False):
        '''
        '''
        self._debug = False
        self.debug = debug # Set property
        self._code_root = os.path.abspath(os.path.dirname(__file__)) # Directory containing module code
        
        self._input_path = None
        self._output_path = None
        self._input_dataset = None # GDAL Dataset for input
        self._netcdf_dataset = None # NetCDF Dataset for output
        self._metadata_dict = {}
        self._metadata_mapping_dict = OrderedDict()
        
    def translate(self, input_path, output_path=None):
        '''
        Virtual function - performs basic initialisation for file translations
        Should be overridden in subclasses for each specific format but called first to perform initialisations
        '''
        assert os.path.exists(input_path), 'Input file %s does not exist' % input_path
        self._input_path = os.path.abspath(input_path)
        
        # Default to outputting .nc file of same name in current dir
        self._output_path = os.path.abspath(output_path or os.path.splitext(os.path.basename(input_path))[0] + '.nc')
        if os.path.exists(self._output_path):
            logger.warning('Output NetCDF file %s already exists. Backing up to %s.bck', self._output_path, self._output_path)
            mv_command = ['mv', 
                            self._output_path,
                            self._output_path + '.bck'
                            ]
            logger.debug('mv_command = %s', mv_command)
            subprocess.check_call(mv_command)
            
        self._input_dataset = None
        self._netcdf_dataset = None
        self._metadata_dict = {}
    
    def update_nc_metadata(self, output_path=None):
        '''
        Function to import all available metadata and set attributes in NetCDF file.
        Should be overridden in subclasses for each specific format but called first to perform initialisations
        '''
        assert output_path or self._output_path, 'Output NetCDF path not defined'
        
        if output_path: # New output path specified for update
            self._output_path = output_path
            if self._netcdf_dataset:
                self._netcdf_dataset.close()
            self._netcdf_dataset = netCDF4.Dataset(self._output_path, mode='r+')
            self.import_metadata()

        assert self._metadata_dict, 'No metadata acquired'
        self.set_netcdf_metadata_attributes()
        
    def import_metadata(self):
        '''
        Virtual function to read metadata from all available sources and set self._metadata_dict. 
        Should be overridden for each specific format
        '''
        if self._input_dataset:
            self._metadata_dict['GDAL'] = self._input_dataset.GetMetadata_Dict() # Read generic GDAL metadata (if any)
        else:
            logger.warning('No GDAL-compatible input dataset defined.')
        
    def get_metadata(self, metadata_path):
        '''
        Function to read metadata from nested dict self._metadata_dict.
        Returns None if atrribute does not exist
        Argument:
            metadata_path: Period-delineated path to required metadata element
        '''

        focus_element = self._metadata_dict
        subkey_list = metadata_path.split('.')
        for subkey in subkey_list:
            focus_element = focus_element.get(subkey)
            if focus_element is None: # Atrribute not found
                break
            
        return focus_element
        
    
    def set_netcdf_metadata_attributes(self): 
        '''
        Function to set all NetCDF metadata attributes using self._metadata_mapping_dict to map from NetCDF attribute name to 
        '''
        assert self._metadata_mapping_dict, 'No metadata mapping defined'
        assert self._netcdf_dataset, 'NetCDF output dataset not defined.'
#        assert self._metadata_dict, 'No metadata acquired'
        
        def getMinMaxExtents(samples, lines, geoTransform):
            """
            Calculates the min/max extents based on the geotransform and raster sizes.
        
            :param samples:
                An integer representing the number of samples (columns) in an array.
        
            :param lines:
                An integer representing the number of lines (rows) in an array.
        
            :param geoTransform:
                A tuple containing the geotransform information returned by GDAL.
        
            :return:
                A tuple containing (min_lat, max_lat, min_lon, max_lat)
        
            :notes:
                Hasn't been tested for northern or western hemispheres.
            """
            extents = []
            x_list  = [0, samples]
            y_list  = [0, lines]
        
            for px in x_list:
                for py in y_list:
                    x = geoTransform[0]+(px*geoTransform[1])+(py*geoTransform[2])
                    y = geoTransform[3]+(px*geoTransform[4])+(py*geoTransform[5])
                    extents.append([x,y])
        
            extents = np.array(extents)
            min_lat = np.min(extents[:,1])
            max_lat = np.max(extents[:,1])
            min_lon = np.min(extents[:,0])
            max_lon = np.max(extents[:,0])
        
            return (min_lat, max_lat, min_lon, max_lon)

        # Set geospatial attributes
        crs = self._netcdf_dataset.variables['crs']
        geotransform = [float(string) for string in crs.GeoTransform.strip().split(' ')]
        # min_lat, max_lat, min_lon, max_lon = getMinMaxExtents(self._input_dataset.RasterXSize,
        #                                                       self._input_dataset.RasterYSize,
        #                                                       geotransform
        #                                                       )
        min_lat, max_lat, min_lon, max_lon = getMinMaxExtents(len(self._netcdf_dataset.variables['lon']),
                                                              len(self._netcdf_dataset.variables['lat']),
                                                              geotransform
                                                              )
        
        attribute_dict = dict(zip(['geospatial_lat_min', 'geospatial_lat_max', 'geospatial_lon_min', 'geospatial_lon_max'],
                                  [min_lat, max_lat, min_lon, max_lon]
                                  )
                              )
        attribute_dict['geospatial_lon_resolution'] = geotransform[1]
        attribute_dict['geospatial_lat_resolution'] = geotransform[5]
        attribute_dict['geospatial_bounds'] = 'POLYGON((%s %s, %s %s, %s %s, %s %s, %s %s))' % (min_lon, min_lat,
                                                                                                max_lon, min_lat,
                                                                                                max_lon, max_lat,
                                                                                                min_lon, max_lat,
                                                                                                min_lon, min_lat
                                                                                                )
        #attribute_dict['geospatial_bounds_crs'] = self._input_dataset.GetProjection()
        attribute_dict['geospatial_bounds_crs'] = crs.spatial_ref

        for key, value in attribute_dict.items():
            setattr(self._netcdf_dataset, key, value)

        # Set attributes defined in self._metadata_mapping_dict
        for key in self._metadata_mapping_dict.keys():
            metadata_path = self._metadata_mapping_dict[key]
            value = self.get_metadata(metadata_path)
            if value is not None:
                logger.debug('Setting %s to %s', key, value)
                setattr(self._netcdf_dataset, key, value) #TODO: Check whether hierarchical metadata required
            else:
                logger.warning('Metadata path %s not found', metadata_path)
                
        # Ensure only one metadata link is stored - could be multiple, comma-separated entries
        if hasattr(self._netcdf_dataset, 'metadata_link'):
            url_list = [url.strip() for url in (getattr(self._netcdf_dataset, 'metadata_link').split(','))]
            doi_list = [url for url in url_list if url.startswith('http://dx.doi.org/')]
            if len(url_list) > 1: # If more than one URL in list
                try:
                    url = doi_list[0] # Use first (preferably only) DOI URL
                except:
                    url = url_list[0] # Just use first URL if no DOI found
                setattr(self._netcdf_dataset, 'metadata_link', url)
            


    def get_csw_record_from_title(self, csw_url, title):
        '''
        Function to return OWSLib CSW record record from specified CSW URL using title as the search criterion
        '''
        csw = CatalogueServiceWeb(csw_url)
        assert csw.identification.type == 'CSW', '%s is not a valid CSW service' % csw_url  
        
        title_query = PropertyIsEqualTo('csw:Title', title.replace('_', '%'))
        csw.getrecords2(constraints=[title_query], esn='full', outputschema='http://www.isotc211.org/2005/gmd', maxrecords=2)
        
        # Ensure there is exactly one record found
        assert len(csw.records) > 0, 'No CSW records found for title "%s"' % title
        assert len(csw.records) == 1, 'Multiple CSW records found for title "%s"' % title
        
        return csw.records.values()[0]
    
    def get_csw_record_by_id(self, csw_url, identifier):
        '''
        Function to return OWSLib CSW record record from specified CSW URL using UUID as the search criterion
        '''
        csw = CatalogueServiceWeb(csw_url)
        assert csw.identification.type == 'CSW', '%s is not a valid CSW service' % csw_url   
        
        csw.getrecordbyid(id=[identifier], esn='full', outputschema='http://www.isotc211.org/2005/gmd')
        
        # Ensure there is exactly one record found
        assert len(csw.records) > 0, 'No CSW records found for ID "%s"' % identifier
        assert len(csw.records) == 1, 'Multiple CSW records found for ID "%s"' % identifier
        
        return csw.records.values()[0]


    def get_metadata_dict_from_xml(self, xml_string):
        '''
        Function to parse an XML string into a nested dict
        '''
        assert xml_string, 'No XML metadata string provided'
        xml_metadata = XMLMetadata()
        xml_metadata.read_string(xml_string)
        return xml_metadata.metadata_dict
        
    def do_md5sum(self):
        '''
        Function to generate MD5 checksum in file alongside output dataset
        Returns MD5 checksum
        '''
        assert self._output_path, 'No output path defined'
        assert self._netcdf_dataset, 'No NetCDF dataset defined'
        
        # Close and reopen NetCDF file as read-only
        self._netcdf_dataset.close()
        self._netcdf_dataset = netCDF4.Dataset(self._output_path, mode='r')

        md5sum_path = self._output_path + '.md5'
        md5sum_command = ['md5sum', self._output_path]
        md5_output = subprocess.check_output(md5sum_command)

        # Write chhecksum to file
        md5file = open(md5sum_path, 'w')
        md5file.write(md5_output)
        md5file.close()

        md5sum = md5_output.split(' ')[0]
        logger.debug('MD5 checksum %s written to %s', md5sum, md5sum_path)
        return md5sum

    @property
    def metadata_dict(self):
        return self._metadata_dict
    
    @property
    def metadata_sources(self):
        return sorted(self._metadata_dict.keys())
    
    @property
    def input_dataset(self):
        return self._input_dataset
    
    @property
    def netcdf_dataset(self):
        return self._netcdf_dataset
    
    @property
    def debug(self):
        return self._debug
    
    @debug.setter
    def debug(self, debug_value):
        if self._debug != debug_value:
            self._debug = debug_value
            
            if self._debug:
                logger.setLevel(logging.DEBUG)
            else:
                logger.setLevel(logging.INFO)

def main():
    g2n = Geophys2NetCDF(debug=True)
    g2n.translate('IR_gravity_anomaly_Australia_V1/IR_gravity_anomaly_Australia_V1.ers')
    
if __name__ == 'main':
    main()

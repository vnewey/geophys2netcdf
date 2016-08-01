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
from collections import OrderedDict
import logging
import subprocess
#from osgeo import gdal, osr
import numpy as np
import netCDF4
from owslib.csw import CatalogueServiceWeb
from owslib.fes import PropertyIsEqualTo #, PropertyIsLike, BBox
from datetime import datetime
import tempfile
import dateutil.parser
from dateutil import tz
import pytz
from glob import glob
import json
import urllib

from metadata import XMLMetadata, NetCDFMetadata

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # Initial logging level for this module

class Geophys2NetCDF(object):
    '''
    Class definition for Geophys2NETCDF
    Base class for geophysics conversions
    '''
    NCI_CSW = 'http://geonetworkrr2.nci.org.au/geonetwork/srv/eng/csw'
#    GA_CSW = 'http://www.ga.gov.au/geonetwork/srv/en/csw' # Old GeoCat CSW
#    GA_CSW = 'http://ecat.ga.gov.au/geonetwork/srv/eng/csw' # New externally-visible eCat CSW
#    GA_CSW = 'http://intranet.ga.gov.au/geonetwork/srv/eng/csw' # New internally-visible eCat CSW
    GA_CSW = 'http://localhost:8081/geonetwork/srv/eng/csw' # Port forwarded GA internal CSW
    FILE_EXTENSION = None # Unknown for base class
    DEFAULT_CHUNK_SIZE = 128 # Default chunk size for lat & lon dimensions
    EXCLUDED_EXTENSIONS = ['.bck', '.md5', '.uuid', '.json', '.tmp']
    
    METADATA_MAPPING = None # Needs to be defined in subclasses

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
        self._uuid = None # File identifier - must be unique to dataset
        self._metadata_dict = {}
        
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
            logger.warning('WARNING: Output NetCDF file %s already exists.', self._output_path)
            if os.path.exists(self._output_path + '.bck'):
                logger.warning('WARNING: Keeping existing backup file %s.bck', self._output_path)
            else:
                logger.warning('WARNING: Backing up existing NetCDF file to %s.bck', self._output_path)
                mv_command = ['mv', 
                                self._output_path,
                                self._output_path + '.bck'
                                ]
                logger.debug('mv_command = %s', mv_command)
                subprocess.check_call(mv_command)
            
        self._input_dataset = None
        self._netcdf_dataset = None
        self._metadata_dict = {}
    
    def read_iso_datetime_string(self, iso_datetime_string):
        '''
        Helper function to convert an ISO datetime string into a Python datetime object
        '''
        if not iso_datetime_string:
            return None

        try:
            iso_datetime = dateutil.parser.parse(iso_datetime_string)
        except ValueError, e:
            logger.warning('WARNING: Unable to parse "%s" into ISO datetime (%s)', iso_datetime_string, e.message)
            iso_datetime = None
            
        return iso_datetime
    
    def get_iso_utcnow(self, utc_datetime=None):
        '''
        Helper function to return an ISO string representing a UTC date/time. Defaults to current datetime.
        '''
        return (utc_datetime or datetime.utcnow()).replace(tzinfo=tz.gettz('UTC')).isoformat()
    
    def get_utc_mtime(self, file_path):
        '''
        Helper function to return the UTC modification time for a specified file
        '''
        assert file_path and os.path.exists(file_path), 'Invalid file path "%s"' % file_path
        return datetime.fromtimestamp(os.path.getmtime(file_path), pytz.utc)

    def gdal_translate(self, input_path, output_path, chunk_size=None):
        '''
        Function to use gdal_translate to perform initial format translation (format specific)
        '''
        chunk_size = chunk_size or Geophys2NetCDF.DEFAULT_CHUNK_SIZE
        temp_path = os.path.join(tempfile.gettempdir(), os.path.basename(output_path))
        gdal_command = ['gdal_translate', 
                        '-of', 'netCDF',
                        '-co', 'FORMAT=NC4C', 
                        '-co', 'COMPRESS=DEFLATE', 
                        '-co', 'WRITE_BOTTOMUP=YES', 
                        input_path, 
                        temp_path
                        ]
        
        logger.debug('gdal_command = %s', ' '.join(gdal_command))
        
        try:
            logger.info('Translating %s to temporary, un-chunked NetCDF file %s', input_path, temp_path)
            subprocess.check_call(gdal_command)
            
            logger.info('Translating temporary file %s to chunked NetCDF file %s', temp_path, output_path)
            subprocess.check_call(['nccopy', '-u', '-d', '2', '-c', 'lat/%d,lon/%d' % (chunk_size, chunk_size), temp_path,  output_path])
        finally:
            if not self._debug:
                os.remove(temp_path)
                logger.debug('Removed temporary, un-chunked NetCDF file %s', temp_path)
         
    def update_nc_metadata(self, output_path=None):
        '''
        Function to import all available metadata and set attributes in NetCDF file.
        Should be overridden in subclasses for each specific format but called first to perform initialisations
        '''
        assert output_path or self._output_path, 'Output NetCDF path not defined'
        
        if output_path: # New output path specified for nc metadata update
            assert os.path.exists(output_path), 'NetCDF file %s does not exist.' % output_path
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
            logger.debug('Read GDAL metadata from %s', self._input_path)
        else:
            logger.debug('No GDAL-compatible input dataset defined.')
        
        if self._netcdf_dataset:
            self._metadata_dict['NetCDF'] = NetCDFMetadata(self._netcdf_dataset).metadata_dict # Read generic GDAL metadata (if any)
            logger.debug('Read NetCDF metadata from %s', self._output_path)
        else:
            logger.debug('No NetCDF-compatible output dataset defined.')
        
    def get_metadata(self, metadata_path, default_namespace='gmd:'):
        '''
        Function to read metadata from nested dict self._metadata_dict.
        Returns None if atrribute does not exist
        Argument:
            metadata_path: Period-delineated path to required metadata element
            default_namespace: string defining possible default namespace prefix - needed for early versions of pyproj
        '''

        focus_element = self._metadata_dict
        subkey_list = metadata_path.split('/')
        for subkey in subkey_list:
            focus_element = focus_element.get(subkey) or focus_element.get(default_namespace + subkey)
            if focus_element is None: # Atrribute not found
                break
            
        return focus_element
        
    
    def set_netcdf_metadata_attributes(self): 
        '''
        Function to set all NetCDF metadata attributes using self.METADATA_MAPPING to map from NetCDF attribute name to 
        '''
        assert self.METADATA_MAPPING, 'No metadata mapping defined'
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
        attribute_dict['geospatial_lon_units'] = self._netcdf_dataset.variables['lon'].units
        attribute_dict['geospatial_lat_units'] = self._netcdf_dataset.variables['lat'].units
        attribute_dict['geospatial_bounds'] = 'POLYGON((%s %s, %s %s, %s %s, %s %s, %s %s))' % (min_lon, min_lat,
                                                                                                max_lon, min_lat,
                                                                                                max_lon, max_lat,
                                                                                                min_lon, max_lat,
                                                                                                min_lon, min_lat
                                                                                                )
        attribute_dict['geospatial_bounds_crs'] = crs.spatial_ref

        for key, value in attribute_dict.items():
            setattr(self._netcdf_dataset, key, value)

        # Set attributes defined in self.METADATA_MAPPING
        # Scan list in reverse to give priority to earlier entries
        for key, metadata_path in reversed(self.METADATA_MAPPING):
            value = self.get_metadata(metadata_path)
            if value is not None:
                logger.debug('Setting %s to %s', key, value)
                setattr(self._netcdf_dataset, key, value) #TODO: Check whether hierarchical metadata required
            else:
                logger.warning('WARNING: Metadata path %s not found', metadata_path)
                
        # Ensure only one DOI is stored - could be multiple, comma-separated entries
        if hasattr(self._netcdf_dataset, 'doi'):
            url_list = [url.strip() for url in self._netcdf_dataset.doi.split(',')]
            doi_list = [url for url in url_list if url.startswith('http://dx.doi.org/')]
            if len(url_list) > 1: # If more than one URL in list
                try: # Give preference to proper DOI URL
                    url = doi_list[0] # Use first (preferably only) DOI URL
                except:
                    url = url_list[0] # Just use first URL if no DOI found
                url = url.replace('&amp;', '&')                
                self._netcdf_dataset.doi = url
        
        # Set metadata_link to NCI metadata URL
        self._netcdf_dataset.metadata_link = 'https://pid.nci.org.au/dataset/%s' % self.uuid
        
        self._netcdf_dataset.Conventions = 'CF-1.6,ACDD-1.3'
        
        # Remove old fields - remove this later
        if hasattr(self._netcdf_dataset, 'id'):
            del self._netcdf_dataset.id
        if hasattr(self._netcdf_dataset, 'ga_uuid'):
            del self._netcdf_dataset.ga_uuid
        if hasattr(self._netcdf_dataset, 'keywords_vocabulary'):
            del self._netcdf_dataset.keywords_vocabulary

    def read_csv(self, csv_path):
        assert os.path.exists(csv_path), 'CSV file %s does not exist' % csv_path
        csv_file = open(csv_path)
        keys = None
        record_list = []
        for line in csv_file:
            if not keys:
                keys = [header.strip() for header in line.split(',')]
            else:
                record_list.append(dict(zip(keys, [value.strip() for value in line.split(',')])))
        return record_list        
            

    def get_uuid(self, title=None):
        '''
        Function to return UUID from csv file from file basename
        Sample UUID: 221dcfd8-03d7-5083-e053-10a3070a64e3
        '''
        self._uuid = None
        
        def get_uuid_from_netcdf():
            '''
            Function to return UUID from csv file from file basename
            Sample UUID: 221dcfd8-03d7-5083-e053-10a3070a64e3
            '''
            uuid = None
            try: # Try to use existing "identifier" attribute in NetCDF file
                uuid = self._netcdf_dataset.identifier
                logger.debug('Read UUID %s from NetCDF file', uuid)
            except:
                logger.debug('Unable to read UUID from NetCDF file')
                
            return uuid
            
        def get_uuid_from_json(json_path=None):
            '''
            Function to return UUID from JSON file
            Sample UUID: 221dcfd8-03d7-5083-e053-10a3070a64e3
            '''
            json_path = json_path or os.path.join(os.path.dirname(self._output_path), '.metadata.json')
            uuid = None
            
            try:
                json_file = open(json_path, 'r')
                uuid = json.load(json_file)['uuid']
                json_file.close()
            except:
                logger.debug('Unable to read UUID from JSON file %s', json_path)
                
            return uuid
            
        def get_uuid_from_csv(csv_path, file_path):
            '''
            Function to return UUID from csv file from file basename
            Sample UUID: 221dcfd8-03d7-5083-e053-10a3070a64e3
            '''
            uuid = None
            basename = os.path.splitext(os.path.basename(file_path))[0]
            
            try:
                record_list = self.read_csv(csv_path)
                uuid_list = [record['UUID'] for record in record_list if os.path.splitext(os.path.basename(record['PATHNAME']))[0] == basename]
                if len(uuid_list) == 1:
                    uuid = uuid_list[0].lower()
                    if len(uuid) == 32: # hyphens missing
                        uuid = '-'.join([uuid[uuid_section[0]: uuid_section[1]] for uuid_section in [(0, 8), (8, 12), (12, 16), (16, 20), (20, 32)]])
                    logger.info('UUID %s found from CSV file', uuid)
                    return uuid
            except:
                logger.debug('Unable to read unique UUID for %s from CSV file', basename, csv_path)
    
            return uuid
            
        def get_uuid_from_title(csw_url, title):
            '''
            Function to return OWSLib CSW record record from specified CSW URL using title as the search criterion
            Sample UUID: 221dcfd8-03d7-5083-e053-10a3070a64e3
            '''
            MAXRECORDS = 200
    
            uuid = None
            csw = CatalogueServiceWeb(csw_url)
            assert csw.identification.type == 'CSW', '%s is not a valid CSW service' % csw_url  
            
            search_title = title.replace('_', '%')
            while search_title and len(title)-len(search_title) < 10 and not uuid:
                title_query = PropertyIsEqualTo('csw:Title', '%' + search_title + '%')
                csw.getrecords2(constraints=[title_query], esn='summary', maxrecords=MAXRECORDS)
                
                if not csw.records: # No records found
                    search_title = search_title[0:-1] # Broaden search by shortening title
                else:
                    uuid_list = []
                    alphanumeric_title = re.sub('\W', '', title) # Strip all non-alphanumeric characters from title
                    while not uuid_list:
                        uuid_list = [identifier for identifier in csw.records.keys() if alphanumeric_title in re.sub('\W', '', csw.records[identifier].title)]
                        if len(uuid_list) == 1: # Unique match found
                            uuid = uuid_list[0]
                            logger.info('UUID %s found from title characters', uuid)
                            break
                        else:
                            alphanumeric_title = alphanumeric_title[0:-1] # Broaden search by shortening munged_title
            
            return uuid
    
        self._uuid = (
                      get_uuid_from_json(os.path.join(os.path.dirname(self._output_path), '.metadata.json')) or
                      get_uuid_from_netcdf()
                      )
                                         
        if not self._uuid and self._output_path:
            get_uuid_from_csv(os.path.join(self._code_root, 'uuid.csv'), self._output_path)
            
        if not self._uuid and self._input_path:
            get_uuid_from_csv(os.path.join(self._code_root, 'uuid.csv'), self._input_path)

        #May need to look up uuid from NCI - GA's GeoNetwork 2.6 does not support wildcard queries
        #TODO: Remove this hack when GA's CSW is updated to v3.X or greater
        if not self._uuid and title:
            get_uuid_from_title(Geophys2NetCDF.NCI_CSW, title)
            
        assert self._uuid, 'Unable to determine unique UUID for %s' % self.output_path
        logger.debug('self._uuid = %s', self._uuid)
        return self._uuid

    def get_csw_record_by_id(self, csw_url, identifier):
        '''
        Function to return OWSLib CSW record record from specified CSW URL using UUID as the search criterion
        '''
        csw = CatalogueServiceWeb(csw_url)
        assert csw.identification.type == 'CSW', '%s is not a valid CSW service' % csw_url   
        
        csw.getrecordbyid(id=[identifier], esn='full', outputschema='own')
        
        # Ensure there is exactly one record found
        assert len(csw.records) > 0, 'No CSW records found for ID "%s"' % identifier
        assert len(csw.records) == 1, 'Multiple CSW records found for ID "%s"' % identifier
        
        return csw.records.values()[0]
    
    def get_csw_xml_by_id(self, csw_url, identifier):
        #url = '%s?outputFormat=application%%2Fxml&service=CSW&outputSchema=own&request=GetRecordById&version=2.0.2&elementsetname=full&id=%s' % (csw_url, identifier)
        #return urllib.urlopen(url).read()
        xml_url = re.sub('/csw$', '/xml.metadata.get?uuid=%s' % identifier, csw_url)
        logger.debug('URL = %s', xml_url)
        return urllib.urlopen(xml_url).read()


    def get_metadata_dict_from_xml(self, xml_string):
        '''
        Function to parse an XML string into a nested dict
        '''
        assert xml_string, 'No XML metadata string provided'
        xml_metadata = XMLMetadata()
        xml_metadata.read_string(xml_string)
        return xml_metadata.metadata_dict
    
        
    def write_json_metadata(self, dataset_folder=None): 
        '''
        Function to write UUID, file_paths and current timestamp to .metadata.json
        '''
        assert self._uuid, 'UUID not set'
        
        dataset_folder = dataset_folder or os.path.dirname(self._output_path)
        assert dataset_folder, 'dataset_folder not defined.'
        dataset_folder = os.path.abspath(dataset_folder)
        
        json_output_path = os.path.join(dataset_folder, '.metadata.json')
        
        file_list = [file_path for file_path in glob(os.path.join(dataset_folder, '*')) 
                     if os.path.splitext(file_path)[1] not in Geophys2NetCDF.EXCLUDED_EXTENSIONS
                     and os.path.isfile(file_path)]
        
        md5_output = subprocess.check_output(['md5sum'] + file_list)
        md5_dict = {re.search('^(\w+)\s+(.+)$', line).groups()[1]: 
                    re.search('^(\w+)\s+(.+)$', line).groups()[0] 
                    for line in md5_output.split('\n') if line.strip()
                    }
        
        metadata_dict = {'uuid': self._uuid,
                         'time': self.get_iso_utcnow(),
                         'folder_path': dataset_folder,
                         'files': [{'file': os.path.basename(filename),
                                    'md5': md5_dict[filename],
                                    'mtime': self.get_utc_mtime(filename).isoformat()
                                    }
                                    for filename in sorted(md5_dict.keys())
                                   ]
                         }
        
        json_output_file = open(json_output_path, 'w')
        json.dump(metadata_dict, json_output_file, indent=4)
        json_output_file.close()
        logger.info('Finished writing metadata file %s', json_output_path)
        
    def check_json_metadata(self, output_path=None): 
        '''
        Function to check UUID, file_paths MD5 checksums from .metadata.json
        '''
        output_path = output_path or self._output_path
        assert output_path, 'No output path defined'
        
        dataset_folder = os.path.dirname(output_path)
        
        report_list = []
        
        dataset_folder = dataset_folder or os.path.dirname(self._output_path)
        assert dataset_folder, 'dataset_folder not defined.'
        dataset_folder = os.path.abspath(dataset_folder)
        
        json_metadata_path = os.path.join(dataset_folder, '.metadata.json')
        json_metadata_file = open(json_metadata_path, 'r')
        metadata_dict = json.load(json_metadata_file)
        json_metadata_file.close()
        
        if metadata_dict['folder_path'] != dataset_folder:
            report_list.append('Dataset folder Changed from %s to %s'% (metadata_dict['folder_path'], dataset_folder))
        
        file_list = [file_path for file_path in glob(os.path.join(dataset_folder, '*')) 
                     if os.path.splitext(file_path)[1] not in Geophys2NetCDF.EXCLUDED_EXTENSIONS
                     and os.path.isfile(file_path)]
        
        md5_output = subprocess.check_output(['md5sum'] + file_list)
        calculated_md5_dict = {os.path.basename(re.search('^(\w+)\s+(.+)$', line).groups()[1]): 
                               re.search('^(\w+)\s+(.+)$', line).groups()[0] 
                               for line in md5_output.split('\n') if line.strip()
                               }
        
        saved_md5_dict = {file_dict['file']:
                         file_dict['md5']
                         for file_dict in metadata_dict['files']
                         }
        
        for saved_filename, saved_md5sum in saved_md5_dict.items():
            calculated_md5sum = calculated_md5_dict.get(saved_filename) 
            if not calculated_md5sum:
                new_filenames = [new_filename for new_filename, new_md5sum in calculated_md5_dict.items() if new_md5sum == saved_md5sum]
                if new_filenames: 
                    report_list.append('File %s has been renamed to %s' % (saved_filename, new_filenames[0]))
                else:
                    report_list.append('File %s does not exist' % saved_filename)
            else: 
                if saved_md5sum != calculated_md5sum:
                    report_list.append('MD5 Checksum for file %s has changed from %s to %s' % (saved_filename, saved_md5sum, calculated_md5sum))
            
        if report_list:
            raise Exception('\n'.join(report_list))
        else:
            logger.info('File paths and checksums verified OK in %s', dataset_folder)
    
        
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
    def uuid(self):
        return self._uuid
    
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

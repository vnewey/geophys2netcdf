#!/usr/bin/env python

#=========================================================================
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
#=========================================================================
'''
Geophys2NetCDF Class
Created on 29/02/2016

@author: Alex Ip
'''
import os
import re
#from collections import OrderedDict
import logging
import subprocess
#from osgeo import gdal, osr
from osgeo.osr import SpatialReference, CoordinateTransformation
import numpy as np
import netCDF4
from owslib.csw import CatalogueServiceWeb
from owslib.fes import PropertyIsEqualTo  # , PropertyIsLike, BBox
import tempfile
from pprint import pprint

import json
import urllib

from geophys2netcdf.metadata import XMLMetadata, NetCDFMetadata
from geophys_utils import netcdf2convex_hull
from geophys_utils import DataStats
from geophys2netcdf.metadata_json import write_json_metadata, check_json_metadata

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Initial logging level for this module


class Geophys2NetCDF(object):
    '''
    Class definition for Geophys2NETCDF
    Base class for geophysics conversions
    '''
    NCI_CSW = 'http://geonetworkrr2.nci.org.au/geonetwork/srv/eng/csw'
#    GA_CSW = 'http://www.ga.gov.au/geonetwork/srv/en/csw' # Old GeoCat CSW
#    GA_CSW = 'http://ecat.ga.gov.au/geonetwork/srv/eng/csw' # New externally-visible eCat CSW
# GA_CSW = 'http://intranet.ga.gov.au/geonetwork/srv/eng/csw' # New
# internally-visible eCat CSW
    # Port forwarded GA internal CSW
    GA_CSW = 'http://localhost:8081/geonetwork/srv/eng/csw'
    FILE_EXTENSION = None  # Unknown for base class
    DEFAULT_CHUNK_SIZE = 128  # Default chunk size for lat & lon dimensions
    EXCLUDED_EXTENSIONS = ['.bck', '.md5', '.uuid', '.json', '.tmp']
    DECIMAL_PLACES = 12 # Number of decimal places to which geometry values should be rounded

    METADATA_MAPPING = None  # Needs to be defined in subclasses

    def __init__(self, debug=False):
        '''
        '''
        self._debug = False
        self.debug = debug  # Set property
        self._code_root = os.path.abspath(os.path.dirname(
            __file__))  # Directory containing module code

        self._input_path = None
        self._output_path = None
        self._input_dataset = None  # GDAL Dataset for input
        self._netcdf_dataset = None  # NetCDF Dataset for output
        self._uuid = None  # File identifier - must be unique to dataset
        self._metadata_dict = {}

    def translate(self, input_path, output_path=None, force_overwrite=False):
        '''
        Virtual function - performs basic initialisation for file translations
        Should be overridden in subclasses for each specific format but called first to perform initialisations
        '''
        assert os.path.exists(
            input_path), 'Input file %s does not exist' % input_path
        self._input_path = os.path.abspath(input_path)

        # Default to outputting .nc file of same name in current dir
        self._output_path = os.path.abspath(
            output_path or os.path.splitext(os.path.basename(input_path))[0] + '.nc')
        if os.path.exists(self._output_path):
            logger.warning(
                'WARNING: Output NetCDF file %s already exists.', self._output_path)
            if force_overwrite:
                if os.path.exists(self._output_path + '.bck'):
                    logger.warning(
                        'WARNING: Keeping existing backup file %s.bck', self._output_path)
                    logger.warning(
                         'WARNING: Removing existing NetCDF file %s', self._output_path)
                    rm_command = ['rm',
                                  self._output_path
                                  ]
                    logger.debug('rm_command = %s', rm_command)
                    subprocess.check_call(rm_command)
                else:
                    logger.warning(
                        'WARNING: Backing up existing NetCDF file to %s.bck', self._output_path)
                    mv_command = ['mv',
                                  self._output_path,
                                  self._output_path + '.bck'
                                  ]
                    logger.debug('mv_command = %s', mv_command)
                    subprocess.check_call(mv_command)
                
        self._input_dataset = None
        self._netcdf_dataset = None
        self._metadata_dict = {}

    def gdal_translate(self, input_path, output_path, chunk_size=None):
        '''
        Function to use gdal_translate to perform initial format translation (format specific)
        '''
        chunk_size = chunk_size or Geophys2NetCDF.DEFAULT_CHUNK_SIZE
        temp_path = os.path.join(
            tempfile.gettempdir(), os.path.basename(output_path))
        command = ['gdal_translate',
                   '-of', 'netCDF',
                   '-co', 'FORMAT=NC4C',
                   '-co', 'COMPRESS=DEFLATE',
                   '-co', 'WRITE_BOTTOMUP=NO', # N.B: This was previously YES, but GDAL doesn't like it
                   input_path,
                   temp_path
                   ]

        logger.debug('command = %s', ' '.join(command))

        logger.info(
            'Translating %s to temporary, un-chunked NetCDF file %s', input_path, temp_path)
        subprocess.check_call(command)

        arg_list = []
        temp_dataset = netCDF4.Dataset(temp_path, 'r')
        assert len(
            temp_dataset.dimensions) == 2, 'Dataset must have exactly two dimensions'
        for dimension in temp_dataset.dimensions.values():
            arg_list += [dimension.name, min(chunk_size, dimension.size)]
        temp_dataset.close()

        try:
            logger.info(
                'Translating temporary file %s to chunked NetCDF file %s', temp_path, output_path)
            command = ['nccopy', '-u', '-d', '2', '-c', '%s/%d,%s/%d' %
                       tuple(arg_list), temp_path, output_path]
            logger.debug('command = %s', ' '.join(command))
            subprocess.check_call(command)
            logger.info('Chunked NetCDF file %s created', output_path)
        finally:
            if not self._debug:
                os.remove(temp_path)
                logger.debug(
                    'Removed temporary, un-chunked NetCDF file %s', temp_path)

    def write_json_metadata(self):
        write_json_metadata(
            self._uuid,
            os.path.dirname(self._output_path),
            Geophys2NetCDF.EXCLUDED_EXTENSIONS)

    def check_json_metadata(self):
        check_json_metadata(
            self._uuid,
            os.path.dirname(self._output_path),
            Geophys2NetCDF.EXCLUDED_EXTENSIONS)

    def update_nc_metadata(self, output_path=None, do_stats=False, xml_path=None):
        '''
        Function to import all available metadata and set attributes in NetCDF file.
        Should be overridden in subclasses for each specific format but called first to perform initialisations
        '''
        output_path = output_path or self._output_path

        assert output_path, 'Output NetCDF path not defined'

        assert os.path.exists(
            output_path), 'NetCDF file %s does not exist.' % output_path
        self._output_path = output_path
        if self._netcdf_dataset:
            self._netcdf_dataset.close()
        try:
            self._netcdf_dataset = netCDF4.Dataset(
                self._output_path, mode='r+')
        except Exception as e:
            logger.error('Unable to open NetCDF file %s: %s',
                         (self._output_path, e.message))
            raise
        self.import_metadata(xml_path)

        assert self._metadata_dict, 'No metadata acquired'
        self.set_netcdf_metadata_attributes(do_stats=do_stats)

    def import_metadata(self, xml_path=None):
        '''
        Virtual function to read metadata from all available sources and set self._metadata_dict.
        Should be overridden for each specific format
        '''
        if self._input_dataset:
            # Read generic GDAL metadata (if any)
            self._metadata_dict[
                'GDAL'] = self._input_dataset.GetMetadata_Dict()
            logger.debug('Read GDAL metadata from %s', self._input_path)
        else:
            logger.debug('No GDAL-compatible input dataset defined.')

        if self._netcdf_dataset:
            self._metadata_dict['NetCDF'] = NetCDFMetadata(
                self._netcdf_dataset).metadata_dict  # Read generic GDAL metadata (if any)
            logger.debug('Read NetCDF metadata from %s', self._output_path)
        else:
            logger.debug('No NetCDF-compatible output dataset defined.')
            
    def dump_metadata(self):
        '''
        Function to print metadata dict
        '''
        #TODO: Need something better than just printing.
        # self.import_metadata()
        pprint(self._metadata_dict)

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
            focus_element = focus_element.get(
                subkey) or focus_element.get(default_namespace + subkey)
            if focus_element is None:  # Atrribute not found
                break

        return focus_element

    def set_netcdf_metadata_attributes(
            self, to_crs='EPSG:4326', do_stats=False):
        '''
        Function to set all NetCDF metadata attributes using self.METADATA_MAPPING to map from NetCDF ACDD global attribute name to metadata path (e.g. xpath)
        Parameter:
            to_crs: EPSG or WKT for spatial metadata
            do_stats: Boolean flag indicating whether minmax stats should be determined (slow)
        '''
        assert self.METADATA_MAPPING, 'No metadata mapping defined'
        assert self._netcdf_dataset, 'NetCDF output dataset not defined.'
#        assert self._metadata_dict, 'No metadata acquired'

        # Set geospatial attributes
        try:
            grid_mapping = [variable.grid_mapping for variable in self._netcdf_dataset.variables.values(
            ) if hasattr(variable, 'grid_mapping')][0]
        except:
            logger.error(
                'Unable to determine grid_mapping for spatial reference')
            raise

        crs = self._netcdf_dataset.variables[grid_mapping]

        spatial_ref = crs.spatial_ref
        geoTransform = [float(string)
                        for string in crs.GeoTransform.strip().split(' ')]
        xpixels, ypixels = (
            dimension.size for dimension in self._netcdf_dataset.dimensions.values())
        dimension_names = (
            dimension.name for dimension in self._netcdf_dataset.dimensions.values())

        # Create nested list of bounding box corner coordinates
        bbox_corners = [[geoTransform[0] + (x_pixel_offset * geoTransform[1]) + (y_pixel_offset * geoTransform[2]),
                         geoTransform[3] + (x_pixel_offset * geoTransform[4]) + (y_pixel_offset * geoTransform[5])]
                        for x_pixel_offset in [0, xpixels]
                        for y_pixel_offset in [0, ypixels]]

        if to_crs:  # Coordinate transformation required
            from_spatial_ref = SpatialReference()
            from_spatial_ref.ImportFromWkt(spatial_ref)

            to_spatial_ref = SpatialReference()
            # Check for EPSG then Well Known Text
            epsg_match = re.match('^EPSG:(\d+)$', to_crs)
            if epsg_match:
                to_spatial_ref.ImportFromEPSG(int(epsg_match.group(1)))
            else:  # Assume valid WKT definition
                to_spatial_ref.ImportFromWkt(to_crs)

            coord_trans = CoordinateTransformation(
                from_spatial_ref, to_spatial_ref)

            extents = np.array(
                [coord[0:2] for coord in coord_trans.TransformPoints(bbox_corners)])
            spatial_ref = to_spatial_ref.ExportToWkt()

            centre_pixel_coords = [coord[0:2] for coord in coord_trans.TransformPoints(
                [[geoTransform[0] + (x_pixel_offset * geoTransform[1]) + (y_pixel_offset * geoTransform[2]),
                  geoTransform[3] + (x_pixel_offset * geoTransform[4]) + (y_pixel_offset * geoTransform[5])]
                 for x_pixel_offset in [xpixels // 2, xpixels // 2 + 1]
                 for y_pixel_offset in [ypixels // 2, ypixels // 2 + 1]]
            )
            ]

            # Use Pythagoras to compute centre pixel size in new coordinates
            # (never mind the angles)
            yres = pow(pow(centre_pixel_coords[1][0] - centre_pixel_coords[0][0], 2) + pow(
                centre_pixel_coords[1][1] - centre_pixel_coords[0][1], 2), 0.5)
            xres = pow(pow(centre_pixel_coords[2][0] - centre_pixel_coords[0][0], 2) + pow(
                centre_pixel_coords[2][1] - centre_pixel_coords[0][1], 2), 0.5)

            # TODO: Make this more robust - could pull single unit from WKT
            if to_spatial_ref.IsGeographic():
                xunits, yunits = ('degrees_east', 'degrees_north')
            elif to_spatial_ref.IsProjected():
                xunits, yunits = ('m', 'm')
            else:
                xunits, yunits = ('unknown', 'unknown')

        else:  # Use native coordinates
            extents = np.array(bbox_corners)
            xres = round(geoTransform[1], Geophys2NetCDF.DECIMAL_PLACES)
            yres = round(geoTransform[5], Geophys2NetCDF.DECIMAL_PLACES)
            xunits, yunits = (self._netcdf_dataset.variables[
                              dimension_name].units for dimension_name in dimension_names)

        xmin = np.min(extents[:, 0])
        ymin = np.min(extents[:, 1])
        xmax = np.max(extents[:, 0])
        ymax = np.max(extents[:, 1])

        attribute_dict = dict(zip(['geospatial_lon_min', 'geospatial_lat_min', 'geospatial_lon_max', 'geospatial_lat_max'],
                                  [xmin, ymin, xmax, ymax]
                                  )
                              )
        attribute_dict['geospatial_lon_resolution'] = xres
        attribute_dict['geospatial_lat_resolution'] = yres
        attribute_dict['geospatial_lon_units'] = xunits
        attribute_dict['geospatial_lat_units'] = yunits

        try:
            convex_hull = [coordinate[0:2] for coordinate in coord_trans.TransformPoints(
                netcdf2convex_hull(self.netcdf_dataset, 2000000000))]  # Process dataset in pieces <= 2GB in size
        except:
            logger.info('Unable to compute convex hull. Using rectangular bounding box instead.')
            convex_hull = [coordinate[0:2] for coordinate in coord_trans.TransformPoints(bbox_corners + [bbox_corners[0]])]

        attribute_dict['geospatial_bounds'] = 'POLYGON((' + ', '.join([' '.join(
            ['%.4f' % ordinate for ordinate in coordinates]) for coordinates in convex_hull]) + '))'

        attribute_dict['geospatial_bounds_crs'] = spatial_ref

        for key, value in attribute_dict.items():
            setattr(self._netcdf_dataset, key, value)

        # Set attributes defined in self.METADATA_MAPPING
        # Scan list in reverse to give priority to earlier entries
        #TODO: Improve this coding - it's a bit crap
        keys_read = []
        for key, metadata_path in self.METADATA_MAPPING:
            # Skip any keys already read
            if key in keys_read:
                continue

            value = self.get_metadata(metadata_path)
            if value is not None:
                logger.debug('Setting %s to %s', key, value)
                # TODO: Check whether hierarchical metadata required
                setattr(self._netcdf_dataset, key, value)
                keys_read.append(key)
            else:
                logger.warning(
                    'WARNING: Metadata path %s not found', metadata_path)

        unread_keys = sorted(
            list(set([item[0] for item in self.METADATA_MAPPING]) - set(keys_read)))
        if unread_keys:
            logger.warning(
                'WARNING: No value found for metadata attribute(s) %s' % ', '.join(unread_keys))

        # Ensure only one DOI is stored - could be multiple, comma-separated
        # entries
        if hasattr(self._netcdf_dataset, 'doi'):
            url_list = [url.strip()
                        for url in self._netcdf_dataset.doi.split(',')]
            doi_list = [url for url in url_list if url.startswith(
                'http://dx.doi.org/')]
            if len(url_list) > 1:  # If more than one URL in list
                try:  # Give preference to proper DOI URL
                    url = doi_list[0]  # Use first (preferably only) DOI URL
                except:
                    url = url_list[0]  # Just use first URL if no DOI found
                url = url.replace('&amp;', '&')
                self._netcdf_dataset.doi = url

        # Set metadata_link to NCI metadata URL
        self._netcdf_dataset.metadata_link = 'https://pid.nci.org.au/dataset/%s' % self.uuid

        self._netcdf_dataset.Conventions = 'CF-1.6, ACDD-1.3'

        if do_stats:
            datastats = DataStats(netcdf_dataset=self.netcdf_dataset,
                                  netcdf_path=None, max_bytes=2000000000)  # 2GB pieces
            datastats.data_variable.actual_range = np.array(
                [datastats.value('min'), datastats.value('max')], dtype='float32')

        # Remove old fields - remove this later
        if hasattr(self._netcdf_dataset, 'id'):
            del self._netcdf_dataset.id
        if hasattr(self._netcdf_dataset, 'ga_uuid'):
            del self._netcdf_dataset.ga_uuid
        if hasattr(self._netcdf_dataset, 'keywords_vocabulary'):
            del self._netcdf_dataset.keywords_vocabulary

    def read_csv(self, csv_path):
        assert os.path.exists(
            csv_path), 'CSV file %s does not exist' % csv_path
        csv_file = open(csv_path)
        keys = None
        record_list = []
        for line in csv_file:
            if not keys:
                keys = [header.strip() for header in line.split(',')]
            else:
                record_list.append(
                    dict(zip(keys, [value.strip() for value in line.split(',')])))
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
            try:  # Try to use existing "identifier" attribute in NetCDF file
                uuid = self._netcdf_dataset.uuid
                logger.debug('Read UUID %s from NetCDF file', uuid)
            except:
                logger.debug('Unable to read UUID from NetCDF file')

            return uuid

        def get_uuid_from_json(json_path=None):
            '''
            Function to return UUID from JSON file
            Sample UUID: 221dcfd8-03d7-5083-e053-10a3070a64e3
            '''
            json_path = json_path or os.path.join(
                os.path.dirname(self._output_path), '.metadata.json')
            uuid = None

            try:
                json_file = open(json_path, 'r')
                uuid = json.load(json_file)['uuid']
                json_file.close()
            except:
                logger.debug(
                    'Unable to read UUID from JSON file %s', json_path)

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
                uuid_list = [record['UUID'] for record in record_list if os.path.splitext(
                    os.path.basename(record['PATHNAME']))[0] == basename]
                if len(uuid_list) == 1:
                    uuid = uuid_list[0].lower()
                    if len(uuid) == 32:  # hyphens missing
                        uuid = '-'.join([uuid[uuid_section[0]: uuid_section[1]]
                                         for uuid_section in [(0, 8), (8, 12), (12, 16), (16, 20), (20, 32)]])
                    logger.info('UUID %s found from CSV file', uuid)
                    return uuid
            except:
                logger.debug(
                    'Unable to read unique UUID for %s from CSV file', basename, csv_path)

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
            while search_title and len(
                    title) - len(search_title) < 10 and not uuid:
                title_query = PropertyIsEqualTo(
                    'csw:Title', '%' + search_title + '%')
                csw.getrecords2(
                    constraints=[title_query], esn='summary', maxrecords=MAXRECORDS)

                if not csw.records:  # No records found
                    # Broaden search by shortening title
                    search_title = search_title[0:-1]
                else:
                    uuid_list = []
                    # Strip all non-alphanumeric characters from title
                    alphanumeric_title = re.sub('\W', '', title)
                    while not uuid_list:
                        uuid_list = [identifier for identifier in csw.records.keys(
                        ) if alphanumeric_title in re.sub('\W', '', csw.records[identifier].title)]
                        if len(uuid_list) == 1:  # Unique match found
                            uuid = uuid_list[0]
                            logger.info(
                                'UUID %s found from title characters', uuid)
                            break
                        else:
                            # Broaden search by shortening munged_title
                            alphanumeric_title = alphanumeric_title[0:-1]

            return uuid

        self._uuid = (
            get_uuid_from_json(os.path.join(os.path.dirname(self._output_path), '.metadata.json')) or
            get_uuid_from_netcdf()
        )

        if not self._uuid and self._output_path:
            get_uuid_from_csv(os.path.join(
                self._code_root, 'uuid.csv'), self._output_path)

        if not self._uuid and self._input_path:
            get_uuid_from_csv(os.path.join(
                self._code_root, 'uuid.csv'), self._input_path)

        # May need to look up uuid from NCI - GA's GeoNetwork 2.6 does not support wildcard queries
        # TODO: Remove this hack when GA's CSW is updated to v3.X or greater
        if not self._uuid and title:
            get_uuid_from_title(Geophys2NetCDF.NCI_CSW, title)

        if not self._uuid:
            logger.warning('Unable to determine unique UUID for %s' % self._output_path)
            
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
        assert len(
            csw.records) > 0, 'No CSW records found for ID "%s"' % identifier
        assert len(
            csw.records) == 1, 'Multiple CSW records found for ID "%s"' % identifier

        return csw.records.values()[0]

    def get_csw_xml_by_id(self, csw_url, identifier):
        #url = '%s?outputFormat=application%%2Fxml&service=CSW&outputSchema=own&request=GetRecordById&version=2.0.2&elementsetname=full&id=%s' % (csw_url, identifier)
        # return urllib.urlopen(url).read()
        xml_url = re.sub('/csw$', '/xml.metadata.get?uuid=%s' %
                         identifier, csw_url)
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
    g2n.translate(
        'IR_gravity_anomaly_Australia_V1/IR_gravity_anomaly_Australia_V1.ers')

if __name__ == 'main':
    main()

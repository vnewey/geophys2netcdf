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
import threading
import traceback
import numpy as np
from datetime import datetime, date, timedelta
import pytz
import calendar
import collections
import numexpr
import logging
import cPickle
import itertools
import time
import netCDF4
from osgeo import osr
from osgeo import gdal
from pprint import pprint
from math import floor
from distutils.util import strtobool
from multiprocessing import Process, Lock, Pool, cpu_count
import SharedArray as sa


# Set handler for root logger to standard output
console_handler = logging.StreamHandler(sys.stdout)
#console_handler.setLevel(logging.INFO)
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)
logging.root.addHandler(console_handler)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Initial logging level for this module

from gdf._arguments import CommandLineArgs
from gdf._config_file import ConfigFile

class Geophys2NetCDF(object):
    '''
    Class definition for GDF (General Data Framework).
    Manages configuration and database connections.
    '''
    DEFAULT_CONFIG_FILE = 'geophys2netcdf.conf' # N.B: Assumed to reside in code root directory
    MAX_READ_SIZE = 2 * 1073741824 

    def read_ers_metadata(self, ers_path):
        '''
        Function to read metadata from specified.isi file into a nested dict
        
        .isi file will be formatted as follows:
            MetaData Begin
            Name    = IR_gravity_anomaly_Australia_V1.ers
            Version    = "Intrepid v4.3.0 default for SunOS (sparc) by lee optimised build 567b22b07dd7 (Free Version)"
            IR_gravity_anomaly_Australia_V1 Begin
                GroupBy    = no
                DataType    = IEEE4ByteReal
                ByteOrder    = MSBFirst
                Bands    = 1
                Minimum    =  -1286.08496094
                Maximum    =   1207.94592285
                Mean    =  -11.7970361617
                Variance    =   66055.0473974
                Samples    = 10039386
                Nulls    = 13869108
                Projection    = "GEODETIC"
                Datum    = "GDA94"
                BandId    = "IR_gravity_anomaly V1"
            IR_gravity_anomaly_Australia_V1 End
            Extensions Begin
                JetStream Begin
                    Theme    = "GRAVITY"
                    LABEL    = "Isostatic_Residual_Gravity_Anomaly_Grid_Geodetic_Version_1"
                    DATE    = "2011"
                    CELLSIZE    = "0.00833"
                    FLAVOUR    = "Unknown"
                    LINESPACING    = "Unknown"
                    Surveyid    = "4105"
                    CSDATA    = "GDA94"
                    LICENCENO    = "1"
                JetStream End
            Extensions End
        MetaData End
        
    .ers file format is as follows:
        DatasetHeader Begin
                LastUpdated     = Tue Feb 28 05:16:57 GMT 2012
                Version = "5.0"
                DataSetType     = ERStorage
                DataType        = Raster
                HeaderOffset    = 512
                CoordinateSpace Begin
                        Projection      = "GEODETIC"
                        CoordinateType  = LATLONG
                        Datum   = "GDA94"
                        Rotation        = 0:0:0
                CoordinateSpace End
                ByteOrder       = LSBFirst
                RasterInfo Begin
                        CellType        = IEEE4ByteReal
                        NrOfLines       = 4182
                        NrOfCellsPerLine        = 5717
                        NrOfBands       = 1
                        NullCellValue   = -99999.00000000
                        CellInfo Begin
                                Xdimension      =      0.00833333
                                Ydimension      =      0.00833333
                        CellInfo End
                        RegistrationCellX       = 0
                        RegistrationCellY       = 0
                        RegistrationCoord Begin
                                Longitude       = 109:6:0.843442298
                                Latitude        = -9:21:17.81304202
                        RegistrationCoord End
                        BandId Begin
                                Value   = "IR_gravity_anomaly V1"
                        BandId End
                RasterInfo End
        DatasetHeader End

    '''
        
        def read_part_ers_metadata(self, metadata_path):
            '''
            Function to read ERS metadata from .isi or .ers file into a nested dict
            '''
            metadata_dict = {}
            section_list = []
            section_dict = metadata_dict
            parent_dict = None
            isi_file = open(metadata_path, 'r')
        
            line = 'BEGIN ALL'
            for line in isi_file:
                line = line.strip()
                logger.debug('line = %s' % line)
                match = re.match('(\w+) Begin$', line)
                if match is not None:
                    section = match.groups()[0]
                    logger.debug('Begin section %s' % section)
                    section_list.append(section)
                    section_dict[section] = {}
                    parent_dict = section_dict
                    section_dict = section_dict[section]
                else:
                    match = re.match('(\w+) End$', line)
                    if match is not None:
                        end_section = match.groups()[0]
                        assert end_section == section, 'Unmatched section end: %s' % line
                        logger.debug('End section %s' % section)
                        del section_list[-1]
                        if section_list:
                            section = section_list[-1]
                        else:
                            section = ''
                        section_dict = parent_dict
                    else:
                        try:
                            key, value = [element.strip() for element in line.split('=')]
                            
                            # Change numeric types to either integer or float
                            try:
                                assert '.' not in value, 'Decimal point or period found'
                                value = int(value)
                            except:
                                try:
                                    value = float(value)
                                except:
                                    pass # Leave value as string
                                
                            logger.debug('key = %s, value = %s' % (key, value))
                            section_dict[key] = value
                        except:
                            pass # Ignore any line not of format "key = value"
            
            return metadata_dict
            # End of function read_part_ers_metadata
            
        full_metadata_dict = {}
        for extension in ['isi', 'ers']:
            metadata_path = os.path.splitext(ers_path)[0] + '.' + extension
            full_metadata_dict.update(read_part_ers_metadata(metadata_path))
            
        return full_metadata_dict

    def __init__(self, config=None, debug=False):
        '''
        '''
        self._debug = False
        self.debug = debug # Set property
        self._code_root = os.path.abspath(os.path.dirname(__file__)) # Directory containing module code
        self._config_path = config or os.path.join(self._code_root, Geophys2NetCDF.DEFAULT_CONFIG_FILE)
        
        # Create master configuration dict containing both command line and config_file parameters
        self._config_file_object = ConfigFile(self._config_path)  
    
    def translate_ers(self, input_dataset, netcdf_dataset): 
        input_path = input_dataset.GetFileList()[0]
          
        metadata_dict = self.read_isi(os.path.splitext(input_path)[0] + '.isi')

        for band_index in input_dataset.RasterCount:
            pass 

    def translate(self, input_path, output_path=None):
        
        if not output_path:
            output_path = os.path.splitext(input_path)[0] + '.nc'
                 
        input_dataset = gdal.Open(input_path)
        assert input_dataset, 'Unable to open input file %s' % input_path
        
        input_driver_name = input_dataset.GetDriver().GetDescription()
        
        netcdf_dataset = netcdf_dataset = netCDF4.Dataset(output_path, mode='w', format='NETCDF4_CLASSIC')
        
        if input_driver_name == 'ERS':
            self.translate_ers(input_dataset, netcdf_dataset)
            
        elif input_driver_name == 'GeoTIFF':
#            metadata_dict = input_dataset.GetMetadata_Dict()
            pass
        else:
            raise Exception('Unhandled input file type: %s' % input_driver_name)
                

    
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

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
import subprocess
import gc
from osgeo import osr
from osgeo import gdal
from pprint import pprint
from math import floor
from distutils.util import strtobool
from multiprocessing import Process, Lock, Pool, cpu_count
from owslib.csw import CatalogueServiceWeb
from owslib.fes import PropertyIsEqualTo, PropertyIsLike, BBox

from _geophys2netdcf import Geophys2NetCDF
from metadata import ERSMetadata, XMLMetadata

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

class ERS2NetCDF(Geophys2NetCDF):
    '''
    '''
    NCI_CSW = 'http://geonetworkrr2.nci.org.au/geonetwork/srv/eng/csw'
    GA_CSW = 'http://www.ga.gov.au/geonetwork/srv/en/csw'
    
    def gdal_translate(self, input_path, output_path):
        '''
        '''
        #=======================================================================
        # input_shape = (input_dataset.RasterYSize, input_dataset.RasterXSize) #TODO: Check whether YX array ordering is a general thing
        # 
        # for band_index in range(input_dataset.RasterCount):
        #     band = input_dataset.GetRasterBand(band_index + 1)
        #     input_blocksize = band.GetBlockSize() # XY order
        #     input_blocksize.reverse() # YX order - same as array shape
        #     
        #     block_counts = [(input_shape[index] - 1) // input_blocksize[index] + 1 for index in range(2)]
        #=======================================================================
            
        gdal_command = ['gdal_translate', 
                        '-of', 'netCDF',
                        '-co', 'FORMAT=NC4C', 
                        '-co', 'COMPRESS=DEFLATE', 
                        '-co', 'WRITE_BOTTOMUP=YES', 
                        input_path, 
                        output_path
                        ]
        
        logger.debug('gdal_command = %s', gdal_command)
        
        subprocess.check_call(gdal_command)
         
    def get_csw_uuid_from_title(self, csw_url, title):
        csw = CatalogueServiceWeb(csw_url)
        assert csw.identification.type == 'CSW', '%s is not a valid CSW service' % csw_url  
        
        title_query = PropertyIsEqualTo('csw:Title', title.replace('_', '%'))
        csw.getrecords2(constraints=[title_query], maxrecords=2)
        
        # Ensure there is exactly one ID found
        assert len(csw.records) > 0, 'No CSW records found for title "%s"' % title
        assert len(csw.records) == 1, 'Multiple CSW records found for title "%s"' % title
        
        return csw.results[csw.results.keys()[0]]['identifier']
    
    def get_csw_record_by_id(self, csw_url, identifier):
        csw = CatalogueServiceWeb(csw_url)
        assert csw.identification.type == 'CSW', '%s is not a valid CSW service' % csw_url   
        
        #csw.getrecordbyid(id=['221dcfd8-03d7-5083-e053-10a3070a64e3']) # This doesn't work for some reason
        id_query = PropertyIsEqualTo('csw:Identifier', '221dcfd8-03d7-5083-e053-10a3070a64e3')
        csw.getrecords2(constraints=[id_query], esn='full', maxrecords=2)
        
        # Ensure there is exactly one ID found
        assert len(csw.records) > 0, 'No CSW records found for ID "%s"' % identifier
        assert len(csw.records) == 1, 'Multiple CSW records found for ID "%s"' % identifier
        
        return csw.results[csw.results.keys()[0]]


    def get_xml_metadata_dict_from_record(self, csw_record):
        xml_metadata = XMLMetadata()
        xml_metadata.read_string(csw_record.xml)
        return xml_metadata.metadata_dict
        
        
    def translate(self, input_path, output_path=None):
        '''
        Function overriding Geophys2NetCDF.translate to perform ERS format-specific translation
        '''
        Geophys2NetCDF.translate(self, input_path, output_path) # Perform initialisations
        
        self.gdal_translate(self._input_path, self._output_path)
        
        self._input_dataset = gdal.Open(self._input_path)
        assert self._input_dataset, 'Unable to open input file %s' % self._input_path
         
        self._input_driver_name = self._input_dataset.GetDriver().GetDescription()
        assert self._input_driver_name == 'ERS', 'Input file is not of type ERS'
         
        self._netcdf_dataset = netCDF4.Dataset(self._output_path, mode='w')
        
        self._metadata_dict['GDAL'] = self._input_dataset.GetMetadata_Dict() # Read generic GDAL metadata (if any)
        
        # Read data from both .ers and .isi files into separate  metadata subtrees
        for extension in ['isi', 'ers']:
            self._metadata_dict[extension.upper()] = ERSMetadata(os.path.splitext(input_path)[0] + '.' + extension).metadata_dict       
                
        logger.debug('self._metadata_dict = ', self._metadata_dict)
        
        # Need to look up uuid from NCI - GA's GeoNetwork 2.6 does not support wildcard queries
        uuid = self.get_csw_uuid_from_title(ERS2NetCDF.NCI_CSW, self._metadata_dict['ISI']['MetaData']['Extensions']['JetStream']['LABEL'])
        logger.debug('uuid = ', uuid)

        csw_record = self.get_csw_record_by_id(ERS2NetCDF.GA_CSW, uuid)
        logger.debug('csw_record = ', csw_record)
        
        self._metadata_dict['CSW'] = self.get_xml_metadata_dict_from_record(csw_record)
        
        logger.debug('self._metadata_dict = ', self._metadata_dict)
        


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
import netCDF4
import subprocess
from osgeo import gdal
from datetime import datetime
from dateutil import tz
from glob import glob

from geophys2netcdf._geophys2netcdf import Geophys2NetCDF
from metadata import ERSMetadata

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Initial logging level for this module

class ERS2NetCDF(Geophys2NetCDF):
    '''
    Class definition for ERS2NetCDF to handle ERS gridded datasets 
    '''
    FILE_EXTENSION = 'ers'
    METADATA_MAPPING = [ # ('netcdf_attribute', 'metadata.key'),
                        ('identifier', 'GA_CSW.MD_Metadata.fileIdentifier.gco:CharacterString'),
                        ('title', 'GA_CSW.MD_Metadata.identificationInfo.MD_DataIdentification.citation.CI_Citation.title.gco:CharacterString'),
                        ('source', 'GA_CSW.MD_Metadata.dataQualityInfo.DQ_DataQuality.scope.DQ_Scope.level.MD_ScopeCode.codeListValue'),
                        ('summary', 'GA_CSW.MD_Metadata.identificationInfo.MD_DataIdentification.abstract.gco:CharacterString'),
#                        ('product_version', ''), # Can't set this - assume value of "1.0" instead
                        ('date_created', 'GA_CSW.MD_Metadata.identificationInfo.MD_DataIdentification.citation.CI_Citation.date.CI_Date.date.gco:Date'),
#                        ('date_modified', 'ERS.DatasetHeader.LastUpdated'), # Use ISO format
                        ('metadata_link', 'GA_CSW.MD_Metadata.distributionInfo.MD_Distribution.transferOptions.MD_DigitalTransferOptions.onLine.CI_OnlineResource.linkage.URL'), # Only DOI used
                        ('history', 'GA_CSW.MD_Metadata.dataQualityInfo.DQ_DataQuality.lineage.LI_Lineage.statement.gco:CharacterString'),
                        ('institution', 'GA_CSW.MD_Metadata.contact.CI_ResponsibleParty.organisationName.gco:CharacterString'),
                        ('keywords', 'GA_CSW.MD_Metadata.identificationInfo.MD_DataIdentification.descriptiveKeywords.MD_Keywords.keyword.gco:CharacterString'),
                        ('keywords_vocabulary', 'GA_CSW.MD_Metadata.identificationInfo.MD_DataIdentification.descriptiveKeywords.MD_Keywords.thesaurusName.CI_Citation.title.gco:CharacterString'),
                        ('license', 'GA_CSW.MD_Metadata.identificationInfo.MD_DataIdentification.resourceConstraints.MD_LegalConstraints.otherConstraints.gco:CharacterString'),
                        ]
    
    def read_ers_datetime_string(self, ers_datetime_string):
        '''
        Helper function to convert an ERS datetime string into a Python datetime object
        e.g: 'Tue Feb 28 05:16:57 GMT 2012'
        '''
        if not ers_datetime_string:
            return None

        try:
            ers_datetime = datetime.strptime(ers_datetime_string, '%a %b %d %H:%M:%S %Z %Y')
            #TODO: Find out why %Z is not parsed to a timezone and remove the following hack
            ers_datetime = ers_datetime.replace(tzinfo=tz.gettz(ers_datetime_string.split(' ')[4])) # This should always work if strptime didn't fail
        except ValueError, e:
            logger.warning('WARNING: Unable to parse "%s" into ERS datetime (%s)', ers_datetime_string, e.message)
            ers_datetime = None
            
        return ers_datetime
    
    def __init__(self, input_path=None, output_path=None, debug=False):
        '''
        Constructor for class ERS2NetCDF
        '''
        Geophys2NetCDF.__init__(self, debug) # Call inherited constructor
        self._metadata_mapping_dict = OrderedDict(ERS2NetCDF.METADATA_MAPPING)

        if input_path:
            self.translate(input_path, output_path)
    
    def translate(self, input_path, output_path=None):
        '''
        Function to perform ERS format-specific translation and set self._input_dataset and self._netcdf_dataset
        Overrides Geophys2NetCDF.translate()
        '''
        Geophys2NetCDF.translate(self, input_path, output_path) # Perform initialisations using base class method
        
        self.gdal_translate(self._input_path, self._output_path) # Use gdal_translate to create basic NetCDF
        
        self._input_dataset = gdal.Open(self._input_path)
        assert self._input_dataset, 'Unable to open input file %s' % self._input_path
         
        self._input_driver_name = self._input_dataset.GetDriver().GetDescription()
        assert self._input_driver_name == 'ERS', 'Input file is not of type ERS'
        
        self._netcdf_dataset = netCDF4.Dataset(self._output_path, mode='r+')
        
        self.import_metadata()

        # Perform format-specific modifications to gdal_translate generated NetCDF dataset
        band_name = (self.get_metadata('ERS.DatasetHeader.RasterInfo.BandId.Value') or
                     self.get_metadata('GA_CSW.MD_Metadata.identificationInfo.MD_DataIdentification.citation.CI_Citation.title.gco:CharacterString'))
            
        variable = self._netcdf_dataset.variables['Band1']
        variable.long_name = band_name
        self._netcdf_dataset.renameVariable('Band1', re.sub('\W', '_', band_name[0:16])) #TODO: Do something more elegant than string truncation for short name

        self._netcdf_dataset.Conventions = self._netcdf_dataset.Conventions + ', ACDD-1.3'
        self.update_nc_metadata() # Will close output file for writing and write checksum and uuid files
        logger.info('Finished translating %s to %s', self._input_path, self._output_path)

    def update_nc_metadata(self, output_path=None):
        '''
        Function to import all available metadata and set attributes in NetCDF file.
        Overrides Geophys2NetCDF.update_nc_metadata
        '''
        Geophys2NetCDF.update_nc_metadata(self, output_path) # Call inherited method
        
        self._netcdf_dataset.sync()

        # Look for date_modified value in source file then in NetCDF file
        date_modified = (self.read_ers_datetime_string(self.get_metadata('ERS.DatasetHeader.LastUpdated')) or
                         (self.read_iso_datetime_string(self._netcdf_dataset.date_modified) if hasattr(self._netcdf_dataset, 'date_modified') else None))

        if date_modified:
            self._netcdf_dataset.date_modified = date_modified.isoformat()
            
            if not hasattr(self._netcdf_dataset, 'product_version'):
                self._netcdf_dataset.product_version = date_modified.isoformat()
        else:
            logger.warning('WARNING: Unable to determine date_modified attribute')
            if not hasattr(self._netcdf_dataset, 'product_version'):
                self._netcdf_dataset.product_version = '1.0' # Set required attribute
            
        # Put something sensible in history attribute
        if self._input_path:
            history_string = '%s Translated from %s using %s' % (self.get_iso_utcnow(), os.path.basename(self._input_path), __name__ + '.py')
            if hasattr(self._netcdf_dataset, 'history') and self._netcdf_dataset.history and (self._netcdf_dataset.history.lower() != 'unknown'):
                history_string = self._netcdf_dataset.history + '\n' + history_string

            self._netcdf_dataset.history = history_string
            
        logger.info('Finished writing output file %s', self._output_path)
        
        # Close and reopen NetCDF file as read-only
        self._netcdf_dataset.sync()
        self._netcdf_dataset.close()
        self._netcdf_dataset = netCDF4.Dataset(self._output_path, mode='r')
        logger.debug('NetCDF file %s reopened as read-only', self._output_path)
        
        self.write_json_metadata()

        # Set permissions to group writeable, world readable - ignore errors
        chmod_command = ['chmod', '-R', 'g+rwX,o+rX', os.path.dirname(self._output_path)]
        logger.debug('gdal_command = %s', chmod_command)
        if subprocess.call(chmod_command):
            logger.warning('WARNING: Command "%s" returned non-zero status.', ' '.join(chmod_command))
            
    def import_metadata(self):
        '''
        Function to read metadata from all available sources and set self._metadata_dict. 
        Overrides Geophys2NetCDF.import_metadata()
        '''
        Geophys2NetCDF.import_metadata(self) # Call inherited function (will only read GDAL metadata from source dataset)
        
        # Read data from both .ers and .isi files into separate  metadata subtrees
        if self._input_path:
            for extension in ['isi', 'ers']:
                self._metadata_dict[extension.upper()] = ERSMetadata(os.path.splitext(self._input_path)[0] + '.' + extension).metadata_dict       
            
        try:
            #TODO: Make this more robust
            title = (self.get_metadata('ISI.MetaData.Extensions.JetStream.LABEL') or
                     os.path.basename(self.get_metadata('ISI.MetaData.Name')) or
                     self._netcdf_dataset.title
                     )
        except:
            title = None
        logger.debug('title = %s', title)
        
        self.get_uuid(title)
        
        # Get record from GA CSW
        try:
            csw_record = self.get_csw_record_by_id(Geophys2NetCDF.GA_CSW, self._uuid)
            logger.debug('GA csw_record = %s', csw_record)
            self._metadata_dict['GA_CSW'] = self.get_metadata_dict_from_xml(csw_record.xml)
        except:
            raise Exception('ERROR: Unable to retrieve CSW record %s from %s' % (self._uuid, Geophys2NetCDF.GA_CSW))
        
        # Get record from NCI CSW (Optional)
        try:
            csw_record = self.get_csw_record_by_id(Geophys2NetCDF.NCI_CSW, self._uuid)
            logger.debug('NCI csw_record = %s', csw_record)
            self._metadata_dict['NCI_CSW'] = self.get_metadata_dict_from_xml(csw_record.xml)
        except:
            logger.warning('WARNING: Unable to retrieve CSW record %s from %s', self._uuid, Geophys2NetCDF.NCI_CSW)
        
        logger.debug('self._metadata_dict = %s', self._metadata_dict)

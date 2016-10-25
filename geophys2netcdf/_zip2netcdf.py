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
import errno
import logging
import subprocess
import tempfile
from shutil import rmtree

from geophys2netcdf._geophys2netcdf import Geophys2NetCDF
from _ers2netcdf import ERS2NetCDF

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Initial logging level for this module


class Zip2NetCDF(Geophys2NetCDF):
    '''
    Class definition for Zip2NetCDF to handle datasets held in zip files
    '''
    FILE_EXTENSION = 'zip'

    def __init__(self, input_path=None, output_path=None, debug=False):
        '''
        Constructor for class Zip2NetCDF
        '''
        self._geophys2netcdf = None
        self._zipdir = None
        self._debug = False
        self.debug = debug  # Set property

        if input_path:
            self.translate(input_path, output_path)

    def __del__(self):
        '''
        Destructor for class Zip2NetCDF
        '''
        if self._zipdir and not self._debug:
            logger.info('Removing temporary directory %s', self._zipdir)
            rmtree(self._zipdir)

    def translate(self, input_path, output_path=None):
        '''
        Function to perform ERS format-specific translation and set self._input_dataset and self._netcdf_dataset
        Overrides Geophys2NetCDF.translate()
        '''
        assert os.path.splitext(input_path)[1].lower(
        ) == '.zip', 'Input dataset %s is not a zip file' % input_path

        input_path = os.path.abspath(input_path)
        output_path = output_path or os.path.splitext(input_path)[0] + '.nc'

        # Remove any existing zip directory
        if self._zipdir:
            logger.info(
                'Removing previous temporary directory %s', self._zipdir)
            os.removedirs(self._zipdir)

        base_path = os.path.join(tempfile.gettempdir(), os.path.splitext(
            os.path.basename(input_path))[0])
        self._zipdir = base_path

        # Unzip file into fresh directory
        zipdir_revision = 0
        while os.path.exists(self._zipdir):
            zipdir_revision += 1
            self._zipdir = '%s_%s' % (base_path, zipdir_revision)
        logger.debug('self._zipdir = %s', self._zipdir)

        try:
            os.makedirs(self._zipdir)
        except OSError, exception:
            if exception.errno != errno.EEXIST or not os.path.isdir(self._zipdir):
                raise exception

        unzip_command = ['unzip',
                         input_path,
                         '-d',
                         self._zipdir
                         ]

        subprocess.check_call(unzip_command)
        logger.info('%s unzipped into %s', input_path, self._zipdir)

        file_list = os.listdir(self._zipdir)
        extension_set = set([os.path.splitext(file_path)[1].lower()
                             for file_path in file_list])
        logger.debug('file_list = %s', file_list)
        logger.debug('extension_set = %s', extension_set)

        if set(['.ers', '.isi', '']) <= extension_set:
            logger.info('%s contains an ERS dataset', self._zipdir)
            ers_list = [
                file_path for file_path in file_list if file_path.lower().endswith('.ers')]
            assert len(
                ers_list) == 1, 'Multiple .ers files found in %s' % self._zipdir

            ers_path = os.path.join(self._zipdir, ers_list[0])
            if os.path.exists(ers_path):
                logger.info('Translating %s to %s', ers_path, output_path)
                self._geophys2netcdf = ERS2NetCDF(
                    input_path=ers_path, output_path=output_path, debug=self._debug)

        elif set(['.blah']) < extension_set:  # Some other extensions
            pass

        else:
            raise Exception('Unhandled file types in zip file %s' % input_path)

    def update_nc_metadata(self, output_path=None):
        return self._geophys2netcdf.update_nc_metadata(output_path)

    def import_metadata(self):
        return self._geophys2netcdf.import_metadata()

    @property
    def metadata_dict(self):
        return self._geophys2netcdf._metadata_dict

    @property
    def metadata_sources(self):
        return sorted(self._geophys2netcdf._metadata_dict.keys())

    @property
    def input_dataset(self):
        return self._geophys2netcdf._input_dataset

    @property
    def netcdf_dataset(self):
        return self._geophys2netcdf._netcdf_dataset

    @property
    def uuid(self):
        return self._geophys2netcdf._uuid

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

            if self._geophys2netcdf:
                self._geophys2netcdf.debug = self._debug

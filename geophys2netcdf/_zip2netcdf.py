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
import sys
import errno
import logging
import subprocess
import tempfile

from _geophys2netdcf import Geophys2NetCDF
from _ers2netcdf import ERS2NetCDF

# Set handler for root logger to standard output
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
#console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)
logging.root.addHandler(console_handler)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Initial logging level for this module

class Zip2NetCDF(Geophys2NetCDF):
    '''
    '''
    def __getattr__(self, attr):
        '''
        Override class __getattr__ method to look in enclosed Geophys2NetCDF object
        '''
        if hasattr(self, attr):
            return super().__getattr__(self, attr)
        elif self._geophys2netcdf:
            return getattr(self._geophys2netcdf, attr)
        else:
            raise AttributeError("'Zip2NetCDF' object has no attribute '%s'" % attr)
        
    
    def __setattr__(self, attr, value):
        '''
        Override class __setattr__ method to look in enclosed Geophys2NetCDF object
        '''
        if hasattr(self, attr):
            super().__setattr__(attr, value)
        elif self._geophys2netcdf:
            setattr(self._geophys2netcdf, attr, value)
        else:
            raise AttributeError("'Zip2NetCDF' object has no attribute '%s'" % attr)
        
    
    def __init__(self, input_path=None, output_path=None, debug=False):
        '''
        Constructor for class Zip2NetCDF
        '''
        self._geophys2netcdf = None
        self._zipdir = None
        
        if input_path:
            self.translate(input_path, output_path)
            
    
    def __del__(self):
        '''
        Destructor for class Zip2NetCDF
        '''
        if self._zipdir:
            os.removedirs(self._zipdir)
            
        super().__del__(self)

    def translate(self, input_path, output_path=None):
        '''
        Function to perform ERS format-specific translation and set self._input_dataset and self._netcdf_dataset
        Overrides Geophys2NetCDF.translate()
        '''
        assert os.path.splitext(input_path)[1].lower() == 'zip', 'Input dataset %s is not a zip file' % input_path

        input_path = os.path.abspath(input_path)
        output_path = output_path or os.path.splitext(input_path)[0] + 'nc'
        
        # Remove any existing zip directory
        if self._zipdir:
            os.removedirs(self._zipdir)

        base_path = os.path.join(tempfile.gettempdir(), os.path.splitext(os.path.basename(input_path)[0]))
        self._zipdir = base_path
        
        # Unzip file into fresh directory
        zipdir_revision = 0
        while os.path.exists(self._zipdir):
            zipdir_revision += 1
            self._zipdir = '%_%s)' % (base_path, zipdir_revision)
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
        
        file_list = os.listdir(self._zipdir)
        extension_set = set([os.path.splitext(file_path)[1].lower() for file_path in file_list])
        logger.debug('file_list = %s', file_list)
        logger.debug('extension_set = %s', extension_set)

        if set(['ers', 'isi', '']) <= extension_set:
            logger.info('%s contains an ERS dataset', self._zipdir)
            ers_list = [file_path for file_path in file_list if file_path.lower().endswith('.ers')]
            assert len(ers_list) == 1, 'Multiple .ers files found in %s' % self._zipdir
            
            ers_path = ers_list[0]
            if os.path.exists(ers_path):
                self._geophys2netcdf = ERS2NetCDF()
                self._geophys2netcdf.translate(ers_path, output_path)
    
        elif set(['blah']) < extension_set:# Some other extensions 
            pass
            
        else:
            raise Exception('Unhandled file types in zip file %s' % input_path)      

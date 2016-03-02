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
from osgeo import osr
from osgeo import gdal
from pprint import pprint
from math import floor
from distutils.util import strtobool
from multiprocessing import Process, Lock, Pool, cpu_count


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
    DEFAULT_CONFIG_FILE = 'geophys2netcdf.conf' # N.B: Assumed to reside in code root directory
    MAX_READ_SIZE = 2 * 1073741824 

    def __init__(self, config=None, debug=False):
        '''
        '''
        self._debug = False
        self.debug = debug # Set property
        self._code_root = os.path.abspath(os.path.dirname(__file__)) # Directory containing module code
        self._config_path = config or os.path.join(self._code_root, Geophys2NetCDF.DEFAULT_CONFIG_FILE)
        self._medatadata_dict = {}
        
        # Create master configuration dict containing both command line and config_file parameters
        self._config_file_object = ConfigFile(self._config_path)  
    
    def translate(self, input_path, output_path=None):
        '''
        Virtual function
        '''
        assert os.path.exists(input_path), 'Input file %s does not exist' % input_path
        self._input_path = input_path
        
        # Default to outputting .nc file of same name in current dir
        self._output_path = output_path or os.path.splitext(os.path.basename(input_path))[0] + '.nc'
            
        self._input_dataset = None
        self._output_dataset = None
        self._metadata_dict = {}
    
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

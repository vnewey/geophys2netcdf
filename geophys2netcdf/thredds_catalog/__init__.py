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
THREDDSCatalog Class
Created on 22/03/2016

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
import re
import logging
import yaml

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Logging level for this module

# Ignore failed import of URL modules
try:
    import urllib
except:
    logger.warning('WARNING: Unable to import urllib. Any OPeNDAP function calls will fail.')

try:
    import lxml.html
except:
    logger.warning('WARNING: Unable to import lxml.html. Any OPeNDAP function calls will fail.')

class THREDDSCatalog(object):
    '''
    Class definition for THREDDSCatalog
    '''
    DEFAULT_THREDDS_CATALOGUE_URL = 'http://dapds00.nci.org.au/thredds/catalog.html'
    
    def __init__(self, thredds_catalog_url=None):
        '''
        Constructor for class THREDDSCatalog
        '''
        thredds_catalog_url = thredds_catalog_url or self.DEFAULT_THREDDS_CATALOGUE_URL
        
        self.thredds_catalog_dict = {thredds_catalog_url: self.get_thredds_dict(thredds_catalog_url)}

    
    def get_thredds_dict(self, thredds_catalog_url):
        '''
        get_thredds_dict - recursive function to parse specified THREDDS catalogue URL and return a nested dict
        Parameter: thredds_catalog_url - string specifying URL of THREDDS catalog
        '''
        def get_absolute_url(href):
            # Create absolute URL
            if href.startswith('/'): # Absolute href - should start with "/thredds/"
                return re.sub('/thredds/.*', href, thredds_catalog_url)
            else: # Relative href
                return re.sub('catalog.html$', href, thredds_catalog_url)
                
        thredds_catalog_dict = {} 
        
        data = urllib.urlopen(thredds_catalog_url).read()
        logger.debug('%s data = %s', thredds_catalog_url, data)
    
        tree = lxml.html.fromstring(data)
        
        title = tree.find('.//title')
        title_text = [e.strip() for e in title.xpath('.//text()') if len(e.strip()) > 0][0]
        logger.debug('title_text = %s', title_text)
        
        if title_text == 'Catalog Services': # This is a landing page for a file
            # Iterate through all service endpoints for file
            for ol in tree.iterfind('.//ol'):
#                logger.debug('ol = %s', ol)
                for li in ol.iterfind('.//li'):
#                    logger.debug('li = %s', li)
                    text = [e.strip() for e in li.xpath('.//text()') if len(e.strip()) > 0]
#                    logger.debug('text = %s', text)
                    if not text: # No li text found
                        continue
                    
                    endpoint_type = text[0].replace(':', '')
                    url = get_absolute_url(text[1])
                    
        #=======================================================================
        #             # Not sure why a isn't found
        #             a = li.find('.//a')
        #             if not a:
        #                 logger.debug('a not found')
        #                 continue
        # 
        #             href = a.get('href')
        #             if not href:
        #                 logger.debug('href not found')
        #                 continue
        #             
        #             url = get_absolute_url(href)
        #=======================================================================
                    
                    logger.debug('Service endpoint: endpoint_type = %s, href = %s', endpoint_type, url)
                    thredds_catalog_dict[endpoint_type] = url
                break # Only process first "<ol>"
            
        else: # Catalog page for virtual subdirectory
    
            for table in tree.iterfind('.//table'):
                first_row = True
                for row in table.iterfind('.//tr'):
                    a = row.find('.//a')
                    if not a:
                        continue
        
                    href = a.get('href')
                    logger.debug('href = %s', href)
                    if not href:
                        continue
                    
                    
                    # Discard first row (parent directory or license folder)
                    if first_row:
                        first_row = False
                        continue
                    
                    url = get_absolute_url(href)
                    
                    if href.endswith('catalog.html'): # Virtual subdirectory                    
                        logger.debug('Virtual subdirectory: url = %s', url)
                        thredds_catalog_dict[url] = self.get_thredds_dict(url) 
                               
                    elif href.startswith('catalog.html?dataset='): # File 
                        filename = os.path.basename(href)

                        logger.debug('File: filename = %s, url = %s', filename, url)
                        try:
                            thredds_catalog_dict[url] = self.get_thredds_dict(url)
                        except Exception, e:
                            logger.error('ERROR: %s', e.message)
                        
                    # Get rid of empty dicts      
                    if thredds_catalog_dict.get(url) == {}:
                        del thredds_catalog_dict[url]
                          
        logger.debug('thredds_catalog_dict = %s', thredds_catalog_dict)
        return thredds_catalog_dict

    def dump(self, yaml_path=None):
        yaml_path = os.path.abspath(yaml_path or (re.sub('\W', '_', re.sub('http://', '', self.thredds_catalog_dict.keys()[0])) + '.yaml'))
        yaml_file = open(yaml_path, 'w')
        yaml.dump(self.thredds_catalog_dict, yaml_file)
        yaml_file.close()
        logger.info('THREDDS catalogue dumped to file %s', yaml_path)
        
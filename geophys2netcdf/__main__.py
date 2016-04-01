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
Created on 08/03/2016

@author: Alex Ip
'''
import sys
import os

from geophys2netcdf import ERS2NetCDF, Zip2NetCDF

def main():
    assert len(sys.argv) >= 2, 'Must provide input file path and optional output file path'
    input_path = os.path.abspath(sys.argv[1])

    # If NetCDF path given, then do update_nc_metadata
    if len(sys.argv) == 2 and os.path.splitext(input_path)[1] == '.nc':
        g2n_object = ERS2NetCDF()
        try:
            g2n_object.check_json_metadata(input_path)
        except Exception, e:
            print('WARNING: %s' % e.message)
            
        g2n_object.update_nc_metadata(input_path)
        g2n_object.check_json_metadata(input_path)
        return

    # Default output path is next to input path
    if len(sys.argv) == 3:
        output_path = os.path.abspath(sys.argv[2])
    else:
        output_path = os.path.abspath(os.path.splitext(input_path)[0] + '.nc')

    g2n_object = None
    for subclass in [ERS2NetCDF, Zip2NetCDF]:
        if os.path.splitext(input_path)[1] == '.' + subclass.FILE_EXTENSION:
            print 'Input file is of type %s' % subclass.FILE_EXTENSION
            g2n_object = subclass(input_path, output_path) # Perform translation
            break
        
    assert g2n_object, 'Unrecognised input file extension'

main()


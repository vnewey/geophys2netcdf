'''
Created on 2Sep.,2016

@author: Alex
'''
import os
import sys
import errno
import logging
import subprocess
import tempfile
from shutil import rmtree
import glob
from osgeo import gdal, gdalconst
import netCDF4
from geophys2netcdf.array_pieces import array_pieces
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Initial logging level for this module

class ERS2NetCDFChecker(object):
    '''
    Class definition for ERS2NetCDFChecker to handle datasets held in zip files
    '''
    FILE_EXTENSION = 'zip'
    def __init__(self, dataset_dir=None, debug=False):
        '''
        Constructor for class ERS2NetCDFChecker
        '''
        self._zipdir = None
        self._debug = False
        self.debug = debug # Set property
        
        if dataset_dir:
            self.check_ERS2NetCDF(dataset_dir)
            
    
    def __del__(self):
        '''
        Destructor for class ERS2NetCDFChecker
        '''
        if self._zipdir and not self._debug:
            logger.info('Removing temporary directory %s', self._zipdir)
            rmtree(self._zipdir)

    def check_ERS2NetCDF(self, dataset_dir):
        '''
        Function to check NetCDF file against ERS 
        '''
        assert os.path.isdir(dataset_dir), '%s is not a directory'
        zip_list = glob.glob(os.path.join(dataset_dir, '*.zip'))
        assert len(zip_list) == 1, 'Unable to find single zip file in %s. (%s)' % (dataset_dir, zip_list.join(', '))
        zip_path = zip_list[0]
        nc_list = glob.glob(os.path.join(dataset_dir, '*.nc'))
        assert len(nc_list) == 1, 'Unable to find single NetCDF file in %s. (%s)' % (dataset_dir, nc_list.join(', '))
        nc_path = nc_list[0]
        
        # Remove any existing zip directory
        if self._zipdir:
            logger.info('Removing previous temporary directory %s', self._zipdir)
            os.removedirs(self._zipdir)

        base_path = os.path.join(tempfile.gettempdir(), os.path.splitext(os.path.basename(zip_path))[0])
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
                         zip_path,
                         '-d',
                         self._zipdir
                         ]
        
        subprocess.check_call(unzip_command)
        logger.info('%s unzipped into %s', zip_path, self._zipdir)

        file_list = os.listdir(self._zipdir)
        extension_set = set([os.path.splitext(file_path)[1].lower() for file_path in file_list])
        logger.debug('file_list = %s', file_list)
        logger.debug('extension_set = %s', extension_set)

        if set(['.ers', '.isi', '']) <= extension_set:
            logger.info('%s contains an ERS dataset', self._zipdir)
            ers_list = [file_path for file_path in file_list if file_path.lower().endswith('.ers')]
            assert len(ers_list) == 1, 'Multiple .ers files found in %s' % self._zipdir
            
            ers_path = os.path.join(self._zipdir, ers_list[0])
            if os.path.exists(ers_path):
                self.compare_ERS2NetCDF(ers_path, nc_path)
            
        else:
            raise Exception('Unhandled file types in zip file %s' % zip_path)      
        
    def compare_ERS2NetCDF(self, ers_path, nc_path):
        assert os.path.isfile(ers_path), 'ERS file %s does not exist' % ers_path
        assert os.path.isfile(nc_path), 'NetCDF file %s does not exist' % nc_path
        
        try:
            ers_gdal_dataset = gdal.Open(ers_path, gdalconst.GF_Read)
            assert ers_gdal_dataset, 'Unable to open ERS file %s using GDAL' % ers_path
            nc_gdal_dataset = gdal.Open(nc_path, gdalconst.GF_Read)
            assert nc_gdal_dataset, 'Unable to open NetCDF file %s using GDAL' % nc_path
            nc_dataset = netCDF4.Dataset(nc_path, 'r')
            assert nc_dataset, 'Unable to open NetCDF file %s using netCDF4' % nc_path
            
            if (ers_gdal_dataset.RasterCount == 1) and (nc_gdal_dataset.RasterCount == 1):
                print 'PASS: Both datasets have a single data variable'
            else:
                raise Exception('FAIL: Both datasets DO NOT have a single data variable')
            
            if (ers_gdal_dataset.RasterXSize == nc_gdal_dataset.RasterXSize) and (ers_gdal_dataset.RasterYSize == nc_gdal_dataset.RasterYSize):
                print 'PASS: Both datasets are the same shape'
            else:
                raise Exception('FAIL: Both datasets are not of the same shape')
            
            if ers_gdal_dataset.GetProjection() == nc_gdal_dataset.GetProjection():
                print 'PASS: Both datasets have the same projection'
            else:
                raise Exception('FAIL: Both datasets do not have the same projection')
            
            if ers_gdal_dataset.GetGeoTransform() == nc_gdal_dataset.GetGeoTransform():
                print 'PASS: Both datasets have the same spatial extent and resolution'
            else:
                raise Exception('FAIL: Both datasets do not have the same spatial extent and resolution')
            
            ers_band = ers_gdal_dataset.GetRasterBand(1)
            nc_band = ers_gdal_dataset.GetRasterBand(1)
            
            if ers_band.GetNoDataValue() == nc_band.GetNoDataValue():
                print 'PASS: Both datasets have the same no-data value'
            else:
                raise Exception('FAIL: Both datasets do not have the same no-data value')
            
            
            
            # Find variable with "grid_mapping" attribute in NetCDF dataset - assumed to be 2D data variable
            try:
                data_variable = [variable for variable in nc_dataset.variables.values() if hasattr(variable, 'grid_mapping')][0]
            except:
                raise Exception('Unable to determine data variable (must have "grid_mapping" attribute')
        
            pixel_count = 0
            min_nc_value = None
            max_nc_value = None
            min_ers_value = None
            max_ers_value = None
            min_difference = None
            max_difference = None
            weighted_mean_nc_value = 0
            weighted_mean_ers_value = 0
            weighted_mean_difference = 0
            for nc_piece_array, start_indices in array_pieces(data_variable, 1000000000): # 1GB Pieces  
                piece_size = reduce(lambda x, y: x*y, nc_piece_array.shape)
                              
                if type(nc_piece_array) == np.ma.core.MaskedArray:
                    nc_piece_array = nc_piece_array.data
                    
                ers_piece_array = ers_band.ReadAsArray(start_indices[0], start_indices[1], nc_piece_array.shape[0], nc_piece_array.shape[1])
                
                difference_piece_array = nc_piece_array - ers_piece_array
                
                try:
                    min_nc_value = min(min_nc_value, np.nanmin(nc_piece_array))
                except:
                    min_nc_value= np.nanmin(nc_piece_array)
        
                try:
                    max_nc_value = max(max_nc_value, np.nanmax(nc_piece_array))
                except:
                    max_nc_value = np.nanmax(nc_piece_array)

                try:
                    min_ers_value = min(min_ers_value, np.nanmin(ers_piece_array))
                except:
                    min_ers_value= np.nanmin(ers_piece_array)
        
                try:
                    max_ers_value = max(max_ers_value, np.nanmax(ers_piece_array))
                except:
                    max_ers_value = np.nanmax(ers_piece_array)

                try:
                    min_difference = min(min_difference, np.nanmin(difference_piece_array))
                except:
                    min_difference= np.nanmin(difference_piece_array)
        
                try:
                    max_difference = max(max_difference, np.nanmax(difference_piece_array))
                except:
                    max_difference = np.nanmax(difference_piece_array)

                
                weighted_mean_nc_value += np.nanmean(nc_piece_array) * piece_size
                weighted_mean_ers_value += np.nanmean(ers_piece_array) * piece_size
                weighted_mean_difference += np.nanmean(difference_piece_array) * piece_size
                
                pixel_count += piece_size
                
            mean_nc_value = weighted_mean_nc_value / pixel_count 
            mean_ers_value = weighted_mean_ers_value / pixel_count 
            mean_difference = weighted_mean_difference / pixel_count 
            
            print 'min nc_value = %f, mean nc_value = %f, max nc_value = %f' % (min_nc_value, mean_nc_value, max_nc_value)
            print 'min ers_value = %f, mean ers_value = %f, max ers_value = %f' % (min_ers_value, mean_ers_value, max_ers_value)
            print 'min difference = %f, mean difference = %f, max difference = %f' % (min_difference, mean_difference, max_difference)
             
        except Exception, e:
            print 'File comparison failed: %s' % e.message
            
            
def main():
    if len(sys.argv) == 2: # Only directory provided
        e2nchecker = ERS2NetCDFChecker(sys.argv[1])
    if len(sys.argv) == 3: # Only directory provided
        e2nchecker = ERS2NetCDFChecker()
        e2nchecker.compare_ERS2NetCDF(sys.argv[1], sys.argv[2])
        
if __name__ == '__main__':
    main()

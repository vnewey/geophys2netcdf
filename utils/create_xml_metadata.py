'''
Created on Apr 7, 2016

@author: Alex Ip, Geoscience Australia
'''
import sys
import netCDF4
import re
import os
import uuid
from pprint import pprint
from jinja2 import Environment, PackageLoader, select_autoescape
from geophys2netcdf.metadata import Metadata, SurveyMetadata, NetCDFMetadata #, JetCatMetadata
from geophys_utils._netcdf_grid_utils import NetCDFGridUtils
from geophys_utils._crs_utils import transform_coords
from geophys2netcdf.metadata import TemplateMetadata

def main():
    '''
    Main function
    '''
    
    def get_xml_text(xml_template_path, metadata_object):
        '''Helper function to perform substitutions on XML template text
        '''
        jinja_environment = Environment(
            loader=PackageLoader(__name__, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'xml')),
            autoescape=select_autoescape(['html', 'xml']
                                         )
                                        )
            
        xml_template = jinja_environment.get_template(xml_template_path)
            
        value_dict = dict(metadata_object.metadata_dict['Template'])
        
        # Convert comma-separated lists to lists of strings
        value_dict['keywords'] = [keyword.strip() for keyword in value_dict['KEYWORDS'].split(',')]
        
        return xml_template.render(**value_dict)

    # Start of main function
    assert len(
        sys.argv) == 4, 'Usage: %s <json_text_template_path> <xml_template_path> <netcdf_path>' % sys.argv[0]
    json_text_template_path = sys.argv[1]
    xml_template_path = sys.argv[2]
    netcdf_path = sys.argv[3]
#    jetcat_path = sys.argv[x]

    metadata_object = Metadata()

    netcdf_metadata = NetCDFMetadata(netcdf_path)
    metadata_object.merge_root_metadata_from_object(netcdf_metadata)

    nc_dataset = netCDF4.Dataset(netcdf_path, 'r+') # Allow for updating of netCDF attributes like uuid
    
    # JetCat and Survey metadata can either take a list of survey IDs as source(s) or a filename from which to parse them
    try:
        survey_ids = nc_dataset.survey_id
        print 'Survey ID "%s" found in netCDF attributes' % survey_ids
        source = [int(value_string.strip()) for value_string in survey_ids.split(',') if value_string.strip()]
    except:
        source = netcdf_path

#    jetcat_metadata = JetCatMetadata(source, jetcat_path=jetcat_path)
#    metadata_object.merge_root_metadata_from_object(jetcat_metadata)

    survey_metadata = SurveyMetadata(source)
    metadata_object.merge_root_metadata_from_object(survey_metadata)

    nc_grid_utils = NetCDFGridUtils(nc_dataset)
    
    # Add some calculated values to the metadata
    calculated_values = {}
    metadata_object.metadata_dict['Calculated'] = calculated_values
    
    calculated_values['FILENAME'] = os.path.basename(netcdf_path)
    
    # Find survey year from end date
    try:
        year = int(re.match('.*?(\d+)$', metadata_object.get_metadata(['Survey', 'ENDDATE'])).group(1))
        if year < 20:
            year += 2000
        elif year < 100:
            year += 1900
            
        calculated_values['YEAR'] = str(year)    
    except:
        calculated_values['YEAR'] = 'UNKNOWN'
        
   
    
    #calculated_values['CELLSIZE'] = str((nc_grid_utils.pixel_size[0] + nc_grid_utils.pixel_size[1]) / 2.0)
    calculated_values['CELLSIZE_M'] = str(int(round((nc_grid_utils.nominal_pixel_metres[0] + nc_grid_utils.nominal_pixel_metres[1]) / 20.0) * 10))
    calculated_values['CELLSIZE_DEG'] = str(round((nc_grid_utils.nominal_pixel_degrees[0] + nc_grid_utils.nominal_pixel_degrees[1]) / 2.0, 8))
    
    survey_id = metadata_object.get_metadata(['Survey', 'SURVEYID'])
    try:
        dataset_survey_id = nc_dataset.survey_id
        assert (set([int(value_string.strip()) for value_string in dataset_survey_id.split(',') if value_string.strip()]) == 
                set([int(value_string.strip()) for value_string in survey_id.split(',') if value_string.strip()])), 'NetCDF survey ID %s is inconsistent with %s' % (dataset_survey_id, survey_id)
    except:
        nc_dataset.survey_id = survey_id
        nc_dataset.sync()
        print 'Survey ID %s written to netCDF file' % survey_id

    dataset_uuid = metadata_object.get_metadata(['NetCDF', 'uuid'])
    if not dataset_uuid: # Create a new UUID and write it to the netCDF file 
        dataset_uuid = uuid.uuid4()
        nc_dataset.uuid = dataset_uuid
        nc_dataset.sync()
        print 'Fresh UUID %s generated and written to netCDF file' % dataset_uuid
        
    calculated_values['UUID'] = str(dataset_uuid)   
    
    WGS84_bbox = transform_coords(nc_grid_utils.native_bbox, nc_grid_utils.crs, 'EPSG:4326')
    WGS84_extents = [min([coordinate[0] for coordinate in WGS84_bbox]),
                     min([coordinate[1] for coordinate in WGS84_bbox]),
                     max([coordinate[0] for coordinate in WGS84_bbox]),
                     max([coordinate[1] for coordinate in WGS84_bbox])
                     ]
    
    calculated_values['ELON'] = str(WGS84_extents[0])
    calculated_values['SLAT'] = str(WGS84_extents[1])
    calculated_values['WLON'] = str(WGS84_extents[2])
    calculated_values['NLAT'] = str(WGS84_extents[3])
    
    #calculated_values['CELLSIZE_DEG'] = (WGS84_extents[2] - WGS84_extents[0]) / 
    
    #template_class = None
    template_metadata_object = TemplateMetadata(json_text_template_path, metadata_object)
    
    metadata_object.merge_root_metadata_from_object(template_metadata_object)

    pprint(metadata_object.metadata_dict)
    
    xml_text = get_xml_text(xml_template_path, metadata_object)
    print xml_text

if __name__ == '__main__':
    main()

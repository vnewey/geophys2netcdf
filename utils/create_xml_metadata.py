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
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from geophys2netcdf.metadata import Metadata, SurveyMetadata, NetCDFMetadata #, JetCatMetadata
from geophys_utils._netcdf_grid_utils import NetCDFGridUtils
from geophys_utils._crs_utils import transform_coords
from geophys2netcdf.metadata import TemplateMetadata

try:
    from geophys2netcdf.metadata import ArgusMetadata
except:
    pass

def main():
    '''
    Main function
    '''
    
    def get_xml_text(xml_template_path, metadata_object):
        '''Helper function to perform substitutions on XML template text
        '''
        template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
        jinja_environment = Environment(
            loader=FileSystemLoader(template_dir or './'),
            autoescape=select_autoescape(['html', 'xml']
                                         )
                                        )
            
        xml_template = jinja_environment.get_template(xml_template_path, parent=None)
            
        value_dict = dict(metadata_object.metadata_dict['Template']) # Copy template values
        
        # Convert multiple sets of comma-separated lists to lists of strings to a list of dicts
        #TODO: Make this slicker
        value_dict['keywords'] = []
        for keyword_list_key in [key for key in value_dict.keys() if re.match('^KEYWORD_\w+_LIST$', key)]:
            keywords = [keyword.strip() for keyword in value_dict[keyword_list_key].split(',')]
            keyword_code = value_dict[re.sub('_LIST$', '_CODE', keyword_list_key)]
            
            value_dict['keywords'] += [{'value': keyword,
                                        'code': keyword_code
                                        } for keyword in keywords
                                       ]
        
        # Create dict containing distribution info for DOI if required
        value_dict['distributions'] = []
        dataset_doi = metadata_object.get_metadata(['Calculated', 'DOI'])
        if dataset_doi:
            try:
                distribution_dict = {'formatSpecification': 'html',
                                     'distributor_name': metadata_object.get_metadata(['Template', 'ORGANISATION_NAME']),
                                     'distributor_telephone': metadata_object.get_metadata(['Template', 'ORGANISATION_PHONE']),
                                     'distributor_address': metadata_object.get_metadata(['Template', 'ORGANISATION_ADDRESS']),
                                     'distributor_city': metadata_object.get_metadata(['Template', 'ORGANISATION_CITY']),
                                     'distributor_state': metadata_object.get_metadata(['Template', 'ORGANISATION_STATE']),
                                     'distributor_postcode': metadata_object.get_metadata(['Template', 'ORGANISATION_POSTCODE']),
                                     'distributor_country': metadata_object.get_metadata(['Template', 'ORGANISATION_COUNTRY']),
                                     'distributor_email': metadata_object.get_metadata(['Template', 'ORGANISATION_EMAIL']),
                                     'url': dataset_doi,
                                     'protocol': 'WWW:LINK-1.0-http--link',
                                     'name': 'Digital Object Identifier for dataset %s' % metadata_object.get_metadata(['Calculated', 'UUID']),
                                     'description': 'Dataset DOI'
                                     }
                
                for key, value in distribution_dict.iteritems():
                    assert value, '%s has no value defined' % key
                
                value_dict['distributions'].append(distribution_dict)
            except Exception as e:
                print 'WARNING: Unable to create DOI distribution: %s' % e.message
        
        return xml_template.render(**value_dict)

    # Start of main function
    assert len(
        sys.argv) >= 4 and len(sys.argv) <= 8, 'Usage: %s <json_text_template_path> <xml_template_path> <netcdf_path> [<xml_output_dir>]' % sys.argv[0]
    json_text_template_path = sys.argv[1]
    xml_template_path = sys.argv[2]
    netcdf_path = sys.argv[3]
    if len(sys.argv) >= 5:
        xml_dir = sys.argv[4]
    else:
        xml_dir = '.'
        
    if len(sys.argv) == 8:
        db_user = sys.argv[5]
        db_password = sys.argv[6]
        db_alias = sys.argv[7]
    else:
        db_user = None
        db_password = None
        db_alias = None
        
#    jetcat_path = sys.argv[x]

    xml_path = os.path.abspath(os.path.join(xml_dir, os.path.splitext(os.path.basename(netcdf_path))[0] + '.xml'))
    print xml_dir, xml_path

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

    try:
        survey_metadata = SurveyMetadata(source)
        metadata_object.merge_root_metadata_from_object(survey_metadata)
    except Exception as e:
        print e.message, 'Attempting direct DB read'
        survey_metadata = ArgusMetadata(db_user, db_password, db_alias, source)
        metadata_object.merge_root_metadata('Survey', survey_metadata.metadata_dict, overwrite=True) # Fake Survey metadata from DB query

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
    
    try:
        calculated_values['START_DATE'] = datetime.strptime(str(metadata_object.get_metadata(['Survey', 'STARTDATE'])), '%d-%b-%y').date().isoformat()
    except:
        calculated_values['START_DATE'] = 'UNKNOWN'    
    
    try:
        calculated_values['END_DATE'] = datetime.strptime(str(metadata_object.get_metadata(['Survey', 'ENDDATE'])), '%d-%b-%y').date().isoformat()
    except:
        calculated_values['END_DATE'] = 'UNKNOWN'    
    
    #history = "Wed Oct 26 14:34:42 2016: GDAL CreateCopy( /local/el8/axi547/tmp/mWA0769_770_772_773.nc, ... )"
    try:
        conversion_datetime_string = re.match('^(.+):.*', str(metadata_object.get_metadata(['NetCDF', 'history']))).group(1)
        try:
            conversion_datetime_string = datetime.strptime(conversion_datetime_string, '%a %b %d %H:%M:%S %Y').isoformat()
        except:
            pass
    except:
        conversion_datetime_string = 'UNKNOWN'
        
    calculated_values['CONVERSION_DATETIME'] = conversion_datetime_string
    
    survey_id = str(metadata_object.get_metadata(['Survey', 'SURVEYID']))
    try:
        dataset_survey_id = str(nc_dataset.survey_id)
        assert (set([int(value_string.strip()) for value_string in dataset_survey_id.split(',') if value_string.strip()]) == 
                set([int(value_string.strip()) for value_string in survey_id.split(',') if value_string.strip()])), 'NetCDF survey ID %s is inconsistent with %s' % (dataset_survey_id, survey_id)
    except:
        nc_dataset.survey_id = str(survey_id)
        nc_dataset.sync()
        print 'Survey ID %s written to netCDF file' % survey_id

    dataset_uuid = metadata_object.get_metadata(['NetCDF', 'uuid'])
    if not dataset_uuid: # Create a new UUID and write it to the netCDF file 
        dataset_uuid = uuid.uuid4()
        nc_dataset.uuid = dataset_uuid
        nc_dataset.sync()
        print 'Fresh UUID %s generated and written to netCDF file' % dataset_uuid
        
    calculated_values['UUID'] = str(dataset_uuid)   
    
    dataset_doi = metadata_object.get_metadata(['NetCDF', 'doi'])
    if not dataset_doi and False: #TODO: Mint a new DOI and write it to the netCDF file 
        dataset_doi = '' #TODO: Replace this with call to DOI minter - might be problematic from a non-GA source address
        nc_dataset.doi = dataset_doi
        nc_dataset.sync()
        print 'Fresh DOI %s generated and written to netCDF file' % dataset_uuid
        
    if dataset_doi:
        calculated_values['DOI'] = str(dataset_doi) 
    
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
        
    #template_class = None
    template_metadata_object = TemplateMetadata(json_text_template_path, metadata_object)
    metadata_object.merge_root_metadata_from_object(template_metadata_object)

    #pprint(metadata_object.metadata_dict)
    
    xml_text = get_xml_text(xml_template_path, metadata_object)
    #print xml_text
    xml_file = open(xml_path, 'w')
    xml_file.write(xml_text)
    xml_file.close()
    print 'XML written to %s' % xml_path

if __name__ == '__main__':
    main()

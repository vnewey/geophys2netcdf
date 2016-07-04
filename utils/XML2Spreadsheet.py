import sys
import re
import subprocess
import urllib
import lxml.html
from geophys2netcdf.metadata import XMLMetadata

identifier_list=['dbcc0c59-81e6-4eed-e044-00144fdd4fa6',
             '0d99907a-a4b5-d656-e053-12a3070ad7ae',
             '0d9a959a-f3f2-cb51-e053-12a3070ab5f9',
             '221dcfd8-04f1-5083-e053-10a3070a64e3',
             '221dcfd8-04f2-5083-e053-10a3070a64e3',
             '221dcfd8-04f4-5083-e053-10a3070a64e3',
             '221dcfd8-04f5-5083-e053-10a3070a64e3',
             '221dcfd8-04f6-5083-e053-10a3070a64e3',
             '221dcfd8-04f7-5083-e053-10a3070a64e3',
             '221dcfd8-04f8-5083-e053-10a3070a64e3',
             '221dcfd8-04f9-5083-e053-10a3070a64e3',
             '221dcfd8-04fa-5083-e053-10a3070a64e3',
             '221dcfd8-04fb-5083-e053-10a3070a64e3',
             '221dcfd8-04fc-5083-e053-10a3070a64e3',
             '221dcfd8-04fd-5083-e053-10a3070a64e3',
             '221dcfd8-04fe-5083-e053-10a3070a64e3',
             '221dcfd8-04ff-5083-e053-10a3070a64e3'
             ]

xpath_list = [ # ('netcdf_attribute', 'metadata.key'),
                        ('title', 'mdb:MD_Metadata/mdb:identificationInfo/mri:MD_DataIdentification/mri:citation/cit:CI_Citation/cit:title/gco:CharacterString'),
                        ('uuid', 'mdb:MD_Metadata/mdb:metadataIdentifier/mcc:MD_Identifier/mcc:code/gco:CharacterString'),
                        ('parent_uuid', 'mdb:MD_Metadata/mdb:parentMetadata/cit:CI_Citation/cit:identifier/mcc:MD_Identifier/mcc:code/gcx:FileName/TEXT'),
                        ('parent_id_type', 'mdb:MD_Metadata/mdb:parentMetadata/cit:CI_Citation/cit:identifier/mcc:MD_Identifier/mcc:description/gco:CharacterString'),
                        ('abstract', 'mdb:MD_Metadata/mdb:identificationInfo/mri:MD_DataIdentification/mri:abstract/gco:CharacterString'),
                        ('lineage_statement', 'mdb:MD_Metadata/mdb:resourceLineage/mrl:LI_Lineage/mrl:statement/gco:CharacterString'),
                        ('source_description', 'mdb:MD_Metadata/mdb:resourceLineage/mrl:LI_Lineage/mrl:source/mrl:LI_Source/mrl:description/gco:CharacterString'),
                        ('keywords', 'mdb:MD_Metadata/mdb:identificationInfo/mri:MD_DataIdentification/mri:descriptiveKeywords/mri:MD_Keywords/mri:keyword/gco:CharacterString'),
                        ('bounds_west', 'mdb:MD_Metadata/mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:geographicElement/gex:EX_GeographicBoundingBox/gex:westBoundLongitude/gco:Decimal'),
                        ('bounds_east', 'mdb:MD_Metadata/mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:geographicElement/gex:EX_GeographicBoundingBox/gex:eastBoundLongitude/gco:Decimal'),
                        ('bounds_south', 'mdb:MD_Metadata/mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:geographicElement/gex:EX_GeographicBoundingBox/gex:southBoundLatitude/gco:Decimal'),
                        ('bounds_north', 'mdb:MD_Metadata/mdb:identificationInfo/mri:MD_DataIdentification/mri:extent/gex:EX_Extent/gex:geographicElement/gex:EX_GeographicBoundingBox/gex:northBoundLatitude/gco:Decimal'),
                        ('distribution_urls', 'mdb:MD_Metadata/mdb:distributionInfo/mrd:MD_Distribution/mrd:distributionFormat/mrd:MD_Format/mrd:formatDistributor/mrd:MD_Distributor/mrd:distributorTransferOptions/mrd:MD_DigitalTransferOptions/mrd:onLine/cit:CI_OnlineResource/cit:linkage/gco:CharacterString'),
                        ('distribution_protocols', 'mdb:MD_Metadata/mdb:distributionInfo/mrd:MD_Distribution/mrd:distributionFormat/mrd:MD_Format/mrd:formatDistributor/mrd:MD_Distributor/mrd:distributorTransferOptions/mrd:MD_DigitalTransferOptions/mrd:onLine/cit:CI_OnlineResource/cit:protocol/gco:CharacterString'),
                        ('distribution_names', 'mdb:MD_Metadata/mdb:distributionInfo/mrd:MD_Distribution/mrd:distributionFormat/mrd:MD_Format/mrd:formatDistributor/mrd:MD_Distributor/mrd:distributorTransferOptions/mrd:MD_DigitalTransferOptions/mrd:onLine/cit:CI_OnlineResource/cit:name/gco:CharacterString'),
                        ('distribution_descriptions', 'mdb:MD_Metadata/mdb:distributionInfo/mrd:MD_Distribution/mrd:distributionFormat/mrd:MD_Format/mrd:formatDistributor/mrd:MD_Distributor/mrd:distributorTransferOptions/mrd:MD_DigitalTransferOptions/mrd:onLine/cit:CI_OnlineResource/cit:description/gco:CharacterString'),
                        ]

field_list = ['title',
              'uuid',
              'doi',
              'parent_uuid',
              'abstract',
              'lineage_statement',
 'source_description',
 'keywords',
 'bounds_west',
 'bounds_east',
 'bounds_south',
 'bounds_north']

csv_path = '/home/547/axi547/national_coverage_metadata.csv'

#GA_GEONETWORK = 'http://ecat.ga.gov.au/geonetwork/srv/eng'
GA_GEONETWORK = 'http://localhost:8081/geonetwork/srv/eng'

def main():
    def get_xml_by_id(geonetwork_url, identifier):
        xml_url = '%s/xml.metadata.get?uuid=%s' % (geonetwork_url, identifier)
        return urllib.urlopen(xml_url).read()

    spreadsheet_dict = {}
    for identifier in identifier_list:
        print 'Reading XML for UUID %s' % identifier
        
        xml_text = get_xml_by_id(GA_GEONETWORK, identifier)
        
        #xml_tree = lxml.html.fromstring(xml_text)
        
        xml_metadata = XMLMetadata()
        xml_metadata.read_string(xml_text)
        record_dict = {}
        spreadsheet_dict[identifier] = record_dict
        
        for xpath_tuple in xpath_list:
            record_dict[xpath_tuple[0]] = xml_metadata.get_metadata(xpath_tuple[1].split('/'))
        
        parent_id_dict = dict(zip(record_dict['parent_id_type'].split(', '), record_dict['parent_uuid'].split(', ')))
        record_dict['parent_uuid'] = parent_id_dict.get('UUID')
        
        record_dict['distribution_urls'] = record_dict['distribution_urls'].split(', ')
        record_dict['distribution_protocols'] = record_dict['distribution_protocols'].split(', ')
        record_dict['distribution_names'] = record_dict['distribution_names'].split(', ')
        record_dict['distribution_descriptions'] = record_dict['distribution_descriptions'].split(', ')
        
        distributions = []
        record_dict['distributions'] = distributions
        for dist_index in range(len(record_dict['distribution_urls'])):
            if re.search('dx\.doi\.org', record_dict['distribution_urls'][dist_index]):
                record_dict['doi'] = record_dict['distribution_urls'][dist_index]
                
            distributions.append({'url': '"' + record_dict['distribution_urls'][dist_index].strip() + '"',
                                  'protocol': '"' + record_dict['distribution_protocols'][dist_index].strip() + '"',
                                  'name': '"' + record_dict['distribution_names'][dist_index].strip() + '"',
                                  'description': '"' + record_dict['distribution_descriptions'][dist_index].strip() + '"',
                                 }) 

        del record_dict['distribution_urls'] 
        del record_dict['distribution_protocols'] 
        del record_dict['distribution_names'] 
        del record_dict['distribution_descriptions'] 
        
        for key in record_dict.keys():
            if type(record_dict[key]) == str and re.match('bounds_.*', key) is None:
                record_dict[key] = '"' + record_dict[key].strip() + '"'
                
    dist_count = max([len(record_dict['distributions']) for record_dict in spreadsheet_dict.values()])
    
    csv_file = open(csv_path, 'w')
    
    spreadsheet_line = ','.join(['"' + field_name + '"' for field_name in field_list])
    for dist_index in range(dist_count):
        for field_name in ['url', 'protocol', 'name', 'description']:
            spreadsheet_line += ',"dist%s_%s"' % (dist_index, field_name)
    
    csv_file.write(spreadsheet_line + '\n') # Write headers
    
    for record_dict in [spreadsheet_dict[xml] for xml in sorted(spreadsheet_dict.keys())]: 
        spreadsheet_line = ','.join([record_dict[key] for key in field_list])
        
        for dist_index in range(len(record_dict['distributions'])):
            dist_dict = record_dict['distributions'][dist_index]
            for field_name in ['url', 'protocol', 'name', 'description']:
                spreadsheet_line += ',' + dist_dict[field_name] 
            
        csv_file.write(spreadsheet_line + '\n') # Write values
        
    csv_file.close()
    print "Finished writing CSV file to %s" % csv_path

if __name__ == '__main__':
    main()




'''
Created on 1Aug.,2016

@author: Alex
'''
import sys
import os
import re
import urllib
import netCDF4
from lxml import etree
from geophys2netcdf import THREDDSCatalog

class XMLUpdater(object):

    # XML_DIR = '/home/547/axi547/national_coverage_metadata'
    XML_DIR = './'
    GA_GEONETWORK = 'http://localhost:8081/geonetwork/srv/eng'
    THREDDS_ROOT_DIR = '/g/data1/rr2/'
    
    THREDDS_CATALOG_URL = 'http://dap.nci.org.au/thredds/remoteCatalogService?catalog=http://dapds00.nci.org.au/thredds/catalogs/rr2/catalog.xml'
    #THREDDS_CATALOG_URL = 'http://dapds00.nci.org.au/thredds/catalogs/rr2/catalog.html'
    print 'thredds_catalog_url = %s' % THREDDS_CATALOG_URL
    
    def __init__(self):
    
        def get_thredds_catalog(thredds_catalog_url):
            yaml_path = os.path.abspath(re.sub('\W', '_', os.path.splitext(re.sub('^http://dap.*\.nci\.org\.au/thredds/', '', thredds_catalog_url))[0]) + '.yaml')
            print 'yaml_path = %s' % yaml_path
            
            if os.path.isfile(yaml_path):
                # Load previously cached catalogue tree
                tc = THREDDSCatalog(yaml_path=yaml_path)
            else:
                # WARNING: This operation may take several hours to complete!
                tc = THREDDSCatalog(thredds_catalog_url=thredds_catalog_url)
                tc.dump(yaml_path)
            
            return tc
        
        self.thredds_catalog = get_thredds_catalog(self.THREDDS_CATALOG_URL)
        
    
    def update_xml(self, nc_path):
        
        def expand_namespace(tag):
            nsmap = {'mdb': 'http://standards.iso.org/iso/19115/-3/mdb/1.0',
                     'mrd': 'http://standards.iso.org/iso/19115/-3/mrd/1.0',
                     'cit': 'http://standards.iso.org/iso/19115/-3/cit/1.0',
                     'gco': 'http://standards.iso.org/iso/19115/-3/gco/1.0',
                    }
            ns_match = re.match('^(\w+):(.+$)', tag)
            if ns_match:
                return './/{' + nsmap[ns_match.group(1)] + '}' + ns_match.group(2)
            else:
                return tag
            
        #=======================================================================
        # def get_datatype(basename):
        #     # Dict of datatypes with filename matching regex
        #     datatype_matches = {'airborne_electromagnetics': None, 
        #              'gravity': 'grav|bouguer',
        #              'magnetics': '^mag',
        #              'magnetotellurics': None,
        #              'radiometrics': '^rad',
        #              'surveys': None,
        #              }
        # 
        #     for datatype in datatype_matches.keys():
        #         if datatype_matches[datatype] and re.search(re.compile(datatype_matches[datatype], re.I), basename):
        #             return datatype
        #     return None # Return None for no match
        #=======================================================================
            
        
        def get_xml_by_id(geonetwork_url, uuid):
            xml_url = '%s/xml.metadata.get?uuid=%s' % (geonetwork_url, uuid)
            print 'URL = %s' % xml_url
            return urllib.urlopen(xml_url).read()
        
        nc_path = os.path.abspath(nc_path)
        
        # Read required values from NetCDF file
        nc_dataset = netCDF4.Dataset(nc_path)
        uuid = nc_dataset.uuid
        doi = nc_dataset.doi
        nc_dataset.close()
        
        print 'Processing Dataset %s with UUID %s' % (nc_path, uuid)
        
        nc_distribution_dict = self.thredds_catalog.find_url_dict(nc_path)
        zip_distribution_dict = self.thredds_catalog.find_url_dict(os.path.splitext(nc_path)[0] + '.zip')
        
        template_dict = {
                         'UUID': uuid,
                         'DOI': doi,
                         'THREDDS_CATALOG_URL': self.thredds_catalog.find_catalogs(nc_path)[-1],
                         'THREDDS_CATALOG_URL': self.thredds_catalog.find_catalogs(nc_path)[-1],
                         'NC_HTTP_URL': nc_distribution_dict['HTTPServer'],
                         'NCSS_URL': nc_distribution_dict['NetcdfSubset'],
                         'OPENDAP_URL': nc_distribution_dict['OPENDAP'],
                         'WCS_URL': nc_distribution_dict['WCS'],
                         'WMS_URL': nc_distribution_dict['WMS'],
                         'ZIP_HTTP_URL': zip_distribution_dict['HTTPServer'],
                         }
        print template_dict
    
        # Read XML template file
        distributionInfo_template_file = open('distributionInfo_template.xml')
        distributionInfo_template_text = distributionInfo_template_file.read()
        distributionInfo_template_file.close()

        for key in sorted(template_dict.keys()):
            distributionInfo_template_text = re.sub('%%%s%%' % key, template_dict[key], distributionInfo_template_text)   
                
        print distributionInfo_template_text
        
        distributionInfo_template_tree = etree.fromstring(distributionInfo_template_text).find(expand_namespace('mdb:distributionInfo'))
        
        try:
            xml_text = get_xml_by_id(self.GA_GEONETWORK, uuid)
            xml_tree = etree.fromstring(xml_text)
        except Exception, e:
            print xml_text
            raise e
        
        metadata_tree = xml_tree.find(expand_namespace('mdb:MD_Metadata'))
        distributionInfo_tree = metadata_tree.find(expand_namespace('mdb:distributionInfo'))
        
        if distributionInfo_tree is None:
            metadata_tree.append(distributionInfo_template_tree)
        else:
            metadata_tree.replace(distributionInfo_tree, distributionInfo_template_tree)
        
        xml_path = os.path.abspath(os.path.join(self.XML_DIR, '%s.xml' % uuid))
        xml_file = open(xml_path, 'w')
        
        xml_file.write(etree.tostring(xml_tree, pretty_print=True))
        
        xml_file.close()
        print 'Finished writing XML to file %s' % xml_path
    
def main():
    xml_updater = XMLUpdater()
    
    for nc_path in sys.argv[1:]:
        try:
            xml_updater.update_xml(nc_path)
        except Exception, e:
            print 'XML update failed for %s:\n%s' % (nc_path, e.message)
        

if __name__ == '__main__':
    main()   
    
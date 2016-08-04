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
    
    THREDDS_CATALOG_URL = 'http://dapds00.nci.org.au/thredds/catalogs/rr2/catalog.html'
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
        
        self.nsmap = None
        self.thredds_catalog = get_thredds_catalog(self.THREDDS_CATALOG_URL)
        
    
    def update_xml(self, nc_path):
        
        def get_xml_by_id(geonetwork_url, uuid):
            xml_url = '%s/xml.metadata.get?uuid=%s' % (geonetwork_url, uuid)
            print 'URL = %s' % xml_url
            return urllib.urlopen(xml_url).read()
        
        nc_path = os.path.abspath(nc_path)
        
        # Read required values from NetCDF file
        nc_dataset = netCDF4.Dataset(nc_path)
        
        try:
            uuid = nc_dataset.uuid
        except:
            raise Exception('UUID not found in %s' % nc_path)
        
        try:
            doi = nc_dataset.doi
        except:
            raise Exception('DOI not found in %s' % nc_path)
        nc_dataset.close()
        
        print 'Processing Dataset %s with UUID %s' % (nc_path, uuid)
        
        nc_distribution_dict = self.thredds_catalog.find_url_dict(nc_path)
        assert nc_distribution_dict, 'No THREDDS endpoints found for %s' % nc_path

        zip_path = os.path.splitext(nc_path)[0] + '.zip'
        zip_distribution_dict = self.thredds_catalog.find_url_dict(zip_path) # Optional - could be an empty dict
#        assert nc_distribution_dict, 'No THREDDS endpoints found for %s' % zip_path
        
        thredds_catalog_list = self.thredds_catalog.find_catalogs(nc_path)
        assert thredds_catalog_list, 'No THREDDS catalogue found for %s' % nc_path
        
        template_dict = {
                         'UUID': uuid,
                         'DOI': doi,
                         'THREDDS_CATALOG_URL': thredds_catalog_list[0], # Should be one - fail otherwise
                         'NC_HTTP_URL': nc_distribution_dict.get('HTTPServer'),
                         'NCSS_URL': nc_distribution_dict.get('NetcdfSubset'),
                         'OPENDAP_URL': nc_distribution_dict.get('OPENDAP'),
                         'WCS_URL': nc_distribution_dict.get('WCS'),
                         'WMS_URL': nc_distribution_dict.get('WMS'),
                         'ZIP_HTTP_URL': zip_distribution_dict.get('HTTPServer'),
                         }
#        print template_dict
    
        # Need to read namespace info from main XML first
        xml_text = get_xml_by_id(self.GA_GEONETWORK, uuid)
        try:
            xml_tree = etree.fromstring(xml_text)
        except Exception, e:
            print xml_text
            raise e
        
        # Read XML template file
        distributionInfo_template_file = open('distributionInfo_template.xml')
        distributionInfo_template_text = distributionInfo_template_file.read()
        distributionInfo_template_file.close()
        
        # Perform any global substitutions
        distributionInfo_template_text.replace('sales@ga.gov.au', 'clientservices@ga.gov.au')

        # Perform specialised text substitutions
        for key in sorted(template_dict.keys()):
            if template_dict[key] is None:
                print 'WARNING: %s not set in template XML' % key
            else:
                distributionInfo_template_text = re.sub('%%%s%%' % key, template_dict[key], distributionInfo_template_text)   
                
#        print distributionInfo_template_text        
        distributionInfo_template_tree = etree.fromstring(distributionInfo_template_text).find(path='mdb:distributionInfo', namespaces=xml_tree.nsmap)
        
        # Purge any distributionFormat with un-substituted expressions
        MD_Distribution_tree = distributionInfo_template_tree.find(path='mrd:MD_Distribution', namespaces=xml_tree.nsmap)
        for distributionFormat_tree in MD_Distribution_tree.iterfind(path='mrd:distributionFormat', namespaces=xml_tree.nsmap):
            for text in distributionFormat_tree.itertext():
                if re.search('%.*%', text):
                    print 'Removing incomplete distributionFormat %s' % distributionFormat_tree.tag
                    MD_Distribution_tree.remove(distributionFormat_tree)
                    break
        
        distributionInfo_tree = xml_tree.find(path='mdb:distributionInfo', namespaces=xml_tree.nsmap)
        if distributionInfo_tree is None:
            print 'Creating new distributionInfo element from template'
            xml_tree.append(distributionInfo_template_tree)
        else:
            print 'Replacing existing distributionInfo element with template'
            xml_tree.replace(distributionInfo_tree, distributionInfo_template_tree)
        
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
    

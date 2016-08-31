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
    #GA_GEONETWORK = 'http://ecat.ga.gov.au/geonetwork/srv/eng' # GA's externally-facing GeoNetwork - DO NOT USE!!!
    GA_GEONETWORK = 'http://localhost:8081/geonetwork/srv/eng' # GA's internal GeoNetwork via port forward
    THREDDS_ROOT_DIR = '/g/data1/rr2/'
    
    THREDDS_CATALOG_URL = 'http://dapds00.nci.org.au/thredds/catalogs/rr2/catalog.html'
    print 'thredds_catalog_url = %s' % THREDDS_CATALOG_URL
    
    def __init__(self):
    
        #TODO: Work out some way of making this faster.
        def get_thredds_catalog(thredds_catalog_url):
            '''
            Function to return a THREDDSCatalog either from a pre-cached YAML file or read from specified THREDDS catalog
            '''
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
        '''
        Function to read, update and write XML metadata for specified NetCDF file
        N.B: Requires UUID & DOI global attributes to be pre-populated in NetCDF file
        Currently creates or replaces distributionInfo element using template XML file
        '''
        def get_xml_by_id(geonetwork_url, uuid):
            '''
            Function to return complete, native (ISO19115-3) XML text for metadata record with specified UUID
            '''
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
        source_MD_Distribution_tree = distributionInfo_template_tree.find(path='mrd:MD_Distribution', namespaces=xml_tree.nsmap)
        for distributionFormat_tree in source_MD_Distribution_tree.iterfind(path='mrd:distributionFormat', namespaces=xml_tree.nsmap):
            for text in distributionFormat_tree.itertext():
                if re.search('%.*%', text):
                    print 'Removing incomplete distributionFormat %s' % distributionFormat_tree.tag
                    source_MD_Distribution_tree.remove(distributionFormat_tree)
                    break
        
        # Create or replace distributionInfo element
        distributionInfo_tree = xml_tree.find(path='mdb:distributionInfo', namespaces=xml_tree.nsmap)
        if distributionInfo_tree is None:
            print 'Creating new distributionInfo element from template'
            xml_tree.append(distributionInfo_template_tree)
        else:
            print 'Replacing existing distributionFormat elements from template'
#            xml_tree.replace(distributionInfo_tree, distributionInfo_template_tree)
            distribution_tree = distributionInfo_tree.find(path='mrd:MD_Distribution', namespaces=xml_tree.nsmap)
            assert distribution_tree is not None, 'Destination mrd:MD_Distribution not found'
            
            for source_distributionFormat_tree in source_MD_Distribution_tree.iterfind(path='mrd:distributionFormat', namespaces=xml_tree.nsmap): 
                source_OnlineResource_tree = source_distributionFormat_tree.find(path='.//cit:CI_OnlineResource', namespaces=xml_tree.nsmap)
                assert source_OnlineResource_tree is not None, 'Unable to find source cit:CI_OnlineResource'
                
                source_protocol = source_OnlineResource_tree.find('cit:protocol', namespaces=xml_tree.nsmap).find('gco:CharacterString', namespaces=xml_tree.nsmap).text
                source_linkage = source_OnlineResource_tree.find('cit:linkage', namespaces=xml_tree.nsmap).find('gco:CharacterString', namespaces=xml_tree.nsmap).text
                match = re.match('(\w+)://([^/]+)((/[^/\?]+){0,2}).*/([^/]+)$', source_linkage)
                if match is None:
                    print 'Unable to parse %s' % source_linkage
                    continue

                source_link_protocol = match.group(1)
                source_host = match.group(2)
                source_dir = match.group(3)
                source_file = match.group(5)

                print 'Processing %s: protocol=%s, link_protocol=%s, host=%s, root=%s, file=%s' % (source_linkage, source_protocol, source_link_protocol, source_host, source_dir, source_file)
                
                # Check all distributions for match
                match_found = False
                for dest_distributionFormat_tree in distribution_tree.iterfind(path='mrd:distributionFormat', namespaces=xml_tree.nsmap):
                    dest_OnlineResource_tree = dest_distributionFormat_tree.find(path='.//cit:CI_OnlineResource', namespaces=xml_tree.nsmap)
                    assert dest_OnlineResource_tree is not None, 'Unable to find destination cit:CI_OnlineResource'
                
                    dest_protocol = dest_OnlineResource_tree.find('cit:protocol', namespaces=xml_tree.nsmap).find('gco:CharacterString', namespaces=xml_tree.nsmap).text
                    dest_linkage = dest_OnlineResource_tree.find('cit:linkage', namespaces=xml_tree.nsmap).find('gco:CharacterString', namespaces=xml_tree.nsmap).text
                    match = re.match('(\w+)://([^/]+)((/[^/\?]+){0,2}).*/([^/]+)$', dest_linkage)
                    if match is None:
                        print 'Unable to parse %s' % dest_linkage
                        continue

                    dest_link_protocol = match.group(1)
                    dest_host = match.group(2)
                    dest_dir = match.group(3)
                    dest_file = match.group(5)
                    
#                    print 'Checking %s: protocol=%s, link_protocol=%s, host=%s, root=%s, file=%s' % (dest_linkage, dest_protocol, dest_link_protocol, dest_host, dest_dir, dest_file)

                    # Determine match based on protocol, host and file
                    match_found = (((source_protocol == dest_protocol) and 
                                    (source_link_protocol == dest_link_protocol) and 
                                    (source_host == dest_host) and 
                                    (source_dir == dest_dir) and
                                    (source_file == dest_file)) or
                                  ((re.search('thredds/.*[c|C]atalog', source_dir) is not None) and # Special case for THREDDS catalog page
                                   (re.search('thredds/.*[c|C]atalog', dest_dir) is not None) and
                                   (source_protocol == dest_protocol) and 
                                   (source_link_protocol == dest_link_protocol) and 
                                   (source_file == dest_file)))
                    
                    if match_found: # Update existing distribution
                        print 'Match found %s: protocol=%s, link_protocol=%s, host=%s, dir=%s, file=%s' % (dest_linkage, dest_protocol, dest_link_protocol, dest_host, dest_dir, dest_file)
                        distribution_tree.replace(dest_distributionFormat_tree, source_distributionFormat_tree)
                        break
                     
                if not match_found: # Add new distribution
                    print 'No match found. Adding new mrd:distributionFormat subtree for %s' % source_linkage
                    distribution_tree.append(source_distributionFormat_tree)   

        
        xml_path = os.path.abspath(os.path.join(self.XML_DIR, '%s.xml' % uuid))
        xml_file = open(xml_path, 'w')
        
        xml_file.write(etree.tostring(xml_tree, pretty_print=True))
        
        xml_file.close()
        print 'Finished writing XML to file %s' % xml_path
    
def main():
    assert len(sys.argv) > 1, 'Usage: %s <netcdf_file> [<netcdf_file>...]' % sys.argv[0]        
        
    xml_updater = XMLUpdater()
    
    for nc_path in sys.argv[1:]:
        try:
            xml_updater.update_xml(nc_path)
        except Exception, e:
            print 'XML update failed for %s:\n%s' % (nc_path, e.message)
        

if __name__ == '__main__':
    main()   
    

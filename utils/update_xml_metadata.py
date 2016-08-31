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
        
        def update_bounds(nc_dataset, xml_tree):
            '''
            Read the following ACDD global attributes from the NetCDF file:
            
                :geospatial_bounds = "POLYGON((112.502532442 -9.0256618335, 154.662515579 -9.0256618335, 154.662515579 -43.9289812055, 112.502532442 -43.9289812055, 112.502532442 -9.0256618335))" ;
                :geospatial_bounds_crs = "GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\",SPHEROID[\"WGS 84\",6378137,298.257223563,AUTHORITY[\"EPSG\",\"7030\"]],AUTHORITY[\"EPSG\",\"6326\"]],PRIMEM[\"Greenwich\",0,AUTHORITY[\"EPSG\",\"8901\"]],UNIT[\"degree\",0.0174532925199433,AUTHORITY[\"EPSG\",\"9122\"]],AUTHORITY[\"EPSG\",\"4326\"]]" ;
                :geospatial_lat_max = -9.0256618335 ;
                :geospatial_lat_min = -43.9289812055 ;
                :geospatial_lat_resolution = 0.000833332999995662 ;
                :geospatial_lat_units = "degrees_north" ;
                :geospatial_lon_max = 154.6625155785 ;
                :geospatial_lon_min = 112.5025324425 ;
                :geospatial_lon_resolution = 0.000833332999974346 ;
                :geospatial_lon_units = "degrees_east" ;
            
            then populate the following XML elements:  
              
                  <mri:extent>
                    <gex:EX_Extent>
                      <gex:description>
                        <gco:CharacterString>unknown</gco:CharacterString>
                      </gex:description>
                      <gex:geographicElement>
                        <gex:EX_GeographicBoundingBox>
                          <gex:westBoundLongitude>
                            <gco:Decimal>112.5</gco:Decimal>
                          </gex:westBoundLongitude>
                          <gex:eastBoundLongitude>
                            <gco:Decimal>154.7</gco:Decimal>
                          </gex:eastBoundLongitude>
                          <gex:southBoundLatitude>
                            <gco:Decimal>-43.9</gco:Decimal>
                          </gex:southBoundLatitude>
                          <gex:northBoundLatitude>
                            <gco:Decimal>-9</gco:Decimal>
                          </gex:northBoundLatitude>
                        </gex:EX_GeographicBoundingBox>
                      </gex:geographicElement>
                    </gex:EX_Extent>
                  </mri:extent>
                
            '''
            # Create or replace distributionInfo element
            source_extent_tree = etree.fromstring('''
                  <mri:extent>
                    <gex:EX_Extent>
                      <gex:description>
                        <gco:CharacterString>unknown</gco:CharacterString>
                      </gex:description>
                      <gex:geographicElement>
                        <gex:EX_GeographicBoundingBox>
                          <gex:westBoundLongitude>
                            <gco:Decimal>%f</gco:Decimal>
                          </gex:westBoundLongitude>
                          <gex:eastBoundLongitude>
                            <gco:Decimal>%f</gco:Decimal>
                          </gex:eastBoundLongitude>
                          <gex:southBoundLatitude>
                            <gco:Decimal>%f</gco:Decimal>
                          </gex:southBoundLatitude>
                          <gex:northBoundLatitude>
                            <gco:Decimal>%f</gco:Decimal>
                          </gex:northBoundLatitude>
                        </gex:EX_GeographicBoundingBox>
                      </gex:geographicElement>
                    </gex:EX_Extent>
                  </mri:extent>
                  ''' % (nc_dataset.geospatial_lon_min,
                         nc_dataset.geospatial_lon_max,
                         nc_dataset.geospatial_lat_min,
                         nc_dataset.geospatial_lat_max,
                         )
                  )

            
            dest_MD_DataIdentification_tree = xml_tree.find(path='mri:MD_DataIdentification', namespaces=xml_tree.nsmap)
            assert dest_MD_DataIdentification_tree is not None, 'dest_MD_DataIdentification_tree element does not exist'
            
            dest_extent_tree = dest_MD_DataIdentification_tree.find(path='mri:extent', namespaces=xml_tree.nsmap)
            if dest_extent_tree is None:
                print 'Creating new mri:extent subtree'
                dest_MD_DataIdentification_tree.append(source_extent_tree)
            else:
                print 'Replacing existing mri:extent subtree'
                dest_MD_DataIdentification_tree.replace(dest_extent_tree, source_extent_tree)
            return           
        
        
        def update_distributions(xml_tree):
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
            source_distributionInfo_tree = etree.fromstring(distributionInfo_template_text).find(path='mdb:distributionInfo', namespaces=xml_tree.nsmap)
            
            # Purge any distributionFormat with un-substituted expressions
            source_MD_Distribution_tree = source_distributionInfo_tree.find(path='mrd:MD_Distribution', namespaces=xml_tree.nsmap)
            for source_distributionFormat_tree in source_MD_Distribution_tree.iterfind(path='mrd:distributionFormat', namespaces=xml_tree.nsmap):
                for text in source_distributionFormat_tree.itertext():
                    if re.search('%.*%', text):
                        print 'Removing incomplete distributionFormat %s from updated template XML' % source_distributionFormat_tree.tag
                        source_MD_Distribution_tree.remove(source_distributionFormat_tree)
                        break
            
            # Create or replace distributionInfo element
            dest_distributionInfo_tree = xml_tree.find(path='mdb:distributionInfo', namespaces=xml_tree.nsmap)
            if dest_distributionInfo_tree is None:
                print 'Creating new distributionInfo subtree from template'
                xml_tree.append(source_distributionInfo_tree)
            else:
    #            xml_tree.replace(dest_distributionInfo_tree, distributionInfo_template_tree)
                dest_MD_Distribution_tree = dest_distributionInfo_tree.find(path='mrd:MD_Distribution', namespaces=xml_tree.nsmap)
                if dest_MD_Distribution_tree is None: # Destination mrd:MD_Distribution not found
                    print 'Creating new mrd:MD_Distribution subtree from template'
                    dest_distributionInfo_tree.append(source_MD_Distribution_tree)
                else:
                    print 'Adding or replacing individual mrd:distributionFormat subtrees from template'
                    source_distributionFormat_count = 0
                    replaced_distributionFormat_count = 0
                    new_distributionFormat_count = 0
                    
                    for source_distributionFormat_tree in source_MD_Distribution_tree.iterfind(path='mrd:distributionFormat', namespaces=xml_tree.nsmap):
                        source_distributionFormat_count += 1 
                        source_OnlineResource_tree = source_distributionFormat_tree.find(path='.//cit:CI_OnlineResource', namespaces=xml_tree.nsmap)
                        assert source_OnlineResource_tree is not None, 'Unable to find source cit:CI_OnlineResource under mrd:distributionFormat'
                        
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
        
    #                    print 'Processing %s: protocol=%s, link_protocol=%s, host=%s, root=%s, file=%s' % (source_linkage, source_protocol, source_link_protocol, source_host, source_dir, source_file)
                        
                        # Check all distributions for match
                        distribution_match_found = False
                        for dest_distributionFormat_tree in dest_MD_Distribution_tree.iterfind(path='mrd:distributionFormat', namespaces=xml_tree.nsmap):
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
                            
    #                        print 'Checking %s: protocol=%s, link_protocol=%s, host=%s, root=%s, file=%s' % (dest_linkage, dest_protocol, dest_link_protocol, dest_host, dest_dir, dest_file)
        
                            # Determine match based on protocol, host and file
                            distribution_match_found = (((source_protocol == dest_protocol) and 
                                            (source_link_protocol == dest_link_protocol) and 
                                            (source_host == dest_host) and 
                                            (source_dir == dest_dir) and
                                            (source_file == dest_file)) 
                                           or
                                          ((re.search('thredds/.*[c|C]atalog', source_dir) is not None) and # Special case for THREDDS catalog page
                                           (re.search('thredds/.*[c|C]atalog', dest_dir) is not None) and
                                           (source_protocol == dest_protocol) and 
                                           (source_link_protocol == dest_link_protocol) and 
                                           (source_file == dest_file)))
                            
                            if distribution_match_found: # Update existing distribution
    #                            print 'Match found %s: protocol=%s, link_protocol=%s, host=%s, dir=%s, file=%s' % (dest_linkage, dest_protocol, dest_link_protocol, dest_host, dest_dir, dest_file)
                                dest_MD_Distribution_tree.replace(dest_distributionFormat_tree, source_distributionFormat_tree)
                                replaced_distributionFormat_count += 1
                                break
                             
                        if not distribution_match_found: # Add new distribution
    #                        print 'No match found. Adding new mrd:distributionFormat subtree for %s' % source_linkage
                            dest_MD_Distribution_tree.append(source_distributionFormat_tree)   
                            new_distributionFormat_count += 1
        
            print '%d complete distributions from template. %d replaced and %d added. %d final distributions' % (source_distributionFormat_count,
                                                                                                               replaced_distributionFormat_count,
                                                                                                               new_distributionFormat_count,
                                                                                                               len(dest_MD_Distribution_tree)
                                                                                                               )

        
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
        
        print 'Processing Dataset %s with UUID %s' % (nc_path, uuid)

        xml_text = get_xml_by_id(self.GA_GEONETWORK, uuid)
        try:
            xml_tree = etree.fromstring(xml_text)
        except Exception, e:
            print xml_text
            raise e
        
        update_bounds(nc_dataset, xml_tree)
        nc_dataset.close()
        
        update_distributions(xml_tree)
        
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
    

from _metadata import Metadata, MetadataException
from _mtl_metadata import MTLMetadata
from _report_metadata import ReportMetadata
from _xml_metadata import XMLMetadata
from _ers_metadata import ERSMetadata

def metadata_class(metadata_type_tag):
    metadata_class_map = {'MTL': MTLMetadata,
                          'REPORT': ReportMetadata,
                          'XML': XMLMetadata,
                          'ERS': ERSMetadata,
                          'ISI': ERSMetadata,
                          }
    
    return metadata_class_map.get(metadata_type_tag.trim().upper())
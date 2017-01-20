'''
Created on 20Jan.,2017

@author: Alex
'''
import re
import json
from pprint import pprint

class MetadataText(object):
    '''
    '''
    def __init__(self, template_json_path, metadata_object=None):
        self.attributes = {}
        self.metadata_object = None
        
        template_json_file = open(template_json_path)  
        self.template = {str(key): str(value) for key, value in json.load(template_json_file).iteritems()} # Convert from unicode
        template_json_file.close()
        
        # Find all elements in templates
        element_set = set()
        for attribute_text in self.template.values():
            for s in re.finditer('%%(.+?)%%', attribute_text):
                element_set.add(s.group(1))
        
        self.metadata_dict = {element: None for element in element_set}
        
        if metadata_object:
            self.update_text(metadata_object)
            
    
    def update_text(self, metadata_object):
        self.metadata_object = metadata_object
        
        # Update metadata dict from metadata object
        for element in self.metadata_dict.keys():
            self.metadata_dict[element] = metadata_object.get_metadata(element.split('/')) or 'UNKNOWN'
           
        for attribute_name, attribute_text in self.template.iteritems():
            for s in re.finditer('%%(.+?)%%', attribute_text):
                element = s.group(1)
                attribute_text = attribute_text.replace('%%' + element + '%%', self.metadata_dict[element])
            self.attributes[attribute_name.upper()] = attribute_text

        

        
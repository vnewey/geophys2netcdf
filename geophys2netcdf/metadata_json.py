'''
Created on 28Oct.,2016

@author: Alex Ip
'''
import os
from glob import glob
import subprocess
import re
import json
import logging

from geophys2netcdf.datetime_utils import get_iso_utcnow, get_utc_mtime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Initial logging level for this module


def write_json_metadata(uuid, dataset_folder, excluded_extensions=[]):
    '''
    Function to write UUID, file_paths and current timestamp to .metadata.json
    '''
    assert uuid, 'UUID not set'

    assert os.path.isdir(
        dataset_folder), 'dataset_folder is not a valid directory.'
    dataset_folder = os.path.abspath(dataset_folder)

    json_metadata_path = os.path.join(dataset_folder, '.metadata.json')

    file_list = [file_path for file_path in glob(os.path.join(dataset_folder, '*'))
                 if os.path.splitext(file_path)[1] not in excluded_extensions
                 and os.path.isfile(file_path)]

    md5_output = subprocess.check_output(['md5sum'] + file_list)
    md5_dict = {re.search('^(\w+)\s+(.+)$', line).groups()[1]:
                re.search('^(\w+)\s+(.+)$', line).groups()[0]
                for line in md5_output.split('\n') if line.strip()
                }

    metadata_dict = {'uuid': uuid,
                     'time': get_iso_utcnow(),
                     'folder_path': dataset_folder,
                     'files': [{'file': os.path.basename(filename),
                                'md5': md5_dict[filename],
                                'mtime': get_utc_mtime(filename).isoformat()
                                }
                               for filename in sorted(md5_dict.keys())
                               ]
                     }

    json_output_file = open(json_metadata_path, 'w')
    json.dump(metadata_dict, json_output_file, indent=4)
    json_output_file.close()
    logger.info('Finished writing metadata file %s', json_metadata_path)


def check_json_metadata(uuid, dataset_folder, excluded_extensions=[]):
    '''
    Function to check UUID, file_paths MD5 checksums from .metadata.json
    '''
    assert uuid, 'UUID not set'

    assert os.path.isdir(
        dataset_folder), 'dataset_folder is not a valid directory.'
    dataset_folder = os.path.abspath(dataset_folder)

    json_metadata_path = os.path.join(dataset_folder, '.metadata.json')

    json_metadata_file = open(json_metadata_path, 'r')
    metadata_dict = json.load(json_metadata_file)
    json_metadata_file.close()

    report_list = []

    if metadata_dict['uuid'] != uuid:
        report_list.append('UUID Changed from %s to %s' % (
            metadata_dict['uuid'], uuid))

    if metadata_dict['folder_path'] != dataset_folder:
        report_list.append('Dataset folder Changed from %s to %s' % (
            metadata_dict['folder_path'], dataset_folder))

    file_list = [file_path for file_path in glob(os.path.join(dataset_folder, '*'))
                 if os.path.splitext(file_path)[1] not in excluded_extensions
                 and os.path.isfile(file_path)]

    md5_output = subprocess.check_output(['md5sum'] + file_list)
    calculated_md5_dict = {os.path.basename(re.search('^(\w+)\s+(.+)$', line).groups()[1]):
                           re.search('^(\w+)\s+(.+)$', line).groups()[0]
                           for line in md5_output.split('\n') if line.strip()
                           }

    saved_md5_dict = {file_dict['file']:
                      file_dict['md5']
                      for file_dict in metadata_dict['files']
                      }

    for saved_filename, saved_md5sum in saved_md5_dict.items():
        calculated_md5sum = calculated_md5_dict.get(saved_filename)
        if not calculated_md5sum:
            new_filenames = [new_filename for new_filename, new_md5sum in calculated_md5_dict.items(
            ) if new_md5sum == saved_md5sum]
            if new_filenames:
                report_list.append('File %s has been renamed to %s' % (
                    saved_filename, new_filenames[0]))
            else:
                report_list.append(
                    'File %s does not exist' % saved_filename)
        else:
            if saved_md5sum != calculated_md5sum:
                report_list.append('MD5 Checksum for file %s has changed from %s to %s' % (
                    saved_filename, saved_md5sum, calculated_md5sum))

    if report_list:
        raise Exception('\n'.join(report_list))
    else:
        logger.info(
            'File paths and checksums verified OK in %s', dataset_folder)

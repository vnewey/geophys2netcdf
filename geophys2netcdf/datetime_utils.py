'''
Created on 28Oct.,2016

@author: Alex Ip
'''

import os
import dateutil.parser
from datetime import datetime
from dateutil import tz
import pytz
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Initial logging level for this module


def read_iso_datetime_string(iso_datetime_string):
    '''
    Helper function to convert an ISO datetime string into a Python datetime object
    '''
    if not iso_datetime_string:
        return None

    try:
        iso_datetime = dateutil.parser.parse(iso_datetime_string)
    except ValueError as e:
        logger.warning(
            'WARNING: Unable to parse "%s" into ISO datetime (%s)', iso_datetime_string, e.message)
        iso_datetime = None

    return iso_datetime


def get_iso_utcnow(utc_datetime=None):
    '''
    Helper function to return an ISO string representing a UTC date/time. Defaults to current datetime.
    '''
    return (utc_datetime or datetime.utcnow()).replace(
        tzinfo=tz.gettz('UTC')).isoformat()


def get_utc_mtime(file_path):
    '''
    Helper function to return the UTC modification time for a specified file
    '''
    assert file_path and os.path.exists(
        file_path), 'Invalid file path "%s"' % file_path
    return datetime.fromtimestamp(os.path.getmtime(file_path), pytz.utc)

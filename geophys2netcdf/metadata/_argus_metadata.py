#!/usr/bin/env python

"""Argus Metadata module

Author: Alex Ip (alex.ip@ga.gov.au)
Written: 5/7/2016
"""
# TODO: Check potential issues with unicode vs str

import logging
import cx_Oracle
import sys
from pprint import pprint

from geophys2netcdf.metadata import Metadata

logger = logging.getLogger('root.' + __name__)


class ArgusMetadata(Metadata):
    """Subclass of Metadata to manage Argus data
    """
    
    # Murray's Argus query
    ARGUS_QUERY = '''SELECT
       TO_NUMBER(regexp_substr(A.SURVEYS.SURVEYID, '^\d+$')),
       A.SURVEYS.SURVEYNAME,
       A.SURVEYS.STATE,
       A.SURVEYS.OPERATOR,
       A.SURVEYS.CONTRACTOR,
       A.SURVEYS.PROCESSOR,
       DECODE(ARGUS.AIRSURVEYS.SURVEY_TYPE,'DETL','Detailed',
                                'NGMA','NGMA',
                                'REGN','Regional',
                                'SEMI-DETL','Semi-detailed',
                                ARGUS.AIRSURVEYS.SURVEY_TYPE) as SURVEY_TYPE,
        A.SURVEYS.DATATYPES,
        A.SURVEYS.VESSEL,
        DECODE(A.SURVEYS.VESSEL_TYPE,'FW', 'Plane',
                           'RW', 'Helicopter',
                           'FW/RW', 'Plane and Helicopter',
                           A.SURVEYS.VESSEL_TYPE) as VESSEL_TYPE,
        A.SURVEYS.RELEASEDATE,
        A.SURVEYS.ON_OFF || 'shore' as ONSHORE_OFFSHORE,
        A.SURVEYS.STARTDATE,
        A.SURVEYS.ENDDATE,
        A.SURVEYS.WLONG,
        A.SURVEYS.ELONG,
        A.SURVEYS.SLAT,
        A.SURVEYS.NLAT,
        ARGUS.AIRSURVEYS.LINE_KM,
        ARGUS.AIRSURVEYS.TOT_KM as TOTAL_KM,
        A.SURVEYS.SPACEMIN as LINE_SPACING,
        ARGUS.AIRSURVEYS.LINE_DIR AS LINE_DIRECTION,
        ARGUS.AIRSURVEYS.TIE_SPG as TIE_SPACING,
        ARGUS.AIRSURVEYS.AREA as SQUARE_KM,
        ARGUS.AIRRAD.XT_VOL as CRYSTAL_VOLUME,
        ARGUS.AIRRAD.XT_VUP as UP_CRYSTAL_VOLUME,
        ARGUS.AIRSURVEYS.DIGITAL_DATA,
        A.SURVEYS.GEODETIC_DATUM,
        ARGUS.AIRSURVEYS.ASL,
        ARGUS.AIRSURVEYS.AGL
from a.surveys
join a.entities using (eno)
join a.entity_types using (entity_type)
join argus.airsurveys using (eno)
left join argus.airdem using (eno)
left join argus.airmag using (eno)
left join argus.airrad using (eno)
--left join argus.survey_remarks on A.SURVEYS.SURVEYID = argus.survey_remarks.SURVEYID
where TO_NUMBER(regexp_substr(A.SURVEYS.SURVEYID, '^\d+$')) = :SURVEYID
--order by TO_NUMBER(A.SURVEYS.SURVEYID)'''
    

        # Class variable holding metadata type string
    _metadata_type_id = 'Argus'
    _filename_pattern = None  # Default RegEx for finding metadata file.

    def __init__(self, db_user, db_password, db_alias, source=None):
        """Instantiates ArgusMetadata object. Overrides Metadata method
        """
        self._metadata_dict = {}

        self.argus_fields = None
                
        self.connection = cx_Oracle.connect('%s/%s@%s' % (db_user, db_password, db_alias))
        self.cursor = self.connection.cursor()
        
        self.cursor.prepare(ArgusMetadata.ARGUS_QUERY)

        if source:
            try: # source is an integer survey_id
                self.read_Argus_metadata(int(source))
            except:
                if isinstance(source, dict):
                    self._metadata_dict = source

    def read_Argus_metadata(self, survey_id):
        '''Read metadata from Argus query
        '''
        query_result = self.cursor.execute(None, {'SURVEYID': survey_id})
        
        if not self.argus_fields:
            self.argus_fields = [field_desc[0] for field_desc in query_result.description]
            
        argus_record = query_result.fetchone()
        self._metadata_dict = dict(zip(self.argus_fields, [str(field) for field in argus_record]))
        
        assert not query_result.fetchone(), 'Multiple records returned for SURVEYID = %d' % survey_id

    def read_file(self, filename=None):
        '''
        Function to read Argus metadata from query and store the results in self._metadata_dict
        Only included for compatibility with file-based metadata
        Argument:
            filename: Argus survey_id to query
        Returns:
            nested dict containing metadata

        '''
        logger.debug('read_file(%s) called', filename)

        survey_id = int(filename) or int(self._filename)
        assert survey_id, 'Survey ID must be specified'

        logger.debug('Reading metadata from Argus query with survey ID %d', survey_id)

        self.read_Argus_metadata(survey_id)
        self._filename = filename

        return self._metadata_dict

    def write_file(self, filename=None, save_backup=False):
        """Function write the metadata contained in self._metadata_dict to an Argus file
        Argument:
            filename: Metadata file to be written
        """
        assert False, 'Argus metadata is read-only'


def main():
    '''
    Main function for quick and dirty testing
    '''
    am = ArgusMetadata(*sys.argv[1:])
    pprint(am.metadata_dict)

if __name__ == '__main__':
    main()

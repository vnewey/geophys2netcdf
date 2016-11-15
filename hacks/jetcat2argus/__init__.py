import os
import yaml
import cx_Oracle
from collections import OrderedDict

class JetCat2Argus(object):
    '''Class definition for JetCat2Argus
    '''
    
    # Murray's Argus query
    ARGUS_QUERY = '''SELECT
       A.SURVEYS.SURVEYID,
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
where regexp_like(A.SURVEYS.SURVEYID, '^[0-9]+$')
--and TO_NUMBER(A.SURVEYS.SURVEYID) in (0029, 0062, 0146, 0165, 0198, 0204, 0223, 0228, 0234, 0250, 0274, 0309, 0325, 0344, 0346, 0382, 0391, 0399, 0402, 0410, 0427, 0428, 0431, 0432, 0433, 0450, 0463, 0479, 0481, 0482, 0484, 0497, 0507, 0509, 0510, 0515, 0516, 0520, 0522, 0528, 0539, 0542, 0549, 0564, 0565, 0566, 0567, 0569, 0570, 0591, 0599, 0606, 0611, 0624, 0643, 0660, 0667, 0690, 0695, 0699, 0700, 0701, 0702, 0703, 0704, 0705, 0706, 0707, 0708, 0709, 0710, 0711, 0712, 0713, 0714, 0715, 0716, 0717, 0718, 0719, 0720, 0721, 0722, 0726, 0730, 0741, 0745, 0750, 0751, 0757, 0761, 0764, 0767, 0769, 0779, 0783, 0786, 0788, 0790, 0807, 0817, 0819, 0826, 0829, 0830, 0850, 0852, 0853, 0854, 0862, 0863, 0872, 0913, 0931, 1017, 1018, 1022, 1023, 1035, 1039, 1041, 1045, 1059, 1062, 1063, 1091, 1112, 1113, 1125, 1126, 1135, 1150, 1151, 1153, 1177, 1210, 1213, 1215, 1217, 1224, 1226, 1227, 1234, 1236, 1240, 1244, 1245, 1255, 1258, 1259, 1260, 1262, 1557, 2002, 2018, 2023)
order by TO_NUMBER(A.SURVEYS.SURVEYID)'''
    
    JETCAT_FIELDS = OrderedDict([
        ('NAME', None), # Dataset name - primary key  
        ('LON1', 'A.SURVEYS.ELONG'),   
        ('LAT1', 'A.SURVEYS.SLAT'),   
        ('LON2', 'A.SURVEYS.WLONG'),   
        ('LAT2', 'A.SURVEYS.SLAT'),   
        ('LON3', 'A.SURVEYS.WLONG'),   
        ('LAT3', 'A.SURVEYS.NLAT'),   
        ('LON4', 'A.SURVEYS.ELONG'),   
        ('LAT4', 'A.SURVEYS.NLAT'),   
        ('CS', None),   
        ('THEME', None),   
        ('DATATYPE', None),   
        ('KSIZE', None),   
        ('DODS_URL', None),   
        ('LABEL', None),   
        ('DATE', None),   
        ('CELLSIZE', None),   
        ('FLAVOUR', None),   
        ('LINESPACING', 'A.SURVEYS.SPACEMIN'),   
        ('Surveyid', 'A.SURVEYS.SURVEYID'),   
        ('CSDATA', None),   
        ('LICENCENO', None),   
        ('CELLSIZE_M', None),   
        ])
    
    THEME_MAP = {'ELEVATION': 'ELEV',
              'GRAVITY': 'GRAV',
              'MAGNETICS': 'MAG',
              'RADIOMETRICS': 'RAD',
              }

    
    def __init__(self, jetcat_path, db_alias, db_user, db_password, output_path):
        '''Constructor for JetCat2Argus
        '''
        self.argus_fields = None
                
        self.jetcat_path = jetcat_path
        self.output_path = output_path
        
        self.jetcat_records = self.read_jetcat_file(self.jetcat_path)
        
        self.connection = cx_Oracle.connect('%s/%s@%s' % (db_user, db_password, db_alias))
        self.cursor = self.connection.cursor()
        self.cursor.prepare(JetCat2Argus.ARGUS_QUERY)
        
        self.argus_records = self.get_argus_records();
        
        self.connection.close()
    
    
    def read_jetcat_file(self, jetcat_path): 
        jetcat_records = {}   
        jetcat_file = open(self.jetcat_path)
        header_list = None
        for line in jetcat_file:
            line = line.replace('\n', '')
            values = line.split('\t')
            
            if header_list is None:
                header_list = values
                assert header_list == JetCat2Argus.JETCAT_FIELDS.keys(), 'Invalid JetCat file format'
                continue
            
            jetcat_records[values[JetCat2Argus.JETCAT_FIELDS.keys().index('NAME')]] = values
            
        return jetcat_records
    

    def print_combined_records(self):
        
        argus_with_jetcat = []
        
        print '\t'.join(['JETCAT_' + key for key in JetCat2Argus.JETCAT_FIELDS.keys()] + 
                        ['ARGUS_' + key for key in self.argus_fields])
        
        for jetcat_name in sorted(self.jetcat_records.keys()):
            jetcat_record = self.jetcat_records[jetcat_name]
            
            survey_id = jetcat_record[JetCat2Argus.JETCAT_FIELDS.keys().index('Surveyid')]
            
            argus_record = self.argus_records.get(survey_id)
            self.print_combined_record(jetcat_record, argus_record)
            
            if argus_record:
                argus_with_jetcat.append(survey_id)
                
        # Print Argus records without jetcat records
        for survey_id in sorted(self.argus_records.keys()):
            if survey_id not in argus_with_jetcat:
                jetcat_record = None
                argus_record = self.argus_records[survey_id]
                self.print_combined_record(jetcat_record, argus_record)
        
    def print_combined_record(self, jetcat_record=None, argus_record=None):
        assert jetcat_record or argus_record, 'Must supply either jetcat_record, argus_record or both'
        
        if jetcat_record is None:
            jetcat_record = tuple([None for _field in JetCat2Argus.JETCAT_FIELDS.keys()])
        
        if argus_record is None:
            argus_record = tuple([None for _field in self.argus_fields])
        
        print '\t'.join([str(value) if value is not None else '' 
                         for value in (list(jetcat_record) + list(argus_record))]
                        )
        
        
    def get_argus_records(self):
        '''Function to return a dict of all argus records keyed by survey_id'''
        
        argus_path = 'argus.yaml'
        
        if os.path.isfile(argus_path): # Cache file exists
            argus_file = open(argus_path, 'r')
            argus_records = yaml.load(argus_file)
            argus_file.close()
        else: # Use DB query
            argus_records = {}
        
            query_result = self.cursor.execute(None)
            
            if not self.argus_fields:
                self.argus_fields = [field_desc[0] for field_desc in query_result.description]
                
            for argus_record in query_result:
                argus_records[argus_record[self.argus_fields.index('SURVEYID')]] = argus_record
            
            argus_file = open(argus_path, 'w')
            yaml.dump(argus_records, argus_file)
            argus_file.close()

        return argus_records
        


        
        
        
                
    
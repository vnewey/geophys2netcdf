'''
Created on 3Nov.,2016

@author: u76345
'''
import sys
import os
from jetcat2argus import JetCat2Argus

def main():
    assert len(sys.argv) == 5, 'Usage: %s <jetcat_path> <db_alias> <db_user> <db_password>' % sys.argv[0]
    
    jetcat_path = sys.argv[1]
    db_alias = sys.argv[2]
    db_user = sys.argv[3]
    db_password = sys.argv[4]
    
    assert os.path.isfile(jetcat_path), '%s is not a valid file' % jetcat_path
    
    j2a = JetCat2Argus(jetcat_path, db_alias, db_user, db_password)
    j2a.print_combined_records()
    

if __name__ == '__main__':
    main()
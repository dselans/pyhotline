#!/usr/bin/env python
#
# A helper script for creating the initial SQLite client/message database
#

import os
import sys

from pyhotline import _SQL

if len(sys.argv) != 2:
    print "Usage: ./%s db_file" % sys.argv[0]
    sys.exit(1)

db_file = sys.argv[1]

if os.path.exists(db_file):
    overwrite = raw_input("db_file '%s' already exists, overwrite? (y/n) " % db_file)
    if overwrite == 'y':
        os.remove(db_file)
    else:
        print "Databsae installation aborted."
        sys.exit(1)

(status, msg) = _SQL.setupDatabase(db_file)
if not status:
    print "Unable to setup database. Exception: %s" % msg 
    sys.exit(1)
else:
    print "Database setup completed."
    sys.exit(0)

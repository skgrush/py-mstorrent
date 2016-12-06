#!/usr/bin/env python3

import sys
import os
import os.path

SCRIPT_DIR = os.path.dirname(os.path.realpath( __file__ ))
MY_WORKING_DIR = os.getcwd()
WORKING_DIR = os.path.realpath( os.path.join( MY_WORKING_DIR, '..' ) )
SRC_DIR = os.path.realpath(os.path.join( SCRIPT_DIR, '../' ))
sys.path.insert(0, SRC_DIR)

import server
confpath = os.path.join( WORKING_DIR, 'confServer.cfg' )


srv = server.TrackerServer( "localhost", server.TrackerServerHandler,
                            config_file=confpath )


try:
    srv.serve_forever()

except KeyboardInterrupt:
    pass
    
finally:
    srv.shutdown()
    print("Tracker server has shut down")

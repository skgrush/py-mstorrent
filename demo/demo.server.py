#!/usr/bin/env python3
"""py-mstorrent Demo Server Script

Peer 1 Expectations:
 * Started at time = 0
 * continue hosting .track files
"""

import sys
import os
import os.path

from demo_helper import WORKING_DIR, SRC_DIR
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

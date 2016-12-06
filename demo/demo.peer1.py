#!/usr/bin/env python3
"""py-mstorrent Demo Peer 1 Script

Peer 1 Expectations:
 * Started at t=0
 * have a small file named `small.file`
 * create a tracker for the small file
 * continue hosting the small file
 * some time after t=90s, terminate
"""

from demo_helper import START_TIME, WORKING_DIR, MY_WORKING_DIR, SRC_DIR, \
                        PeerDemo, timeout, seconds

import curses
import time
import sys
import os
import os.path

sys.path.insert(0, SRC_DIR)

import peer

confpath = os.path.join( WORKING_DIR, 'confPeers.cfg' )

if not os.path.isdir( 'peerfolder' ):
    os.mkdir( 'peerfolder', mode=0o777 )

#symlink small.file into the peer's upload folder
_smfile_orig_path = os.path.join( WORKING_DIR, 'small.file' )
_smfile_end_path  = os.path.join( MY_WORKING_DIR, 'peerfolder/small.file' )
if os.path.isfile( _smfile_orig_path ):
    os.symlink( _smfile_orig_path, _smfile_end_path )
else:
    raise RuntimeError("Failed to find small.file")

demo = PeerDemo('REQ', 'createtracker small.file "This file is small"')

# built-in delay to let server start up
time.sleep(3)

curses.wrapper(peer.main, demo, confpath)

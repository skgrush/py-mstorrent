#!/usr/bin/env python3
"""py-mstorrent Demo Peer 2 Script

Peer 2 Expectations:
 * Started at t=0
 * have a large file named `large.file`
 * create a tracker for the large file
 * continue hosting the large file
 * some time after t=90s, terminate
"""

from demo_helper import START_TIME, WORKING_DIR, MY_WORKING_DIR, SRC_DIR, PeerDemo

import curses
import sys
import os
import os.path

sys.path.insert(0, SRC_DIR)

import peer

confpath = os.path.join( WORKING_DIR, 'confPeers.cfg' )


#symlink large.file into the peer's upload folder
_lgfile_orig_path = os.path.join( WORKING_DIR, 'large.file' )
_lgfile_end_path  = os.path.join( MY_WORKING_DIR, 'peerfolder/large.file' )
if os.path.isfile( _lgfile_orig_path ):
    os.symlink( _lgfile_orig_path, _lgfile_end_path )
else:
    raise RuntimeError("Failed to find large.file")

demo = Demo('REQ', 'createtracker large.file "This file is LARGE"')

# built-in delay to let server start up
time.sleep(3)

curses.wrapper(peer.main, demo, confpath)

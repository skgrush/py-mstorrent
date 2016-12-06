#!/usr/bin/env python3
"""py-mstorrent Demo Peer N Script, where N>2

Peer 3+ Expectations:
 * Started at t=30s or 90s 
 * issue REQ command
 * GET both small.file and large.file
"""

from demo_helper import START_TIME, WORKING_DIR, MY_WORKING_DIR, SRC_DIR, PeerDemo

import curses
import sys
import os
import os.path

sys.path.insert(0, SRC_DIR)

import peer

confpath = os.path.join( WORKING_DIR, 'confPeers.cfg' )

if not os.path.isdir( 'peerfolder' ):
    os.mkdir( 'peerfolder', mode=0o777 )

demo = PeerDemo('REQ', 'gettracker large.file', 'gettracker small.file')

curses.wrapper(peer.main, demo, confpath)

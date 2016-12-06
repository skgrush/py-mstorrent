#!/usr/bin/env python3
"""py-mstorrent Demo Helper Script"""

import time
import sys
import os
import os.path

START_TIME = time.time()
SCRIPT_DIR = os.path.dirname(os.path.realpath( __file__ ))
MY_WORKING_DIR = os.getcwd()
WORKING_DIR = os.path.realpath( os.path.join( MY_WORKING_DIR, '..' ) )
SRC_DIR = os.path.realpath(os.path.join( SCRIPT_DIR, '../' ))

class PeerDemo:
    cmds = []
    
    def __init__(self, *cmdlist):
        self.cmds = cmdlist
    
    def run(self, cl):
        for cmd in self.cmds:
            time.sleep(1)
            cl.command(cmd)


def waiter(waitTil, inc=5):
    
    last = 0
    
    while( 

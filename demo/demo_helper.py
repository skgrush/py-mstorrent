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


def seconds():
    return int( time.time() - START_TIME )


def waiter(waitTil, inc=5):
    """wait until *waitTil* seconds after START_TIME."""
    
    target = time.time() + waitTil
    last = 0
    
    while( time.time() < target ):
        diff = target - time.time()
        t = time.time() - START_TIME
        
        if inc < t - last:
            print("t = {} sec".format(int(t)))
        
        if diff < inc:
            time.sleep( diff )
            return
        else:
            time.sleep(1)
            continue


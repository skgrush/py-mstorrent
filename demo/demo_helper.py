#!/usr/bin/env python3
"""py-mstorrent Demo Helper Script"""

import signal
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
    
    target = START_TIME + waitTil
    last = 0
    
    while( time.time() < target ):
        diff = target - time.time()
        
        if inc < seconds() - last:
            print("t = {} sec".format(seconds()))
            last = seconds()
        
        if diff < inc:
            time.sleep( diff )
            return
        else:
            time.sleep(1)
            continue

class timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)

#!/usr/bin/env python3
"""

Peer 1 Expectations:
 * Started at time = 0
 * have a small file named `small.file`
 * create a tracker for the small file
 * continue hosting the small file
"""

import subprocess
import time

import sys
import os
import os.path

START_TIME = time.time()
SCRIPT_DIR = os.path.dirname(os.path.realpath( __file__ ))
MY_WORKING_DIR = os.getcwd()
WORKING_DIR = os.path.realpath( os.path.join( MY_WORKING_DIR, '..' ) )
SRC_DIR = os.path.realpath(os.path.join( SCRIPT_DIR, '../' ))


confpath = os.path.join( WORKING_DIR, 'confPeers.cfg' )


if os.path.isfile( os.path.join( WORKING_DIR, 'small.file' ) ):
    os.symlink( os.path.join( WORKING_DIR, 'small.file' ),
                os.path.join( MY_WORKING_DIR, 'peerfolder/small.file' ) )
else:
    raise RuntimeError("Failed to find small.file")


# built-in delay to let server start up
time.sleep(3)

args = ( os.path.join(SRC_DIR,'peer.py'), confpath )
try:
    proc = subprocess.Popen( args, stdin=subprocess.PIPE, shell=True )
    
    # wait for initial start up
    time.sleep(2)
    # pray that it's connected
    
    proc.communicate( input="REQ\n" )
    time.sleep(2)
    proc.communicate( input='createtracker small.file "This file is small"\n' )
    
    try:
        proc.wait()
    
    except KeyboardInterrupt:
        proc.communicate( input='exit\n' )
        
        proc.wait(timeout=10)


finally:
    try:
        proc.terminate()
    except:
        pass
    
    exit()

#!/usr/bin/env python3
"""Demo script for the project.

Basic Guideline:
You are also required to develop a starter script which starts execution of a
server and 2 peers at time 0, start 5 peers which download both the files being
shared at time = 30 secs, start 5 more peers which download both the peers at time
=1 min 30 secs, and finally stop execution of the peers, created at time = 0, at time =
1 min 30 secs.

Runtime Schedule:
t=0  start: server, peer1, peer2
t=30 start: peer3, ..., peer 8
t=90 start: peer9, ..., peer 13
    
"""

import sys
import time
import os, os.path
import subprocess
import glob

from demo_helper import START_TIME, SCRIPT_DIR, seconds, waiter
WORKING_DIR = os.getcwd()

def clean():
    import shutil
    
    #remove server directory
    server_path = os.path.join(WORKING_DIR,'server')
    if os.path.isdir( server_path ):
        shutil.rmtree( server_path )
    
    #remove peer directories
    peer_path = os.path.join(WORKING_DIR,'peer{}')
    for i in range(20):
        if os.path.isdir( peer_path.format(i) ):
            shutil.rmtree( peer_path.format(i) )


def start(name, scriptname):
    """Creates a working directory (WORKING_DIR/*name*) and a gnome-terminal
    instance for *scriptname* to run.
    
    Arguments:
        name (str): Name of the directory and title of the terminal.
        scriptname (str): Name of the script (including extension) to run.
    """
    
    print("\nCreating directory", name)
    wdir = os.path.join( WORKING_DIR, name )
    os.mkdir( wdir, mode=0o777 )
    
    title = name.upper()
    script = os.path.join( SCRIPT_DIR, scriptname )
    
    print("Starting", title, "terminal for script", scriptname)
    
    returncode = subprocess.call(['gnome-terminal',
                                    '--working-directory', wdir,
                                    '--title', title,
                                    '--command', script
                                 ])
    
    if returncode != 0:
        print("\n\nERROR: gnome-terminal returned status code", returncode)
        print("Exiting...")
        exit( returncode )


##
## RUNTIME
##

if len(sys.argv)>1 and sys.argv[1] in ('clean','--clean'):
    clean()
    exit(0)


for fl in ('confPeers.cfg','confServer.cfg','small.file','large.file'):
    if not os.path.isfile( os.path.join( WORKING_DIR, fl ) ):
        print("\n\nERROR: couldn't find file",fl,"in working directory")
        print("Exiting...")
        exit(1)

clean()

#### T = 0s

start('server', 'demo.server.py')
start('peer1',  'demo.peer1.py')
start('peer2',  'demo.peer2.py')

waiter(30)
#### T = 30s

for i in range(3,8+1):
    pr = 'peer{}'.format(i)
    start(pr, 'demo.peer3etc.py')

waiter(90)
#### T = 90s

for i in range(9,13+1):
    pr = 'peer{}'.format(i)
    start(pr, 'demo.peer3etc.py')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tracker server for hosting .track torrent files.
"""

import socket
import socketserver
import threading

import os.path

import urllib.parse
from ipaddress import IPv4Address,AddressValueError

import trackerfile
import apiutils


class TrackerServerHandler(socketserver.BaseRequestHandler):
    """The request handler for TrackerServer.
    """
    
    def handle(self):
        """Convert peer requests into methods
        """
        
        #get (MAX_MESSAGE_LENGTH + 1) bytes
        data = str(self.request.recv(self.server.MAX_MESSAGE_LENGTH+1),
                    apiutils.default_encoding, apiutils.default_encoding_errors)
        
        
        #check if data is <= MAX_MESSAGE_LENGTH
        if len(data) > self.server.MAX_MESSAGE_LENGTH:
            print("Request too long")
            # this is out-of-spec, but necessary
            return self.exception( 'RequestTooLong', "Maximum message length " \
                                "is {}".format(self.server.MAX_MESSAGE_LENGTH) )
        
        #Retrieve command and args from message
        match = apiutils.re_apicommand.match( data )
        if not match:
            print("Bad Request: {!r}".format(data))
            # this is out-of-spec, but necessary
            return self.exception( 'BadRequest', "Failed to parse request" )
        
        command, args = match.group('command','args')
        
        #parse arguments
        args = args.split()
        args = map( apiutils.arg_decode, args )
        
        #find the desired method
        api_method = getattr( self, 'api_{}'.format(command),None )
        if not api_method:
            return self.exception( 'BadRequest', "No such method {!r}".format(
                                                                      command) )
        
        #try calling the method with arguments
        try:
            api_method( *args )
        
        except TypeError as err:
            if 'positional arguments' in str(err):
                return self.exception('BadRequest', err.args[0])
            
            raise err
        
    
    def api_createtracker(self, fname, fsize, descrip, md5, ip, port):
        """Implements the createtracker API command.
        
        All arguments are expected to be strings, but some should be castable
        to the following values:
            fsize: int
            ip: IPv4Address
            port: int
        """
        
        fname,descrip,md5 = map( str, (fname,descrip,md5) )
        
        try:
            fsize,port = int(fsize),int(port)
        except ValueError:
            ##return self.exception('ValueError',"Either fsize ({!r}) or port " \
            ##        "({!r}) is not a valid integer".format(fsize,port) )
            self.request.sendall( b"<createtracker fail>" )
            return
        
        try:
            ip = IPv4Address(ip)
        except AddressValueError:
            ##return self.exception('ValueError',"Malformed IP address: " \
            ##                                            "{!r}".format(ip) )
            self.request.sendall( b"<createtracker fail>" )
            return
        
        
        tfname = "{}.track".format( fname )
        
        tfpath = os.path.join( self.server.torrents_dir, tfname )
        
        #check if .track file already exists
        if os.path.exists( tfpath ):
            self.request.sendall( b"<createtracker ferr>" )
            return
        
        #
        try:
            tf = trackerfile.trackerfile( fname, fsize, descrip, md5 )
        except Exception as err:
            ##return self.exception('RuntimeError',"The following exception " \
            ##        "occurred while creating the trackerfile:\n" \
            ##        "{!s}".format(err) )
            self.request.sendall( b"<createtracker fail>" )
            return
        
        
    
    
    def api_updatetracker(self, fname, start_bytes, end_bytes, ip, port):
        pass
    
    
    def api_req(self, *_):
        pass
    
    
    def api_get(self, track_fname):
        pass
    
    def exception(self, exceptionType, exceptionInfo=''):
        
        exceptionType = exceptionType.replace(' ','')
        if exceptionInfo:
            exceptionInfo ="{}\n".format(urllib.parse.quote_plus(exceptionInfo))
        else:
            exceptionInfo = ''
        
        response = "<EXCEPTION {}>\n{}<EXCEPTION END>\n".format( exceptionType,
                                                                 exceptionInfo )
        
        self.request.sendall( bytes(response, 'utf-8') )


class TrackerServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """The socket server for handling incoming requests.
    """
    
    config_file = None
    MAX_MESSAGE_LENGTH = 4096
    torrents_dir = './torrents/'
    
    def __init__(self, server_address, RequestHandlerClass, 
                       bind_and_activate=True,
                       config_file='./serverThreadConfig.cfg'):
        """TrackerServer initializer. Extends TCPServer constructor
        """
        
        self.config_file = config_file
        # TODO: read from config file
        
        
        super(TrackerServer, self).__init__(server_address, RequestHandlerClass,
                                            bind_and_activate)
    
    


#
# Executable form for testing
#
if __name__ == '__main__':
    
    PORT = 9999
    while True:
        try:
            srv = TrackerServer( ("localhost", PORT), TrackerServerHandler )
        except OSError as err:
            if 'already in use' in str(err):
                PORT += 1
                continue
        break
    
    print("Listening on port {}".format(PORT))
    
    try:
        srv.serve_forever()
    
    finally:
        srv.shutdown()

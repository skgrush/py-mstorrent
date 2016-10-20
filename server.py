#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tracker server for hosting .track torrent files.
"""

import socket
import socketserver
import threading

import os
import os.path

import urllib.parse
from ipaddress import IPv4Address,AddressValueError

import trackerfile
import apiutils
import sillycfg



class TrackerServerHandler(socketserver.BaseRequestHandler):
    """The request handler for TrackerServer.
    """
    
    def handle(self):
        """Convert peer requests into methods
        """
        
        #get (MAX_MESSAGE_LENGTH + 1) bytes
        data = str(self.request.recv(self.server.MAX_MESSAGE_LENGTH+1),
                                                    *apiutils.encoding_defaults)
        
        
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
        command = command.lower()
        
        #parse arguments
        args = args.split()
        args = map( apiutils.arg_decode, args )
        
        #find the desired method
        api_method = getattr( self, 'api_{}'.format(command),None )
        if not api_method:
            print("Bad method: {}".format(command) )
            return self.exception( 'BadRequest', "No such method {!r}".format(
                                                                      command) )
        
        #try calling the method with arguments
        try:
            api_method( *args )
        
        except TypeError as err:
            if 'positional arguments' in str(err):
                print("Bad Request: {}".format(err.args[0]))
                return self.exception('BadRequest', err.args[0])
            
        
    
    def api_createtracker(self, fname, fsize, descrip, md5, ip, port):
        """Implements the createtracker API command.
        
        All arguments are expected to be strings, but *fsize* and *port* should
        be castable to :class:`int` and *ip* should be castable to 
        :class:`~ipaddress.IPv4Address`.
        """
        
        fname,descrip,md5 = map( str, (fname,descrip,md5) )
        
        try:
            fsize,port = int(fsize),int(port)
        except ValueError:
            print("Either fsize ({!r}) or port ({!r}) is not a valid " \
                                                "integer".format(fsize,port))
            ##return self.exception('ValueError',"Either fsize ({!r}) or port " \
            ##        "({!r}) is not a valid integer".format(fsize,port) )
            self.request.sendall( b"<createtracker fail>" )
            return
        
        try:
            ip = IPv4Address(ip)
        except AddressValueError:
            print("Malformed IP Address: {!r}".format(ip))
            ##return self.exception('ValueError',"Malformed IP address: " \
            ##                                            "{!r}".format(ip) )
            self.request.sendall( b"<createtracker fail>" )
            return
        
        
        tfname = "{}.track".format( fname )
        
        tfpath = os.path.join( self.server.torrents_dir, tfname )
        
        #check if .track file already exists
        if os.path.exists( tfpath ):
            print("Couldn't create tracker, already exists.")
            self.request.sendall( b"<createtracker ferr>" )
            return
        
        #create a new trackerfile
        try:
            tf = trackerfile.trackerfile( fname, fsize, descrip, md5 )
        except Exception as err:
            print(err)
            ##return self.exception('RuntimeError',"The following exception " \
            ##        "occurred while creating the trackerfile:\n" \
            ##        "{!s}".format(err) )
            self.request.sendall( b"<createtracker fail>" )
            return
        
        print("Created new trackerfile instance for fname={!r}".format(fname))
        
        #add creator as peer
        try:
            tf.updatePeer( ip, port, 0, fsize-1 )
        except Exception as err:
            print(err)
            self.request.sendall( b"<createtracker fail>" )
            return
        
        print("Added {} (creator) to trackerfile".format( ip ))
        
        #write tracker to file
        with open(tfpath, 'w') as fl:
            tf.writeTo( fl )
        
        print("Wrote trackerfile to disk.")
        
        self.request.sendall( b"<createtracker succ>" )
        return
    
    
    def api_updatetracker(self, fname, start_bytes, end_bytes, ip, port):
        """Implements the updatetracker API command.
        
        All arguments are expected to be strings, but *start_bytes*,
        *end_bytes*, and *port* should be castable to :class:`int` and 
        *ip* should be castable to :class:`~ipaddress.IPv4Address`.
        """
        fname = str(fname)
        
        try:
            start_bytes,end_bytes,port = map(int, (start_bytes,end_bytes,port))
        except ValueError:
            print("Either start_bytes ({!r}), end_bytes ({!r}), or port ({!r})"\
                   " is not a valid integer".format(start_bytes,end_bytes,port))
            ##return self.exception('ValueError',"Either start_bytes ({!r}), " \
            ##               "end_bytes ({!r}), or port ({!r}) is not a valid "\
            ##               "integer".format(start_bytes,end_bytes,port))
            self.request.sendall( b"<updatetracker fail>" )
            return
        
        try:
            ip = IPv4Address(ip)
        except AddressValueError:
            print("Malformed IP Address: {!r}".format(ip))
            ##return self.exception('ValueError',"Malformed IP address: " \
            ##                                            "{!r}".format(ip) )
            self.request.sendall( b"<updatetracker fail>" )
            return
        
        tfname = "{}.track".format( fname )
        
        tfpath = os.path.join( self.server.torrents_dir, tfname )
        
        #check if .track file exists
        if not os.path.exists( tfpath ):
            print("Can't update tracker file, doesn't exist")
            self.request.sendall( b"<updatetracker ferr>" )
            return
        
        #create trackerfile from existing tracker
        try:
            tf = trackerfile.trackerfile.fromPath( tfpath )
        except Exception as err:
            print(err)
            self.request.sendall( b"<updatetracker fail>" )
            return
        
        #add peer peer
        try:
            tf.updatePeer( ip, port, start_bytes, end_bytes )
        except Exception as err:
            print(err)
            self.request.sendall( b"<updatetracker fail>" )
            return
        
        print("Added {} (creator) to trackerfile".format( ip ))
        
        #write tracker to file
        with open(tfpath, 'w') as fl:
            tf.writeTo( fl )
        
        print("Wrote trackerfile to disk.")
        
        self.request.sendall( b"<updatetracker succ>" )
        return
        
    
    
    def api_req(self, *_):
        thelist = []
        tracklist = []
        
        dirname = self.server.torrents_dir
        
        try:
            thelist = os.listdir( dirname )
        except Exception as err:
            print(err)
            # ! this is out-of-spec, but necessary
            self.exception(type(err).__name__, str(err))
            return
        
        for flname in thelist:
            if flname.endswith('.track'):
                tracklist.append(flname)
        
        self.request.sendall( bytes("<REP LIST {}>\n".format(len(tracklist)),
                                    *apiutils.encoding_defaults) )
        
        for i in range(len(tracklist)):
            tfname = tracklist[i]
            
            tf = trackerfile.trackerfile.fromPath( os.path.join(dirname,tfname))
            
            self.request.sendall( bytes("<{} {} {} {}>\n".format(i, tf.filename,
                                                         tf.filesize, tf.md5),
                                                 *apiutils.encoding_defaults) )
        
        self.request.sendall( b"<REP LIST END>\n" )
        
        print("Successfully send REP response.")
        return
    
    
    def api_get(self, track_fname):
        track_fname = str(track_fname)
        
        tfpath = os.path.join( self.server.torrents_dir, track_fname )
        
        #check if .track file exists
        if not os.path.exists( tfpath ):
            print("Can't get tracker file, doesn't exist")
            self.exception("FileNotFound", "No such file {!r}".format(
                                                                   track_fname))
            return
        
        #create trackerfile from existing tracker
        try:
            tf = trackerfile.trackerfile.fromPath( tfpath )
        except Exception as err:
            print(err)
            return self.exception(type(err).__name__, str(err))
        
        #write the tracker file to the socket
        self.request.sendall( b"<REP GET BEGIN>\n" )
        tf.writeToSocket( self.request ) 
        self.request.sendall( bytes( "<REP GET END {}>\n".format(tf.md5),
                                                   *apiutils.encoding_defaults))
        
        print("Sent REP response for {!r}".format(track_fname))
    
    def api_hello(self, *_):
        self.request.sendall( b"<HELLO>\n" )
        print("Sent HELLO response")
    
    def exception(self, exceptionType, exceptionInfo=''):
        
        exceptionType = exceptionType.replace(' ','')
        if exceptionInfo:
            exceptionInfo ="{}\n".format(urllib.parse.quote_plus(exceptionInfo))
        else:
            exceptionInfo = ''
        
        response = "<EXCEPTION {}>\n{}<EXCEPTION END>\n".format( exceptionType,
                                                                 exceptionInfo )
        
        self.request.sendall( bytes(response, *apiutils.encoding_defaults) )


class TrackerServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """The socket server for handling incoming requests.
    
    Unlike the TCPServer constructor, this takes a *server_ip* string
    instead of a tuple address because we will read the port for the
    address from the config file.
    
    Arguments:
        server_ip (str): The IP to bind to and listen to.
        RequestHandlerClass (:class:`~socketserver.BaseRequestHandler`): 
            Should be :class:`~.TrackerServerHandler`.
        bind_and_activate (bool, optional): automatically invokes server
            binding and activation procedures.
        config_file (str, optional): Path to server configuration file.
    """
    
    config_file = None
    MAX_MESSAGE_LENGTH = 4096
    __torrents_dir = None
    
    def __init__(self, server_ip, RequestHandlerClass, 
                       bind_and_activate=True,
                       config_file='./serverThreadConfig.cfg'):
        """TrackerServer initializer."""
        
        self.config_file = sillycfg.ServerConfig.fromFile( config_file )
        self.torrents_dir = self.config_file.sharedFolder
        server_port = self.config_file.listenPort
        
        server_address = (server_ip,server_port)
        
        print("Server will bind to {}:{}".format(*server_address))
        
        super(TrackerServer, self).__init__(server_address, RequestHandlerClass,
                                            bind_and_activate)
    
    @property
    def torrents_dir(self):
        return self.__torrents_dir
    
    @torrents_dir.setter
    def torrents_dir(self,val):
        val = os.path.abspath(val)
        
        if not ( sillycfg.dirmaker(val) ):
            raise RuntimeError("Failed to make torrents directory")
        
        self.__torrents_dir = val


#
# Executable form for testing
#
if __name__ == '__main__':
    
    srv = TrackerServer( "localhost", TrackerServerHandler )
    
    print("Listening on port {}".format(srv.config_file.listenPort))
    
    try:
        srv.serve_forever()
    
    except KeyboardInterrupt:
        print("\n"+"="*40)
        print("Bye, have a wonderful time! (Tracker server shutting down)")
        
    finally:
        srv.shutdown()
        print("Tracker server has shut down")

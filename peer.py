#!/usr/bin/env python3

from clientInterface import *
import apiutils
import argparse
import cmd
import curses
import hashlib
import os

import socket
import socketserver
import threading

import trackerfile

thost = '127.0.0.1'
tport = 9999
myip = None

# Put these in a config
STARTPORT = 666
FILE_DIRECTORY = "torrents/"
CHUNK_SIZE = 1024

def f(queue):
    pass


# Basically a copypaste of server.py
class PeerServerHandler(socketserver.BaseRequestHandler):
    """The request handler for PeerServer.
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

    def api_get(self, seg, fname, start_byte, chunk_size):
        if int(chunk_size) > CHUNK_SIZE:
            return self.exception("ChunkSizeException", "{} > {}".format(chunk_size, CHUNK_SIZE))
        # Open the file
        path = self.server.torrents_dir + "/" + fname
        try:
            file = open(path, "r")
        except Exception as err:
            return self.exception("FileException", str(err))

        file.seek(int(start_byte))
        payload = file.read(int(chunk_size))

        # Transmit up to chunk_size bytes
        response = "<GET GOT {}>\n".format(len(payload))
        response += payload

        file.close()

        self.request.sendall( bytes(response, *apiutils.encoding_defaults) )


    def exception(self, exceptionType, exceptionInfo=''):

        exceptionType = exceptionType.replace(' ','')
        if exceptionInfo:
            exceptionInfo ="{}\n".format(apiutils.arg_encode(exceptionInfo))
        else:
            exceptionInfo = ''
        
        response = "<EXCEPTION {}>\n{}<EXCEPTION END>\n".format( exceptionType,
                                                                 exceptionInfo )
    
        self.request.sendall( bytes(response, *apiutils.encoding_defaults) )

class PeerServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """The socket server for handling incoming requests.
    """
    
    config_file = None
    MAX_MESSAGE_LENGTH = 4096
    __torrents_dir = './torrents/'
    
    def __init__(self, server_address, RequestHandlerClass, 
                       bind_and_activate=True,
                       config_file='./peerThreadConfig.cfg'):
        """PeerServer initializer. Extends TCPServer constructor
        """
        
        self.config_file = config_file
        
        
        self.torrents_dir = './torrents/'
        
        super(PeerServer, self).__init__(server_address, RequestHandlerClass,
                                            bind_and_activate)
    
    @property
    def torrents_dir(self):
        return self.__torrents_dir
    
    @torrents_dir.setter
    def torrents_dir(self,val):
        val = os.path.abspath(val)
        
        if not os.path.exists(val):
            print("No such directory {!r}. Maybe I'll make it.".format(val))
            parentdir = os.path.dirname(val)
            
            if os.path.exists( parentdir ):
                parent_mode = os.stat(parentdir).st_mode
                os.mkdir(val, parent_mode)
                
                self.__torrents_dir = val
                return
        
        else:
            self.__torrents_dir = val
            return
            
        raise FileNotFoundError(2,"No such directory {!r}".format(parentdir),
                                                                    parentdir)
            
        
    
class peer():
    def __init__(self, message_queue):
        self.message_queue = message_queue
        STARTPORT = 666

        while True:
            try:
                self.srv = PeerServer( ("localhost", STARTPORT), PeerServerHandler)
                print("Listening on port {}".format(STARTPORT))
            except Exception as err:
                if 'already in use' in str(err):
                    STARTPORT += 1
                    continue
                else:
                    print(err)
            break

        self.server = multiprocessing.Process(target = self.srv.serve_forever)
        #self.downloader = multiprocessing.Process(target = self.spawn_threads, args = (message_queue))

    # Begin processes for job-2 and job-3
    def begin(self):
        self.server.start()
        #self.downloader.start()
        pass

    # Spawns new threads for each tracker file to download
    def spawn_threads(self):
        pass

    def createtracker(filename, description):
        try:
            size = os.path.getsize(FILE_DIRECTORY + filename)
        except Exception as err:
            print(err)
            return (0, 0)

        try:
            md5 = hashlib.md5()
            with open(FILE_DIRECTORY + filename, "rb") as f:
                for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                    md5.update(chunk)
        except Exception as err:
            print(err)
            return(0, 0)

        return (size, md5.hexdigest())

    def send(self, ip, port, message, queue):
        global myip
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as msg:
            peer.write("Unable to create socket", queue)
            return

        s.connect((ip, int(port)))
        s.send(bytes((message), *apiutils.encoding_defaults))
        myip = s.getsockname()[0]
        resp = s.recv(4096)
        s.close()

        peer.write(apiutils.arg_decode(resp.decode(*apiutils.encoding_defaults)), queue)
        return resp.decode(*apiutils.encoding_defaults)

    def write(message, queue):
        queue.put(str(message))


class interpreter(cmd.Cmd):
    def __init__(self):
        self.stdout = self
        pass

    def str_to_args(string):
        import re
        if string == "":
            return []
        matches = re.finditer('(?P<quote>[\'\"]).*?(?P=quote)', string)

        for match in matches:
            string = string.replace(match.group(), match.group().replace(" ", "%20"))
        args = string.replace("=", " ").split(" ")

        for i in range(len(args)):
            args[i] = args[i].replace("%20", " ").replace("\"", "").replace("\'", "")
        return args

    def do_help(self, line):
        x = cmds["help"].parse_args(interpreter.str_to_args(line))

        if not line:
            self.write(cmds["help"].format_help().replace("peer.py", "help"))
            for command in cmds:
                self.write(command + "\t" + cmds[command].description)
        else:
            if x.command in cmds:
                c = cmds[x.command]
                self.write(c.format_help().replace("peer.py", x.command))
            else:
                self.write("Unknown command {}".format(x.command))
            


    def do_createtracker(self, line):
        x = cmds["createtracker"].parse_args(interpreter.str_to_args(line))
        x.fname, x.descrip = apiutils.arg_encode(x.fname), apiutils.arg_encode(x.descrip)
        self.write("Creating tracker file for {}".format(x.fname))
        fsize, fmd5 = peer.createtracker(x.fname, x.descrip)
        if fsize > 0:
            message = "<createtracker {} {} {} {} {} {}>".format(x.fname, fsize, x.descrip, fmd5, myip, 1000)
            self.write(message)
            response = peer.send(peer, (x.host or thost), (x.port or tport), message, self.message_queue)
        else:
            self.write("Unable to find file {} or file is empty".format(x.fname))

    def do_updatetracker(self, line):
        args = interpreter.str_to_args(line)
        x = cmds["updatetracker"].parse_args(interpreter.str_to_args(line))
        if len(args) == 3:
            response = peer.send(peer, thost, tport, "<updatetracker {} {} {}>".format(args[0], args[1], args[2], ), self.message_queue)
            self.write(response)
        else:
            self.write("Usage: updatetracker filename start_bytes end_bytes")

    def do_gettracker(self, line):
        parse = cmds["gettracker"].parse_args(interpreter.str_to_args(line))
        self.write("Retreiving tracker file for {}".format(parse.fname))


    def do_GET(self, line):
        parse = cmds["GET"].parse_args(interpreter.str_to_args(line))
        peer.send(peer, parse.host, parse.port, "<GET SEG {} {} {}>".format(apiutils.arg_encode(parse.fname), parse.start_byte, parse.chunk_size), self.message_queue)

    def do_REQ(self, line):
        args = interpreter.str_to_args(line)
        host, port = thost, tport
        if len(args) == 1 and args[0]:
            host = args[0]
        elif len(args) == 2:
            host, port = args
        self.write("Requesting list of tracker files from tracker {}:{}".format(host, port))
        response = peer.send(peer, host, port, "<REQ LIST>", self.message_queue)

    # stdout and stderr
    def write(self, msg):
        self.message_queue.put(str(msg))
        pass
    def flush(self):
        pass


class cmdparser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentParserError(message)

class ArgumentParserError(Exception):
    pass

cmds = {
    "help" : cmdparser(description="Display this help page", add_help=False),
    "createtracker" : cmdparser(description="Create a tracker file", add_help=False),
    "updatetracker" : cmdparser(description="Update a tracker file", add_help=False),
    "gettracker" : cmdparser(description="Retrieve a tracker file", add_help=False),
    "GET" : cmdparser(description="Retrieve a segment of a torrent file", add_help=False),
    "REQ" : cmdparser(description="Request a list of tracker files", add_help=False),
    "quit" : cmdparser(description="Exit the program", add_help=False)
}

cmds["help"].add_argument("command", type=str, metavar="command", nargs="?", help="Get help with a specific command")
cmds["createtracker"].add_argument("fname", type=str, help="Name of the file")
cmds["createtracker"].add_argument("descrip", type=str, help="File description")
cmds["createtracker"].add_argument("-host", type=str, help="Tracker ip")
cmds["createtracker"].add_argument("-port", type=int, help="Tracker port")
cmds["REQ"].add_argument("host", type=str, help="Tracker ip", nargs="?")
cmds["REQ"].add_argument("port", type=int, help="Tracker port", nargs="?")
cmds["gettracker"].add_argument("fname", type=str, help="Name of tracker file")
cmds["GET"].add_argument("fname", type=str, help="Name of file")
cmds["GET"].add_argument("start_byte", type=int, help="Start byte")
cmds["GET"].add_argument("chunk_size", type=int, help="Number of bytes to retreive")
cmds["GET"].add_argument("host", type=str, help="Tracker ip")
cmds["GET"].add_argument("port", type=int, help="Tracker port")


def main(stdscr):
    commandline = interpreter()

    cli = clientInterface(stdscr, commandline, cmds)
    commandline.message_queue = cli.queue
    sys.stdout = commandline
    sys.stderr = commandline
    clientInterface.begin(cli)

    my_peer = peer(cli.queue)

    response = my_peer.send(thost, tport, "<HELLO>", cli.queue)
    try:
        my_peer.begin()
    except Exception as err:
        print(err)
    cli.inp.join()

    curses.curs_set(0)

    my_peer.srv.shutdown()

if __name__ == "__main__":
    curses.wrapper(main)
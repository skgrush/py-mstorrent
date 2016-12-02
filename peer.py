#!/usr/bin/env python3
""" Peer-to-peer file transfer client
"""

from clientInterface import *
import apiutils
import argparse
import base64
import cmd
import hashlib
import os
import sillycfg
import sys

import socket
import socketserver
import trackerfile

myip = None

STARTPORT = 11000
CHUNK_SIZE = 1024

class PeerServerHandler(socketserver.BaseRequestHandler):
    """The request handler for PeerServer.
    """
    
    def handle(self):
        """Convert peer requests into into api_* methods

        This method is called when data is received. It interprets the
        command-and-arguments structure dictated by the API into a method
        to which the interpreted arguments are passed. Arguments are decoded
        using :func:`apiutils.arg_decode` before being passed on, but they
        remain strings.
        """
        
        data = str(self.request.recv(4096), *apiutils.encoding_defaults)
        
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
        """Implements the peer's GET API command.
        
        All arguments are expected to be strings, but *start_byte* and *chunk_size*
        should be castable to :class:`int`.
        """
        if seg != "SEG":
            print("GET Error: {}".format(seg))
            return self.exception("BadRequest", "'SEG' expected")
        print("Received request for '{}', starting from byte {} with chunk size {}".format(fname, start_byte, chunk_size))
        if int(chunk_size) > CHUNK_SIZE:
            return self.request.sendall(b"<GET invalid>\n")
        
        # Check if a log file exists for the file
        tracker = os.path.join(self.server.torrents_dir, fname + ".log")
        if not os.path.isfile(tracker):
            return self.exception("NotHostingFile", "Peer does not have a logfile for '{}'.".format(fname))

        # Open the file
        path = os.path.join(self.server.torrents_dir, fname)
        try:
            with open(path, "rb") as file:
                file.seek(int(start_byte))
                payload = file.read(int(chunk_size))

                # Transmit up to chunk_size bytes
                response = "<GET GOT {}>\n".format(len(payload))
                response += bytes.decode(base64.b64encode(payload), "UTF-8")
        except Exception as err:
            print(str(err))
            # Since the file doesn't exist, let the tracker know you're no longer hosting it
            # (todo)

            # Return an Exception
            return self.exception("FileException", "Could not find file for torrent '{}'".format(fname))

        self.request.sendall( bytes(response, *apiutils.encoding_defaults) )
        print("Transmitted bytes {}-{} of file {}".format(start_byte, int(start_byte) + len(payload), fname))



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
    
    __torrents_dir = None
    
    def __init__(self, address, RequestHandlerClass, 
                       bind_and_activate=True,
                       torrents_dir='./peerfolder'):
        """PeerServer initializer. Extends TCPServer constructor
        """
        self.torrents_dir = torrents_dir
        
        
        super(PeerServer, self).__init__(address, RequestHandlerClass,
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
            
        
    
class peer():
    """ Main Peer class; handles job-2 and job-3 for file hosting and downloading
    """
    def __init__(self, config):
        self.config = config
        global STARTPORT
        if STARTPORT < 1024:
            print("Warning: Port {} may be reserved. Please use port 1024 or higher".format(STARTPORT))

        while True:
            try:
                self.srv = PeerServer((myip, STARTPORT), PeerServerHandler)
                print("Listening on port {}".format(STARTPORT))
            except Exception as err:
                if 'already in use' in str(err):
                    STARTPORT += 1
                    continue
                else:
                    print(err)
            break


        self.server = multiprocessing.Process(target = self.srv.serve_forever)

        self.child_conn = multiprocessing.Queue()
        self.download = downloader(self.child_conn)
        self.downloader = multiprocessing.Process(target = self.download.spawn)

    def begin(self):
        """ Begin job-2 and job-3, the chunk server and downloader processes
        """
        self.server.start()
        self.downloader.start()
        pass

    def createtracker(filename):
        """ Create the supplementary log file for a tracker. 
        Also computes and returns the size and md5 of the local file
        Arguments:
            filename (str): The name of the local file, which must exist in FILE_DIRECTORY (under #directory in config)
        """
        # Get the size
        try:
            size = os.path.getsize(FILE_DIRECTORY + filename)
        except Exception as err:
            print(err)
            return (0, 0)

        # Get the md5hash
        try:
            md5 = hashlib.md5()
            with open(FILE_DIRECTORY + filename, "rb") as f:
                for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                    md5.update(chunk)
        except Exception as err:
            print(err)
            return(0, 0)

        # Generate a log file indicating entire file is available
        try:
            with open(os.path.join(FILE_DIRECTORY, filename + ".log"), "w") as logfile:
                logfile.write("0:{}".format(size))
        except Exception as err:
            print(str(err))

        return (size, md5.hexdigest())

    def send(self, ip, port, message):
        """ Sends a message over the network

        Arguments:
            ip (:class:`~ipaddress.IPv4Address`): The target address
            port (int): The target port
            message (str): The message to send to the server
        """
        global myip
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as msg:
            print("unable to create socket")
            return

        s.connect((ip, int(port)))
        s.send(bytes((message), *apiutils.encoding_defaults))
        myip = s.getsockname()[0]
        resp = b""
        while True:
            try:
                data = s.recv(4096)
            except Exception as err:
                print(str(err))
                break
            if not data:
                break
            resp += data

        s.close()
        return resp.decode(*apiutils.encoding_defaults)

class downloader():
    """ The chunk downloader
    """

    workers = []

    def __init__(self, queue):
        self.queue = queue

    def spawn(self):
        """ Spawns new download threads for each tracker file in FILE_DIRECTORY
        """
        # Get the tracker files currently present
        try:
            trackerfiles = [ f for f in os.listdir(FILE_DIRECTORY) if os.path.isfile(os.path.join(FILE_DIRECTORY, f)) ]
        except Exception as err:
            print(err)
            return

        # Spawn a thread for each tracker file
        for file in trackerfiles:
            if file[-6:].lower() == ".track" and not os.path.isfile(os.path.join(FILE_DIRECTORY, file[:-6])):
                self.spawn_thread(file)

        while True:
            try:
                msg = self.queue.get().split(" ")
                if msg[0] == "EXIT":
                    break
                elif msg[0] == "NEW":
                    file = " ".join(msg[1:])
                    print(file)
                    if file[-6:].lower() == ".track":
                        if os.path.isfile(os.path.join(FILE_DIRECTORY, file[:-6])):
                            print("File '{}' already exists, no need to make new download thread".format(file[:-6]))
                        else:
                            print("Spawning thread for {}".format(file[:-6]))
                            self.spawn_thread(file)
                else:
                    # TODO: Add ability to cancel a download
                    pass
            except Exception:
                break

        for worker in self.workers:
            # TODO: Send the exit signal
            pass

        #for worker in self.workers:
        #    worker.join()

        print("Download process ended.")

    def spawn_thread(self, file):
        """ Spawns a new downloader thread

        Arguments:
            file (str): The name of the tracker file
        """
        try:
            tracker = trackerfile.trackerfile.fromPath(FILE_DIRECTORY + file)
            worker = threading.Thread(name=file, target=self.download, args=(tracker, ) )
            self.workers.append(worker)
            worker.start()
        except Exception as err:
            print(err)


    def download(self, tracker):
        """ 
        """
        fname = tracker[0]
        log = []
        
        # Check if a log and/or cache exists for this file
        logpath = os.path.join(FILE_DIRECTORY, fname + ".log")
        if not os.path.isfile(logpath):
            with open(logpath, "w") as logfile:
                logfile.write("0:0")
        with open(logpath, "r+") as logfile:
            try:
                for line in logfile.readlines():
                    if line != "":
                        start, end = line.split(":")
                        log.append((int(start), int(end)))
            except Exception as err:
                print("Malformed Log File {}. ".format(tracker[0]) + str(err))


        cachepath = os.path.join(FILE_DIRECTORY, fname + ".cache")
        if not os.path.isfile(cachepath):
            cache = open(cachepath, "wb")
        else:
            cache = open(cachepath, "r+b")


        while downloader.size_remaining(log, tracker) > 0:
            peer, start, size = downloader.next_bytes(log, tracker)
            chunk = self.get(apiutils.arg_encode(fname), start, size, str(peer[0]), peer[1])
            match = apiutils.re_apicommand.match(chunk)
            if match and match.group(1) == "GET":
                payload = base64.b64decode(chunk.replace(match.group() + "\n", ""))
                if len(payload) == size:
                    downloader.update(cache, log, logpath, start, size, payload)
                    print("Downloaded bytes {} to {} of {}".format(start, start + size, fname))
                else:
                    print("Error - incorrect size!")
                    time.sleep(0.5)
                time.sleep(0.01)
            else:
                print("Error. {}".format(apiutils.arg_decode(chunk)))
                time.sleep(0.5)
                # Request an updated tracker file



        print("Finished downloading '{}'".format(fname))

        # Close files
        if not cache.closed:
            cache.close()

        # Check MD5
        try:
            md5 = hashlib.md5()
            with open(FILE_DIRECTORY + fname + ".cache", "rb") as f:
                for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                    md5.update(chunk)
        except Exception as err:
            print(err)
        
        if md5.hexdigest() == tracker[3]:
            print("md5 check passed for '{}'".format(fname))

            # Delete Tracker File
            os.remove(os.path.join(FILE_DIRECTORY, fname + ".track"))


            # Rename .cache file to actual file
            filepath = os.path.join(FILE_DIRECTORY, fname)
            if not os.path.exists(filepath):
                os.rename(cachepath, filepath)

        else:
            print("File md5s do not match. {} {}".format(md5.hexdigest(), tracker[3]))




    def get(self, file, start_byte, end_byte, ip, port):
        """ Sends a GET SEG request

        Parameters:
            file (str): The name of the file being downloaded
            start_byte (int): The first byte in the range
            end_byte (int): The last byte in the range
            ip (str): The address of the peer which has the desired chunk
            port (int): The port number of the target peer's chunk server
        """
        global myip
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as msg:
            print("Unable to create socket")
            return

        s.connect((ip, int(port)))
        s.send(bytes(("<GET SEG {} {} {}>".format(file, start_byte, end_byte)), *apiutils.encoding_defaults))
        
        resp = b""
        while True:
            try:
                data = s.recv(4096)
            except Exception as err:
                print(str(err))
                break
            if not data:
                break
            resp += data

        s.close()

        return resp.decode(*apiutils.encoding_defaults)

    def gettracker(file, host, port):
        """ Sends a GET request for a tracker file
        """
        message = "<GET {}.track>".format(apiutils.arg_encode(file))
        
        response = peer.send(peer, host, port, message)
        print(response)

        match = apiutils.re_apicommand.match(response)

        if match and match.group("command") == "REP":
            payload = apiutils.re_apicommand.sub("", response)
            with open(os.path.join(FILE_DIRECTORY, file + ".track"), "w") as tracker:
                tracker.write(payload)
                return True

        else:
            print(apiutils.arg_decode(response))

    def updatetracker(file, start_byte, end_byte, host, port):
        """ Sends an updatetracker command to the server
        """
        fname = apiutils.arg_encode(file)
        msg = "<updatetracker {} {} {} {} {}>".format(fname, start_byte, end_byte, myip, STARTPORT)
        response = peer.send(peer, host, port, msg)

        match = apiutils.re_apicommand.match(response)
        if match and match.group("command") == "updatetracker":
            if "succ" in (match.group("args")):
                # it updated successfully
                print("Tracker update successful")
                pass
            else:
                print(match.group("args") + ":" + response)

        else:
            print(response)

        return response

    def size_remaining(log, tracker):
        """ Compute the remaining number of bytes needed to finish downloading the torrent corresponding
        to the given log

        Arguments:
            log: A list of (start_byte, end_byte) tuples representing which chunks have been downloaded
            tracker (:class:`~trackerfile.trackerfile`): The tracker corresponding to the file being downloaded
        """
        filesize = int(tracker[1])
        cachesize = 0

        for start, end in log:
            cachesize += (end - start)

        return filesize - cachesize

    def next_bytes(log, tracker):
        """ Determines which chunk should be downloaded next for the given trackerfile
        """
        peers = (tracker[4])
        for peer in peers:
            peer_start, peer_end = int(peers[peer][0]), int(peers[peer][1])

            if not log:
                return (peer, peer_start, min(CHUNK_SIZE, peer_end - peer_start + 1))
            
            need = int(log[0][1])

            if need >= peer_start and need <= peer_end:
                return (peer, need, min(CHUNK_SIZE, peer_end - need + 1))

        print("Could not find peer with useful chunk")
        return None


    def update(cache, log, logpath, start, size, payload):
        """ Updates the logfile based on the newly retreived chunk
        """
        cache.seek(start)
        cache.write(payload)
        if not log:
            log.append((start, size))
            with open(logpath, "w") as l:
                for st, en in log:
                    l.write("{}:{}\n".format(st, en))
            return True
        for i in range(len(log)):
            s, e = log[i]
            if e >= start and e <= start + size:
                log[i] = (s, start + size)
                with open(logpath, "w") as l:
                    for st, en in log:
                        l.write("{}:{}\n".format(st, en))
                return True






class interpreter(cmd.Cmd):
    """ The command line interpreter for interfacing the user with the API methods

    Implements cmd.Cmd, so all do_* methods are callable via the curses command line
    """

    def __init__(self):
        self.stdout = self
        self.download_queue = None
        pass

    def str_to_args(string):
        """ Converts a space and quote-delimited string to a list of arguments,
        giving priority to quotes so that arguments may have spaces in them
        """
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
        """ Displays a help message for how to use the command line interface or a specific API function
        """
        x = cmds["help"].parse_args(interpreter.str_to_args(line))

        if not line:
            print(cmds["help"].format_help().replace("peer.py", "help"))
            commands = ""
            for command in cmds:
                print(" " + command + "\t" + cmds[command].description)
            print(commands)
        else:
            if x.command in cmds:
                c = cmds[x.command]
                print(c.format_help().replace("peer.py", x.command))
            else:
                print("Unknown command '{}'".format(x.command))
            


    def do_createtracker(self, line):
        """ Sends a createtracker API command to the server
        """
        x = cmds["createtracker"].parse_args(interpreter.str_to_args(line))
        fname, descrip = apiutils.arg_encode(x.fname), apiutils.arg_encode(x.descrip)
        print("Creating tracker file for {}".format(x.fname))
        fsize, fmd5 = peer.createtracker(x.fname)
        if fsize > 0:
            message = "<createtracker {} {} {} {} {} {}>".format(fname, fsize, descrip, fmd5, myip, STARTPORT)
            print(message)
            response = peer.send(peer, (x.host or thost), (x.port or tport), message)
        else:
            print("Unable to find file '{}'' or file is empty".format(x.fname))

    def do_updatetracker(self, line):
        """ Sends an updatetracker API command to the server
        """
        parse = cmds["updatetracker"].parse_args(interpreter.str_to_args(line))
        downloader.updatetracker(parse.fname, parse.start_byte, parse.end_byte, parse.host or thost, parse.port or tport)

    def do_gettracker(self, line):
        """ Sends a gettracker API command to the server
        """
        parse = cmds["gettracker"].parse_args(interpreter.str_to_args(line))
        if downloader.gettracker(parse.fname, parse.host or thost, parse.port or tport):
            # Tell the downloader thread that there is a new tracker file
            self.download_queue.put("NEW {}.track".format(parse.fname))

    def do_GET(self, line):
        """ Sends a GET API command to a peer
        """
        parse = cmds["GET"].parse_args(interpreter.str_to_args(line))
        response = peer.send(peer, parse.host, parse.port, "<GET SEG {} {} {}>".format(apiutils.arg_encode(parse.fname), parse.start_byte, parse.chunk_size))
        print(response)

    def do_REQ(self, line):
        """ Sends the REQ LST api command to the server
        """
        parse = cmds["REQ"].parse_args(interpreter.str_to_args(line))
        host, port = parse.host or thost, parse.port or tport
        print("Requesting list of tracker files from tracker {}:{}".format(host, port))
        response = peer.send(peer, host, port, "<REQ LIST>")
        print(response)

    # Override for stdout and stderr, so that output is sent to the thread-safe message queue
    def write(self, msg):
        self.message_queue.put(str(msg))

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
cmds["updatetracker"].add_argument("fname", type=str, help="Name of tracker file")
cmds["updatetracker"].add_argument("start_byte", type=int, help="Start byte")
cmds["updatetracker"].add_argument("end_byte", type=int, help="End byte")
cmds["updatetracker"].add_argument("-host", type=str, help="IP address of tracker server", nargs="?")
cmds["updatetracker"].add_argument("-port", type=int, help="Port number of tracker server", nargs="?")
cmds["REQ"].add_argument("-host", type=str, help="Tracker ip", nargs="?")
cmds["REQ"].add_argument("-port", type=int, help="Tracker port", nargs="?")
cmds["gettracker"].add_argument("fname", type=str, help="Name of tracker file")
cmds["gettracker"].add_argument("-host", type=str, help="IP address of tracker server", nargs="?")
cmds["gettracker"].add_argument("-port", type=int, help="Port number of tracker server", nargs="?")
cmds["GET"].add_argument("fname", type=str, help="Name of file")
cmds["GET"].add_argument("start_byte", type=int, help="Start byte")
cmds["GET"].add_argument("chunk_size", type=int, help="Number of bytes to retreive")
cmds["GET"].add_argument("host", type=str, help="Peer ip")
cmds["GET"].add_argument("port", type=int, help="Peer port")


def main(stdscr):
    global thost, tport, FILE_DIRECTORY

    # Read the config
    config = sillycfg.ClientConfig.fromFile( "./clientThreadConfig.cfg" )
    if config.validate():
        server_port = config.serverPort
        server_ip = str(config.serverIP)
        
        server_address = (server_ip, server_port)
        FILE_DIRECTORY = config.peerFolder
        
        thost, tport = server_ip, server_port
    else:
        print("Problem validating config file '{}'!".format("./clientThreadedConfig.cfg"))
        time.sleep(5)
        return

    # Set up the client interface and point stdout to the message queue
    commandline = interpreter()

    cli = clientInterface(stdscr, commandline)
    commandline.message_queue = cli.queue
    sys.stdout = commandline
    sys.stderr = commandline
    clientInterface.begin(cli)


    # Initialize the server and downloader processes
    try:
        response = peer.send(peer, *server_address, "<HELLO>")

        my_peer = peer(config)

        commandline.download_queue = my_peer.download.queue

        my_peer.begin()
    except Exception as err:
        print("Critical failure in initialization")
        print(err)


    cli.inp.join()
    curses.curs_set(0)

    # Shut down
    my_peer.download.queue.put("EXIT")
    my_peer.srv.shutdown()

if __name__ == "__main__":
    curses.wrapper(main)
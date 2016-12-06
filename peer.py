#!/usr/bin/env python3
""" Peer-to-peer file transfer client
"""

from clientInterface import *
import base64, hashlib
import cmd, argparse
import os, sys, time
import selectors, socket, socketserver
import apiutils, trackerfile, sillycfg

myip = None

STARTPORT = 11000
CHUNK_SIZE = 1024
MAX_DATA_SIZE = 4096

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
        data = str(self.request.recv(MAX_DATA_SIZE), *apiutils.encoding_defaults)
        
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
            downloader.updatetracker(fname, 0, 0, thost, tport)

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
    
    def STOP_IT(self):
        self.shutdown()

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
                self.srv = PeerServer((myip, STARTPORT), PeerServerHandler, torrents_dir=config.peerFolder)
                print("Listening on port {}".format(STARTPORT))
            except Exception as err:
                if 'already in use' in str(err):
                    STARTPORT += 1
                    continue
                else:
                    print(err)
            break


        self.server = threading.Thread(target = self.srv.serve_forever)

        self.child_conn = multiprocessing.Queue()
        self.download = downloader(self.child_conn)
        self.downloader = multiprocessing.Process(target = self.download.spawn)

        # Update the server about all the files you are hosting and periodically send updates
        self.refresher = threading.Thread(name="refresher", target=peer.server_refresher, daemon=True)

    def begin(self):
        """ Begin job-2 and job-3, the chunk server and downloader processes
        """
        self.server.start()
        self.downloader.start()
        self.refresher.start()
        pass

    def server_refresher():
        while True:
            try:
                trackerfiles = [ os.path.join(FILE_DIRECTORY, f) for f in os.listdir(FILE_DIRECTORY) if os.path.isfile(os.path.join(FILE_DIRECTORY, f)) ]
            except Exception as err:
                print(err)
                return

            # Update the server with each log file
            for file in trackerfiles:
                if file[-4:].lower() == ".log":
                    log = []
                    with open(file, "r+") as logfile:
                        try:
                            for line in logfile.readlines():
                                if line != "":
                                    start, end = line.split(":")
                                    log.append((int(start), int(end)))
                        except Exception as err:
                            print("Malformed Log File {}. ".format(tracker[0]) + str(err))

                    largest = max(log, key = lambda entry: entry[1] - entry[0])
                    filename = "".join(file.split("/")[-1].split(".log")[:-1])
                    downloader.updatetracker(filename, largest[0], (largest[1] - 1) if largest[1] > 0 else 0, thost, tport)
            time.sleep(UPDATE_INTERVAL)

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
                data = s.recv(MAX_DATA_SIZE)
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

        # Listen for additional tracker files
        while True:
            try:
                msg = self.queue.get().split(" ")
                if msg[0] == "EXIT":
                    break
                elif msg[0] == "NEW":
                    file = " ".join(msg[1:])
                    if file[-6:].lower() == ".track":
                        if os.path.isfile(os.path.join(FILE_DIRECTORY, file[:-6])) or os.path.isfile(os.path.join(FILE_DIRECTORY, file[:-6] + ".log")):
                            print("Log file for '{}' already exists, no need to make new download thread".format(file[:-6]))
                        else:
                            print("Spawning thread for {}".format(file[:-6]))
                            self.spawn_thread(file)
                else:
                    pass
            except Exception:
                break

        for worker in self.workers:
            worker[1].append("DIE")

        for worker in self.workers:
            worker[0].join()
            print("Download thread for {} ended".format(worker[0].name))

        print("Download process ended.")

    def spawn_thread(self, file):
        """ Spawns a new downloader thread

        Arguments:
            file (str): The name of the tracker file
        """
        try:
            killer = []
            tracker = trackerfile.trackerfile.fromPath(FILE_DIRECTORY + file)
            worker = threading.Thread(name=file, target=self.download, args=(tracker, killer) )
            self.workers.append((worker, killer))
            worker.start()
        except Exception as err:
            print(err)


    def download(self, tracker, killer):
        """ Downloads chunks corresponding to the provided tracker file

        Arguments:
            tracker (:class:`~trackerfile.trackerfile`): The tracker file corresponding to the file
                you wish to download
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

        dead_peers = []
        downloading = []

        sel = selectors.DefaultSelector()

        # Make sure the tracker is up to date
        if downloader.gettracker(tracker[0], thost, tport):
            fpath = os.path.join(FILE_DIRECTORY, tracker[0] + ".track")
            tracker = trackerfile.trackerfile.fromPath(fpath)


        # Start 

        while downloader.size_remaining(log, tracker) > 0:
            if killer:
                return
            if downloading:
                events = sel.select()
                for event in events:

                    a, event_type = event
                    sock, y, z, data = a                    

                    if event_type == selectors.EVENT_WRITE:
                        payload = "<GET SEG {} {} {}>".format(*data)
                        failed = False
                        try:
                            sock.send(bytes(payload, *apiutils.encoding_defaults))
                        except Exception as err:
                            failed = True

                        sel.unregister(sock)
                        if not failed:
                            sel.register(sock, selectors.EVENT_READ, data)
                    else:

                        sel.unregister(sock)
                        resp = b""
                        while True:
                            try:
                                dat = sock.recv(MAX_DATA_SIZE)
                            except Exception as err:
                                print(str(err))
                                break
                            if not dat:
                                break
                            resp += dat

                        sock.close()

                        chunk = bytes.decode(resp, *apiutils.encoding_defaults)
                        match = apiutils.re_apicommand.match(chunk)

                        if match and match.group(1) == "GET":

                            payload = base64.b64decode(chunk.replace(match.group() + "\n", ""))
                            if len(payload) == data[2]:
                                downloader.update(cache, log, logpath, data[1], data[2], payload)
                                print("Downloaded bytes {} to {} of {}".format(data[1], data[1] + data[2], data[0]))
                            else:
                                print("Error - incorrect size!")
                                time.sleep(0.5)
                        else:
                            print("Error. {}".format(apiutils.arg_decode(chunk)))
                            dead_peers.append(peer)
                        downloading.remove((data[1], data[1] + data[2]))

                            # Request an updated tracker file

            chunk_queue = downloader.next_bytes(log, tracker, downloading, dead_peers)
            if not chunk_queue:
                # No useful chunks to download... try updating the tracker
                if downloader.gettracker(tracker[0], thost, tport):
                    fpath = os.path.join(FILE_DIRECTORY, tracker[0] + ".track")
                    tracker = trackerfile.trackerfile.fromPath(fpath)

                continue

            for peer, start, size in chunk_queue:
                if len(downloading) > 4:
                    break
                downloading.append((start, start + size))

                message = (apiutils.arg_encode(fname), start, size)

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sel.register(s, selectors.EVENT_WRITE, message)
                try:
                    s.connect((str(peer[0]), int(peer[1])))
                except ConnectionRefusedError:
                    print("Dead peer {}!".format(peer))
                    dead_peers.append(peer)
                    downloading.remove((start, start + size))
                    break




        print("Finished downloading '{}'".format(fname))

        # Close files
        if not cache.closed:
            cache.close()

        sel.close()

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
                data = s.recv(MAX_DATA_SIZE)
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
        #print(response)

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
                print(msg)
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

    def next_bytes(log, tracker, downloading, failed_peers):
        """ Determines which chunk should be downloaded next for the given trackerfile

        As per the specification:
            Segment selection: The to-be-downloaded segment(s) is (are) chosen sequentially.
            Peer selection: The peer which has the newest timestamp is selected to be connected to
        """
        peers = (tracker[4])
        freq = dict()

        # Sort by start byte
        peer_list = sorted(peers.keys(), key=lambda k: int(peers[k][0]))

        start_byte, end_byte = None, None
        for peer in peer_list:
            if peer not in failed_peers:
                peer_start, peer_end = int(peers[peer][0]), int(peers[peer][1])
                
                needed = True
                for entry in downloader.merged(log + downloading):
                    start, end = entry
                    if start <= peer_start and end >= peer_end:
                        needed = False
                        break
                    else:
                        if end < peer_end and end >= peer_start:
                            start_byte = end
                            break
                if needed:
                    if not downloading and (not log or log[0][1] == 0):
                        start_byte = peer_start
                    if start_byte:
                        break

        # Sort by peer timestamp
        peer_list = list(reversed(sorted(peers.keys(), key=lambda k: peers[k][2])))

        if start_byte != None:
            for peer in peer_list:
                if peer not in failed_peers:
                    peer_start, peer_end = int(peers[peer][0]), int(peers[peer][1])

                    if start_byte >= peer_start and start_byte < peer_end:
                        # Queue some chunks from this peer

                        chunk_queue = []
                        start = start_byte
                        while start < peer_end and start - start_byte < CHUNK_SIZE * 10:
                            size = min(CHUNK_SIZE, peer_end - start + 1)
                            chunk_queue.append((peer, start, size))
                            start += size
                        return chunk_queue


        #print("Could not find peer with useful chunk")
        return None


    def update(cache, log, logpath, start, size, payload):
        """ Updates the logfile based on the newly retreived chunk
        """
        cache.seek(start)
        cache.write(payload)

        for i in range(len(log)):
            s, e = log[i]
            if e >= start and e <= start + size:
                log[i] = (s, start + size)
                with open(logpath, "w") as l:
                    for st, en in log:
                        l.write("{}:{}\n".format(st, en))

                # Update the tracker with the largest contiguous chunk
                largest = max(log, key = lambda entry: entry[1] - entry[0])
                filename = "".join(logpath.split("/")[-1].split(".log")[:-1])
                downloader.updatetracker(filename, largest[0], largest[1] - 1, thost, tport)
                

                return True

    def merged(log):
        """ Merge adjacent log entries

        Parameters:
            log: list of (start_byte, end_byte) tuples
        """
        merg = sorted(log[:])
        
        i = 0
        while i < len(merg) - 1:
            start1, end1 = merg[i]
            start2, end2 = merg[i + 1]
            if end1 >= start2 and end1 <= end2:
                merg[i] = (start1, end2)
                del merg[i+1]
                continue
            i += 1

        return merg







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

class stdioverride():
    def __init__(self, message_queue):
        self.message_queue = message_queue

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
    global thost, tport, FILE_DIRECTORY, UPDATE_INTERVAL

    # Read the config
    config_file = sys.argv[1] if len(sys.argv) > 1 else "./clientThreadConfig.cfg"
    config = sillycfg.ClientConfig.fromFile( config_file )
    if config.validate():
        server_port = config.serverPort
        server_ip = str(config.serverIP)
        
        server_address = (server_ip, server_port)
        FILE_DIRECTORY = config.peerFolder
        UPDATE_INTERVAL = config.updateInterval

        thost, tport = server_ip, server_port
    else:
        print("Problem validating config file '{}'!".format( config_file ))
        time.sleep(5)
        return

    # Set up the client interface and point stdout to the message queue
    commandline = interpreter()

    cli = clientInterface(stdscr, commandline)
    stdout = stdioverride(cli.queue)
    sys.stdout = stdout
    sys.stderr = stdout
    clientInterface.begin(cli)

    # Initialize the server and downloader processes
    try:
        response = peer.send(peer, server_address[0], server_address[1], 
                             "<HELLO>")

        my_peer = peer(config)

        commandline.download_queue = my_peer.download.queue

        my_peer.begin()
    except Exception as err:
        print("Critical failure in initialization")
        print(err)

    try:
        cli.inp.join()
    except KeyboardInterrupt:
        pass
    curses.curs_set(0)

    # Shut down
    my_peer.download.queue.put("EXIT")
    my_peer.srv.STOP_IT()
    print("Server thread ended.")

if __name__ == "__main__":
    curses.wrapper(main)
    sys.stdout = sys.__stdout__
    print("Received EXIT signal. All processes terminated.")

    

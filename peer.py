#!/usr/bin/env python3

from clientInterface import *
import apiutils
import argparse
import cmd
import curses
import hashlib
import os
import socket
import threading
import trackerfile

thost = '127.0.0.1'
tport = 10000
myip = None

# Put these in a config
FILE_DIRECTORY = "torrents/"
CHUNK_SIZE = 1024

class peer():
    def __init__(self, message_queue):
        self.message_queue = message_queue

    # Spawns new threads for each tracker file
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

        peer.write(resp.decode(*apiutils.encoding_defaults), queue)
        return resp.decode(*apiutils.encoding_defaults)

    def write(message, queue):
        queue.put(str(message))


class interpreter(cmd.Cmd):
    def __init__(self):
        self.stdout = self
        pass

    def do_help(self, line):
        x = cmds["help"].parse_args(line.split(" "))

        if not line:
            for command in cmds:
                self.write(command + "\t" + cmds[command].description)
        else:
            if x.command in cmds:
                c = cmds[x.command]
                self.write(c.format_help().replace("peer.py", x.command))
            else:
                self.write("Unknown command {}".format(x.command))
            


    def do_createtracker(self, line):
        x = cmds["createtracker"].parse_args(line.split(" "))
        self.write("Creating tracker file for {}".format(x.fname))
        fsize, fmd5 = peer.createtracker(x.fname, x.descrip)
        if fsize > 0:
            message = "<createtracker {} {} {} {} {} {}>".format(x.fname, fsize, x.descrip, fmd5, myip, 1000)
            self.write(message)
            response = peer.send(peer, (x.host or thost), (x.port or tport), message, self.message_queue)
        else:
            self.write("Unable to find file {}".format(x.fname))

    def do_updatetracker(self, line):
        args = line.split(" ")
        if len(args) == 3:
            response = peer.send(peer, thost, tport, "<updatetracker {} {} {}>".format(args[0], args[1], args[2], ), self.message_queue)
            self.write(response)
        else:
            self.write("Usage: updatetracker filename start_bytes end_bytes")

    def do_GET(self, line):
        self.write(line)

    def do_REQ(self, line):
        args = line.split(" ")
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
    "GET" : cmdparser(description="Retrieve a segment of a torrent file or a tracker file", add_help=False),
    "REQ" : cmdparser(description="Request a list of tracker files", add_help=False)
}

cmds["help"].add_argument("command", type=str, metavar="command", nargs="?")
cmds["createtracker"].add_argument("fname", type=str, help="Name of the file")
cmds["createtracker"].add_argument("descrip", type=str, help="File description")
cmds["createtracker"].add_argument("-host", type=str, help="Tracker ip")
cmds["createtracker"].add_argument("-port", type=int, help="Tracker port")
cmds["REQ"].add_argument("host", type=str, help="Tracker ip", nargs="?")
cmds["REQ"].add_argument("port", type=int, help="Tracker port", nargs="?")

def main(stdscr):
    commandline = interpreter()

    cli = clientInterface(stdscr, commandline, cmds)
    commandline.message_queue = cli.queue
    sys.stdout = commandline
    sys.stderr = commandline
    clientInterface.begin(cli)

    response = peer.send(peer, thost, tport, "<HELLO>", cli.queue)
    cli.inp.join()

    curses.curs_set(0)

    for process in cli.processes:
        process.join()

if __name__ == "__main__":
    curses.wrapper(main)
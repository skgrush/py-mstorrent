#!/usr/bin/env python3

from clientInterface import *
import cmd
import curses
import socket
import threading
import urllib.parse

class peer():
    def __init__(self, message_queue):
        self.message_queue = message_queue

    # Spawns new threads for each tracker file
    def spawn_threads(self):
        pass

    def send(self, ip, port, message, queue):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as msg:
            peer.write("Unable to create socket", queue)
            return

        s.connect((ip, int(port)))
        s.send(bytes(urllib.parse.quote_plus(message), "UTF-8"))
        resp = s.recv(4096)
        s.close()

        peer.write("Response: " + resp.decode("UTF-8"), queue)
        return resp.decode("UTF-8")

    def write(message, queue):
        queue.put(str(message))




class interpreter(cmd.Cmd):
    def __init__(self):
        self.stdout = self

    def do_help(self, line):
        self.write("Commands:")

        methods = type(self).__dict__
        for name in methods:
            if name[0:3] == "do_":
                self.write("  " + name[3:])

    def do_createtracker(self, line):
        args = line.split(" ")
        if len(args) > 1:
            self.write("Creating tracker file for {}".format(args[0]))
        else:
            self.write("Usage: createtracker filename description")

    def do_updatetracker(self, line):
        args = line.split(" ")
        if len(args) == 3:
            self.write("Updating tracker file {} for bytes {} to {}".format(args[0], args[1], args[2]))
        else:
            self.write("Usage: updatetracker filename start_bytes end_bytes")

    def do_GET(self, line):
        self.write(line)

    def do_REQ(self, line):
        args = line.split(" ")
        host, port = 'localhost', 666
        if len(args) == 1:
            host = args[0]
        elif len(args) == 2:
            host, port = args
        self.write("Requesting list of tracker files from tracker {}:{}".format(host, port))
        response = peer.send(peer, host, port, "<REQ LIST>", self.message_queue)

    def write(self, msg):
        self.message_queue.put(msg)
        pass

def main(stdscr):
    commands = interpreter()

    cli = clientInterface(stdscr, commands)
    commands.message_queue = cli.queue
    clientInterface.begin(cli)
    cli.inp.join()

    curses.curs_set(0)

    for process in cli.processes:
        process.join()

if __name__ == "__main__":
    curses.wrapper(main)
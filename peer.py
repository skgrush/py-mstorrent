#!/usr/bin/env python3

from clientInterface import *
import cmd
import curses

class peer(cmd.Cmd):
    def __init__(self):
        pass

    def do_help(self, line):
        self.write("Commands:")

        methods = type(self).__dict__
        for name in methods:
            if name[0:3] == "do_":
                self.write("  " + name[3:])

    def do_GET(self, line):
        self.write(line)

    def write(self, msg):
        self.message_queue.put(msg)
        pass


def main(stdscr):
    commands = peer()
    commands.stdout = commands

    cli = clientInterface(stdscr, commands)
    commands.message_queue = cli.queue
    clientInterface.begin(cli)
    cli.inp.join()

    curses.curs_set(0)

    for process in cli.processes:
        process.join()

if __name__ == "__main__":
    curses.wrapper(main)
#!/usr/bin/python3

import curses
import multiprocessing
import sys
import threading
import time


def f(q):
    time.sleep(10)
    q.put(str(multiprocessing.current_process()))

class clientInterface():

    def __init__(self, stdscr, commands, args):
        y, x, = stdscr.getmaxyx()
        self.scrolly, self.scrollx = 0, 0
        self.py, self.px = 100*y, x
        self.stdscr = stdscr
        self.user_input = curses.newwin(1, x, y-1, 0)
        self.pad = curses.newpad(self.py, self.px)
        self.linecount = 0

        self.queue = multiprocessing.Queue()
        self.inp = threading.Thread(name="input_recv", target=self.input_loop)
        self.receiver = threading.Thread(name="msg_recv", target=self.writer, daemon=True)
        self.commands = commands
        self.args = args

    def begin(self):
        self.inp.start()
        self.receiver.start()

    def draw_pad(self):
        y, x = self.stdscr.getmaxyx()
        sy, sx = self.scrolly, self.scrollx
        py, px = self.py, self.px
        self.pad.move(y+sy, 0)

        self.pad.noutrefresh(sy, sx, -sy, -sx, min(py, y-2), min(px, x -1))
        self.user_input.noutrefresh()

        curses.doupdate()

    def input_loop(self):
        y, x = self.user_input.getbegyx()[0], self.user_input.getmaxyx()[1]
        self.user_input.keypad(1)

        curses.echo(1)

        k = 0
        input_str = ""
        self.draw_pad()
        self.user_input.addstr("> ")

        while k != 27:
            k = self.user_input.getch()

            # Scrolling
            if k == curses.KEY_DOWN:
                self.scrolly += 1
            elif k == curses.KEY_UP:
                self.scrolly -= 1
            elif k == curses.KEY_LEFT:
                self.scrollx -= 1
            elif k == curses.KEY_RIGHT:
                self.scrollx += 1

            # Enter Key
            elif k == 10 or k == curses.KEY_ENTER:
                self.queue.put("> " + input_str)
                if input_str.lower() in ("quit", "exit"):
                    self.queue.put("Received EXIT signal, waiting on remaining processes...")
                    break
                self.user_input.clear()
                self.send_command(input_str)
                self.user_input.move(0, 0)
                self.user_input.addstr("> ")
                input_str = ""

            # Backspace
            elif k == curses.KEY_BACKSPACE:
                input_str = input_str[:-1]
                self.user_input.clear()
                self.user_input.move(0, 0)
                self.user_input.addstr("> {}".format(input_str[0:x-3]))

            # Detect changes in window size
            elif k == curses.KEY_RESIZE:
                y, x = self.stdscr.getmaxyx()[0] - 1, self.stdscr.getmaxyx()[1]
                self.user_input = curses.newwin(1, x, y, 0)
                self.user_input.keypad(1)
                self.user_input.addstr("> " + input_str[0:x-3])
                curses.doupdate()

            # General character input
            else:
                try:
                    input_str += chr(k)
                except Exception:
                    queue.put(str(k))

            # Bound scroll area
            self.scrollx = max(min(self.px - x, self.scrollx), 0)
            self.scrolly = max(min(self.linecount - y, self.scrolly), 0)
            self.draw_pad()


    def writer(self):
        while True:
            try:
                msg = self.queue.get()
                self.write_msg(msg)
            except Exception:
                break

    def write_msg(self, msg):
        if curses.isendwin():
            return

        y, x = self.stdscr.getmaxyx()
        py, px = self.pad.getmaxyx()
        for line in msg.strip("\r\n").split("\n"):
            try:
                self.pad.addstr(self.linecount % (py - 1), 0, str(line))
                self.linecount += 1 + int(len(line) / px)

                if self.linecount == y + self.scrolly:
                    self.scrolly += 1

                self.draw_pad()
            except Exception as err:
                self.write_msg(str(err))


    def send_command(self, msg):
        try:
            self.commands.onecmd(msg)
        except Exception as err:
            self.write_msg(str(err))

        #p = multiprocessing.Process(target = f, args = (self.queue,))
        #self.processes.append(p)
        #p.start()


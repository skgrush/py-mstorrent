import peer, curses

class Demo:
    def run(self, commandline):
        """ Runs the demo
        """
        commandline.command("help")
        commandline.command("gettracker 'Missouri S&T.jpg'")


if __name__ == "__main__":
    demo = Demo()
    curses.wrapper(peer.main, demo, "clientThreadConfig.cfg")

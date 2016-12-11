# py-mstorrent

#### Authors: Shawn McCormick, Samuel K. Grush

*general_intro*


## Requirements

Dependencies: Python 3.3 or newer. Peer additionally requires the curses module
which (reportedly) only comes with the standard Python distribution on *nix.


## Configuration

You can configure the peer and server with the config files
`clientThreadConfig.cfg` and `serverThreadConfig.cfg`, respectively.


## Usage

### Starting the server:

```ShellSession
./server.py
```

### Starting a peer:

```ShellSession
./peer.py
```

In the command line interface, type `help` to see the commands you can use.

### Final Submission usage:

Use `make` **from the source directory** to build the project. This will
create a `./tracker` executable and three peer directories containing `./peer`.

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Abstraction and handling of .track files.
"""

__license__ = "MIT"
__docformat__ = 'reStructuredText'

import re
import datetime
from ipaddress import IPv4Address

peer_update_interval = 15 * 60 #15 minutes by default
"""Peers will be forgotten after this many seconds."""


_re_md5 = re.compile('^[0-9a-f]{32}$', re.A|re.I)
"""Compiled RegEx object for matching MD5 hex digests"""

_DEFAULT_ENCODING = "utf-8"
""" Default encoding for .track file text"""


class MalformedTrackerFileException(Exception):
    pass

class trackerfile(tuple):
    """Abstracts .track file."""
    
    __slots__ = ()
    
    _metadata_fields = ('Filename', 'Filesize', 'Description', 'MD5')
    
    _fields = tuple( ( n.lower() for n in _metadata_fields ) )
    
    def __new__(cls, filename, filesize, description, md5):
        """Default :class:`.trackerfile` constructor.
        
        Alternative constructors :meth:`~.trackerfile.fromPath` and 
            :meth:`~.trackerfile.fromFileObject` are available.
        
        :param str filename: Name of the file being tracked
        :param int filesize: Size in bytes of the file
        :param str description: Description of the file
        :param str md5: MD5 hash of the file
        :returns: A new :class:`.trackerfile` instance
        :rtype: :class:`.trackerfile`
        :raises ValueError: if the value of an argument isn't acceptable
        :raises TypeError: if the value of an argument is drastically wrong
        """
        
        if not _re_md5.match(md5):
            raise ValueError("'md5' argument to trackerfile constructor must" \
                " be a 32 character hex string.")
        
        out = ( str(filename),
                int(filesize),
                str(description),
                str(md5),
                {})
        return super(trackerfile, cls).__new__(cls, out)
    
    
    @property
    def filename(self):     return self[0]
    
    @property
    def filesize(self):     return self[1]
    
    @property
    def description(self):  return self[2]
    
    @property
    def md5(self):          return self[3]
    
    @property
    def _peers(self):       return self[4]
    
    
    @classmethod
    def fromPath(cls, filepath):
        """Create a new :class:`.trackerfile` instance from a .track file.
        
        :param str filepath: Path to the .track file.
        :returns: A new :class:`.trackerfile` instance
        :rtype: :class:`.trackerfile`
        :raises TypeError: if *filepath* is an incompatible type
        :raises OSError: if there is a problem reading from *filepath*
        :raises: All exceptions raisable by :meth:`~.trackerfile.fromFileObject`
        """
        
        with open(filepath, 'r', encoding=_DEFAULT_ENCODING) as fl:
            return cls.fromFileObject( fl )
    
    
    @classmethod
    def fromFileObject(cls, fileobj, ignorelines=""):
        """Create a new :class:`.trackerfile` instance from a .track file.
        
        :param fileobj: Stream containing a .track file.
        :type fileobj: file-like object
        :param ignorelines: should contain characters that, if a line starts
            with them, will cause the line to be ignored.
        :type ignorelines: str or None
        :returns: a new :class:`.trackerfile` instance
        :rtype: :class:`.trackerfile`
        :raises MalformedTrackerFileException: if the file is malformed
        :raises RuntimeError: if something unexpected happens
        :raises ValueError: if *fileobj* is closed
        :raises TypeError: if an argument is of an incompatible type
        :raises: All exceptions raisable by :meth:`~.trackerfile.parseLine`
        """
        
        metadata = {}
        peers = {}
        
        for line in fileobj:
            parsedline = cls.parseLine(line, ignorelines)
            
            #pass line
            if not parsedline:
                continue
            
            #metadata line
            if len(parsedline) == 2:
                attr, val = parsedline
                
                if attr in metadata and metadata[attr] != val:
                    raise MalformedTrackerFileException("Duplicate metadata " \
                        "for {!r}".format(attr) )
                
                metadata[attr] = val
            
            #peer line
            elif len(parsedline) == 5:
                peer, values = parsedline[0:2], parsedline[2:]
                
                if peer in peers and peers[peer] != values:
                    raise MalformedTrackerFileException("Duplicate peer entry" \
                        " for peer {0[0]}:{0[1]}".format(peer) )
                
                peers[peer] = values
            
            #unexpected state
            else:
                raise RuntimeError("Reached unexpected state. {}.parseLine()" \
                    " returned a {!r}, expected a 2-tuple, 5-tuple, or None" \
                    ".".format(cls.__name__, parsedline) )
            
        for f in cls._fields:
            if f not in metadata:
                raise MalformedTrackerFileException("Missing metadata for " \
                        "{!r}".format(f) )
        
        #create a new trackerfile instance and add peers to it
        new_tracker = cls( *( metadata[f] for f in cls._fields ) )
        new_tracker._peers.update( peers )
        
        return new_tracker
    
    
    @classmethod
    def parseLine(cls, line, ignorelines=""):
        """Parses a line of a .track file.
        
        Essentially calls :meth:`~.trackerfile.parseMetadata`, 
        :meth:`~.trackerfile.parsePeer`, or passes based on line content.
        
        By default, ignores (returns None for) lines starting with '#'. Will
        additionally ignore lines starting with any character in *ignorelines*.
        
        :param str line: .track file line to be parsed
        :param str ignorelines: should contain characters that, if a line starts
            with them, will cause the line to be ignored.
        :returns: a 2-tuple (for a metadata line), a 5-tuple (for a peer line),
            or None (for a pass line).
        :rtype: tuple or None
        :raises AttributeError: if *line* isn't a string
        :raises TypeError: if *ignorelines* isn't iterable
        :raises RuntimeError: if an unexpected state is reached
        :raises: all exceptions raisable by :meth:`~.trackerfile.parseMetadata`
            and :meth:`~.trackerfile.parsePeer`
        """
        
        line = line.strip()
        
        if not line or line[0] == '#' or line[0] in ignorelines:
            return None
        
        #metadata line
        if line[0].isalpha():
            return cls.parseMetadata(line)
        
        #peer line
        if line[0].isdigit():
            return cls.parsePeer(line)
        
        #unexpected state
        raise RuntimeError("Reached unexpected state")
    
    
    @classmethod
    def parseMetadata(cls, line):
        """Parses a metadata line of a .track file.
        
        :param str line: metadata line to be parsed
        :returns: ( :class:`str` *attr*, :class:`str`|:class:`int` *value* )
            where attr is “filename”, ”filesize”, ”description”, or ”md5”
        :rtype: tuple
        :raises MalformedTrackerFileException: if *line* is malformed
        :raises TypeError, AttributeError: if *line* isn't a string
        """
        if ':' not in line:
            raise MalformedTrackerFileException("Invalid metadata line.")
        
        attr,value = line.split(':',1)
        
        if attr not in cls._metadata_fields:
            raise MalformedTrackerFileException("Bad .track line. Starts with" \
                    " alphabetical value {!r} which is not a valid metadata" \
                    " field.".format(split[0]) )
        
        value = value.strip()
        
        if attr == 'Filesize':
            if not value.isdigit():
                raise MalformedTrackerFileException("Bad metadata value. " \
                    "Filesize must be an integer, not {!r}.".format(value) )
            
            value = int(value)
        
        return (attr.lower(), value)
    
    
    @classmethod
    def parsePeer(cls, line):
        """Parses a peer line of a .track file.
        
        :param str line: peer line to be parsed
        :returns: ( :py:class:`~ipaddress.IPv4Address` *peer_ip*, 
                    :class:`int` *peer_port*,
                    :class:`int` *start_byte*,
                    :class:`int` *end_byte*,
                    :class:`~datetime.datetime` *last_timestamp* )
        :rtype: tuple
        :raises MalformedTrackerFileException: if the *line* is malformed
        :raises AttributeError: if *line* isn't a string
        :raises AddressValueError: if the peer ip isn't a valid IPv4 address
        :raises ValueError: if any of the components that should be ints aren't
        """
        parts = line.split(':',4)
        
        if len(parts) != 5:
            raise MalformedTrackerFileException("Wrong number of peer line " \
                    "components. Expected 5, got {}".format( len(parts) ) )
        
        parts[0] = IPv4Address( parts[0].strip() )
        
        # integerize parts 1-4
        for i in range(1,5):
            parts[i] = int( parts[i].strip() )
        
        parts[4] = datetime.datetime.utcfromtimestamp( parts[4] )
        
        return tuple( parts )
    
    
    def clean(self):
        """Removes out-of-date peers"""
        
        #threshold for dropping peers
        thresh = datetime.datetime.utcnow() - \
                 datetime.timedelta(peer_update_interval)
        
        for peer, values in self._peers.items():
            if values[2] < thresh:
                self.removePeer( *peer )
    
    
    def updatePeer(self, peer_ip, peer_port, start_byte, end_byte):
        """Update or add peer-line for (*peer_ip*, *peer_port*) pair.
        
        :param IPv4Address peer_ip: The peer's IP address
        :param int peer_port: The peer's port
        :param int start_byte: The first byte the peer has
        :param int end_byte: The last byte the peer has
        :raises AddressValueError: if *peer_ip* isn't a valid IPv4 address
        :raises ValueError, TypeError: if *peer_port*, *start_byte*, or
            *end_byte* aren't ints, or *start_byte* and *end_byte* form an
            invalid range
        """
        
        peer = IPv4Address(peer_ip),int(peer_port)
        startb,endb = int(start_byte),int(end_byte)
        
        if not (0 <= startb and startb <= endb and endb < self.filesize):
            raise ValueError("startb {} and endb {} is an invalid range for " \
                    "file of size {}".format(startb,endb,self.filesize) )
        
        self._peers[ peer ] = (startb, endb, datetime.datetime.utcnow())
    
    
    def removePeer(self, peer_ip, peer_port):
        """Remove (*peer_ip*, *peer_port*) pair if it exists.
        
        :param IPv4Address peer_ip: IP of peer to be removed
        :param int peer_port: port of peer to be removed
        :returns: True if pair was removed, False if pair not found.
        :rtype: bool
        :raises AddressValueError: if *peer_ip* isn't a valid IPv4 address
        :raises TypeError,ValueError: if *peer_port* isn't an int
        """
        
        peer = IPv4Address(peer_ip),int(peer_port)
        
        try:
            del self._peers[peer]
            return True
        
        except KeyError:
            return False
    
    
    def _metadataGenerator(self):
        """Line generator for metadata"""
        
        for i in range( len(self._metadata_fields) ):
            yield "{}: {}".format( self._metadata_fields[i], self[i] )
    
    
    def _peerGenerator(self):
        """Line generator for peers"""
        
        for peer,values in self._peers.items():
            #       IP     port   sbyte  ebyte
            yield "{0[0]}:{0[1]}:{1[0]}:{1[1]}:{2}".format( peer,values,
                                                int(values[2].timestamp()) )
    
    
    def toString(self):
        """Output as .track file format.
        
        :returns: The tracker file in the .track file format.
        :rtype: str
        """
        output = "\n".join( self._metadataGenerator() )
        output += "\n" + "\n".join( self._peerGenerator() )
        return output
    
    
    def writeTo(self, fileobj):
        """Writes the tracker file to *fileobj* in the .track file format.
        
        Does not close *fileobj*. Only requires ``fileobj.write()`` method.
        
        :param fileobj: The file to be written to
        :type fileobj: file-like object
        :raises OSError,ValueError,AttributeError: If *fileobj* isn't writable
        """
        
        #write metadata
        for line in self._metadataGenerator():
            fileobj.write( line + "\n" )
        
        #write peers
        for line in self._peerGenerator():
            fileobj.write( line + "\n" )
    
    def writeToSocket(self, sock):
        """Writes the tracker file to *sock* in the .track file format.
        
        Does not close *sock*. 
        
        :param sock: The file to be written to
        :type sock: :class:`~socket.socket`
        """
        
        #write metadata
        for line in self._metadataGenerator():
            sock.sendall( bytes(line + "\n", *apiutils.encoding_defaults) )
        
        #write peers
        for line in self._peerGenerator():
            sock.sendall( bytes(line + "\n", *apiutils.encoding_defaults) )
    
    
    
    
    

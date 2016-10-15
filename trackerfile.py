#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Abstraction and handling of .track files.
"""

import re


_re_md5 = re.compile('^[0-9a-f]{32}$', re.A|re.I)
"""Compiled RegEx object for matching MD5 hex digests"""


class MalformedTrackerFileException(Exception):
    pass

class trackerfile(tuple):
    """Abstracts .track file."""
    
    __slots__ = ()
    
    def __new__(cls, filename, filesize, description, md5):
        
        if not _re_md5.match(md5):
            raise ValueError("'md5' argument to trackerfile constructor must" \
                " be a 32 character hex string.")
        
        out = tuple(str(filename),
                    int(filesize),
                    str(description),
                    md5,
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
    def fromFilepath(cls, filepath):
        """Create a new trackerfile instance from a .track file.
        
        NotYetImplemented
        """
        pass
    
    @classmethod
    def parseLine(cls, line):
        """Parses a line of a .track file.
        
        Essentially calls parseMetadata(), parsePeer(), or passes based on line
        content.
        
        Returns a 2-tuple (for a metadata line), a 5-tuple (for a peer line),
        or None (for a pass line). Otherwise raises an exception.
        
        NotYetImplemented
        """
        pass
    
    @staticmethod
    def parseMetadata(line):
        """Parses a metadata line of a .track file.
        
        Returns tuple( str attr, str|int value )
        where attr={“filename”, ”filesize”, ”description”, ”md5”}
        Otherwise raises an exception.
        
        NotYetImplemented
        """
        pass
    
    @staticmethod
    def parsePeer(line):
        """Parses a peer line of a .track file.
        
        Returns ( IPv4Address peer_ip, int peer_port, int start_byte, 
                  int end_byte, datetime.datetime last_timestamp )
        Otherwise raises an exception.
        
        NotYetImplemented
        """
        pass
    
    
    def clean(self):
        """Removes out-of-date peers
        
        NotYetImplemented
        """
        pass
    
    
    def updatePeer(self, peer_ip, peer_port, start_byte, end_byte):
        """Update or add peer-line for (peer_ip, peer_port) pair.
        
        NotYetImplemented
        """
        pass
    
    
    def removePeer(self, peer_ip, peer_port):
        """Remove (peer_ip, peer_port) pair if it exists.
        
        Returns True if pair was removed, False if pair not found.
        
        NotYetImplemented
        """
        pass
    
    
    def toString(self):
        """Output as .track file format.
        
        Returns a string.
        
        NotYetImplemented
        """
        pass
    
    
    def writeTo(self, fileobj):
        """Writes the tracker file to fileobj in the .track file format.
        
        Does not close fileobj. Only requires fileobj.write() method.
        
        NotYetImplemented
        """
        pass
    
    
    

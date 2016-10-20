#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parser for ".cfg" files as defined in project spec.

There are two ways to create configfile (subclass) instances:

    1. Use :meth:`.fromFile`. This will handle all instantiation needs.
    2. Create a new :class:`ServerConfig` or :class:`ClientConfig`
       instance, then call :meth:`.readIn` and :meth:`.parseContents`.

If these steps are not followed, operations may raise 
:exc:`NotFullyInstantiated`.

After an instance is created, call :meth:`.validate` to make sure the contents
are valid.

Attributes:
    DEFAULT_MAX_READ (int): the maximum number of bytes to read from file.
    IGNORE_COMMENT_LINES (bool): Whether or not to ignore #comment lines.
"""

import os
import os.path
from ipaddress import IPv4Address,AddressValueError

DEFAULT_MAX_READ = 1024
IGNORE_COMMENT_LINES = True

def dirmaker(val):
    """Utility function for checking for the existence of a directory, and
    creating it if it doesn't exist.
    
    Will **not** create the parent directory of *val* if it doesn't exist.
    
    Args:
        val (str): Path to the desired directory. 
    
    Returns:
        bool: True if the directory exists or was created; False if not.
    
    Raises:
        FileNotFoundError: If the parent directory of *val* doesn't exist.
    """
    val = os.path.abspath(val)
    
    if os.path.isdir(val):
        return True
    
    print("No such directory {!r}. I'll make it!".format(val))
    parentdir = os.path.dirname(val)
    
    #if the parent directory does exist
    if os.path.exists( parentdir ):
        parent_mode = os.stat(parentdir).st_mode
        os.mkdir(val, parent_mode)
        
        return os.path.exists(val)
    
    raise FileNotFoundError(2,"No such directory {!r}".format(parentdir),
                                                                  parentdir)



class NotFullyInstantiated(RuntimeError):
    """Raised when an operation couldn't be executed because the config hasn't
    been fully instantiated."""
    pass

class InvalidCfg(RuntimeError):
    """Raised when an operation couldn't be executed because the config is 
    invalid.
    """
    pass

class cfgfile:
    """Base class for config file abstractions.
    
    Note:
        Should use :class:`ServerConfig` or :class:`ClientConfig`, rather than
        using this directly.
        I suppose you can use it, but it doesn't validate data.
    """
    
    
    @property
    def cfgPath(self):
        """str: Path to the config file."""
        return self.__path
    
    @property
    def cfgContents(self):
        """str: string contents of the config file.
        
        Raises:
            NotFullyInstantiated: if :meth:`.readIn` hasn't been called.
        """
        if self.__contents is None:
            raise NotFullyInstantiated
        
        return self.__contents
    
    @property
    def cfgLines(self):
        """tuple of str: strings of the lines of the config file.
        
        Raises:
            NotFullyInstantiated: if :meth:`.parseContents` hasn't been
                called.
        """
        if self.__lines is None:
            raise NotFullyInstantiated
        
        return self.__lines
    
    @property
    def cfgValues(self):
        """tuple: interpolated values from the config file.
        
        If :meth:`.parseContents` hasn't been called, will be empty.
        """
        return self.__values
    
    
    def __init__(self, path, maxread=None):
        if maxread is None:
            maxread = DEFAULT_MAX_READ
        
        self.__path = os.path.abspath(path)
        self.cfgMaxread = int(maxread)
        self.__contents = None
        self.__lines = None
        self.__values = ()
        self.__valid = None
    
    
    def exists(self):
        """Whether or not the config file exists at its path.
        
        Returns:
            bool
        """
        return os.path.exists(self.cfgPath)
    
    
    def readIn(self):
        """Read the contents of the config file into :attr:`cfgContents`.
        
        Sets :attr:`cfgContents` attribute.
        """
        with open(self.cfgPath, 'r', encoding='utf-8') as fl:
            self.__contents = fl.read( self.cfgMaxread )
    
    
    def parseContents(self):
        """Parse :attr:`cfgContents` into :attr:`cfgValues`.
        
        Sets :attr:`cfgLines` and :attr:`cfgValues` attributes.
        
        Raises:
            NotFullyInstantiated: if :meth:`.readIn` hasn't been called.
        """
        self.__lines = self.cfgContents.splitlines()
        values = []
        
        for line in self.cfgLines:
            line = line.strip()
            
            if line.isdigit():
                values.append( int(line) )
                continue
                
            try:
                values.append( IPv4Address(line) )
                continue
            except AddressValueError:
                pass
            
            if IGNORE_COMMENT_LINES and line.startswith('#'):
                continue
            
            values.append( line )
        
        self.__values = tuple(values)
    
    
    def validate(self):
        
        #if already validated, just return it
        if self.__valid is not None:
            return self.__valid
        
        #if not instantiated, raise
        if self.cfgLines is None:
            raise NotFullyInstantiated
        
        try:
            self.__valid = self._validate()
        except:
            self.__valid = False
        
        return self.__valid
    
    
    def _validate(self):
        """Internal validation, overloaded by subclass."""
        raise NotImplementedError
    
    
    @classmethod
    def fromFile(cls, path, maxread=DEFAULT_MAX_READ):
        """Read from *path*, and fully instantiate the class instance.
        
        Calls :meth:`.readin` and :meth:`parseContents` so you don't have to!
        """
        inst = cls(path,maxread)
        
        if not inst.exists():
            return False
        
        inst.readIn()
        inst.parseContents()
        
        return inst
    
    
    def __getitem__(self, i):
        """Getter for :attr:`cfgValues`.
        
        Raises:
            NotFullyInstantiated: if :meth:`parseContents` hasn't been called.
        """
        if self.cfgLines is None:
            raise NotFullyInstantiated
        
        return self.cfgValues[i]
    
    
    def __len__(self):
        """The length of :attr:`cfgValues`.
        
        Always returns, even if not fully instantiated.
        """
        return len(self.cfgValues)


class ClientConfig(cfgfile):
    """Client config file abstraction.
    
    Spec defines that *"First 2 lines are port no and IP address of the tracker
    server, and last line is the periodic updatetracker interval in seconds"*.
    
    We additionally define the third line to be the peer folder.
    """
    
    def _validate(self):
        
        firsttwo = ( type(self[0]), type(self[1]) )
        
        return (
            int in firsttwo
            and
            IPv4Address in firsttwo
            and
            isinstance( self[2], str )
            and
            isinstance( self[-1], int )
        )
    
    
    @property
    def serverPort(self):
        """ClientConfig-specific attribute, port of the tracker server.
        
        Should be first or second line of config.
        """
        if not self.validate():
            raise InvalidCfg
        
        return self[0] if isinstance(self[0],int) else self[1]
    
    @property
    def serverIP(self):
        """ClientConfig-specific attribute, IP of the tracker server
        
        Should be first or second line of config.
        """
        if not self.validate():
            raise InvalidCfg
        
        return self[1] if isinstance(self[0],int) else self[0]
    
    @property
    def peerFolder(self):
        """ClientConfig-specific attribute, name of local peer storage.
        
        NOT DEFINED BY SPEC.
        Should be third line of config.
        """
        if not self.validate():
            raise InvalidCfg
        
        return self[2]
    
    @property
    def updateInterval(self):
        """ClientConfig-specific attribute, client updatetracker interval.
        
        Should be the last line of config.
        """
        if not self.validate():
            raise InvalidCfg
        
        return self[-1]



class ServerConfig(cfgfile):
    """Server config file abstraction.
    
    Spec defines that *"[f]irst line is the port no to which the peer listens...
    and last line is the name of the shared folder"*.
    """
    
    def _validate(self):
        
        return (
            isinstance(self[0],int)
            and
            isinstance(self[-1],str)
        )
    
    @property
    def listenPort(self):
        """ServerConfig-specific attribute, which port to listen on.
        
        Should be the first line of config.
        """
        if not self.validate():
            raise InvalidCfg
        
        return self[0]
    
    
    @property
    def sharedFolder(self):
        """ServerConfig-specific attribute, local directory for .track files.
        
        Should be the last line of config.
        """
        if not self.validate():
            raise InvalidCfg
        
        return self[-1]

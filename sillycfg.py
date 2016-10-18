#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parser for ".cfg" files as defined in project spec.

There are two ways to create configfile (subclass) instances:

First is to use *subclass*.fromFile(), where *subclass* is :class:`ServerConfig`
or :class:`ClientConfig`, as appropriate. This will handle all instantiation
needs.

Second is to create a new :class:`ServerConfig` or :class:`ClientConfig`
instance, then call *inst*.readIn() and *inst*.parseContents().

If these steps are not followed, operations may raise 
:exception:`NotFullyInstantiated`.

After an instance is created, call *inst*.validate() to make sure the contents
are valid.


"""

import os
import os.path
from ipaddress import IPv4Address,AddressValueError

DEFAULT_MAX_READ = 1024
IGNORE_COMMENT_LINES = True

def dirmaker(val):
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
    full instantiated been."""
    pass

class InvalidCfg(RuntimeError):
    """Raised when an operation couldn't be executed because the config is 
    invalid.
    """
    pass

class cfgfile:
    
    
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
        """Read the contents of the config file into cfgContents.
        
        Sets cfgContents attribute.
        """
        with open(self.cfgPath, 'r', encoding='utf-8') as fl:
            self.__contents = fl.read( self.cfgMaxread )
    
    
    def parseContents(self):
        """Parse cfgContents into cfgValues.
        
        Sets cfgLines and cfgValues attributes.
        
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
        """Getter for cfgValues.
        
        Raises:
            NotFullyInstantiated: if :meth:`parseContents` hasn't been called.
        """
        if self.cfgLines is None:
            raise NotFullyInstantiated
        
        return self.cfgValues[i]
    
    
    def __len__(self):
        """The length of cfgValues.
        
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
        if not self.validate():
            raise InvalidCfg
        
        return self[0] if isinstance(self[0],int) else self[1]
    
    @property
    def serverIP(self):
        if not self.validate():
            raise InvalidCfg
        
        return self[1] if isinstance(self[0],int) else self[0]
    
    @property
    def peerFolder(self):
        if not self.validate():
            raise InvalidCfg
        
        return self[2]
    
    @property
    def updateInterval(self):
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
        if not self.validate():
            raise InvalidCfg
        
        return self[0]
    
    
    @property
    def sharedFolder(self):
        if not self.validate():
            raise InvalidCfg
        
        return self[-1]

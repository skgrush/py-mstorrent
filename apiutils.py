#!/usr/bin/env python3
# -*- coding: utf-8 -*

__license__ = "MIT"


import re
import urllib.parse

re_apicommand = re.compile("^<(?P<command>[a-z]+)(?P<args>( [^ >]+)*)>\r?$",re.I|re.M)
"""`RegEx object`: pattern to match an API command line.

Matches lines such as:
``<createtracker filename.txt 12586 some_words 0123456789ABCDEF... 1.1.1.1 0>``
"""

default_encoding = 'utf-8'
"""str: encoding to use when encoding/decoding API messages."""

default_encoding_errors = 'replace'
"""str: error handling scheme for encoding/decoding API messages."""

encoding_defaults = (default_encoding,default_encoding_errors)
"""tuple: convenience value containing (:data:`.default_encoding, 
:data:`default_encoding_errors`)"""

def arg_encode(arg):
    """Encoding function for API data.
    
    This is a convenience function to allow encoding to uniformly change.
    """
    return urllib.parse.quote_plus(arg)

def arg_decode(arg):
    """Decoding function for API data.
    
    This is a convenience function to allow encoding to uniformly change.
    """
    return urllib.parse.unquote_plus(arg)

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
default_encoding_errors = 'replace'
encoding_defaults = (default_encoding,default_encoding_errors)

def arg_encode(arg):
    return urllib.parse.quote_plus(arg)

def arg_decode(arg):
    return urllib.parse.unquote_plus(arg)

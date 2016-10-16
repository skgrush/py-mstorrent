#!/usr/bin/env python3
# -*- coding: utf-8 -*


import re
import urllib.parse

re_apicommand = re.compile("^<(?P<command>[a-z]+)(?P<args>( [^ >]+)+)>\r?$",re.I|re.M)

default_encoding = 'utf-8'
default_encoding_errors = 'replace'

def arg_encode(arg):
    return urllib.parse.quote_plus(arg)

def arg_decode(arg):
    return urllib.parse.unquote_plus(arg)

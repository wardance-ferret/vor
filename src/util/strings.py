#!/usr/bin/python

# Some utility functions for vivo to process a string read from a file.
# Todo: make a true module.

import os, re, string, sys, getopt, urllib

def make_query_string_http_safe(s):
        #replace special characters in output using %xx, except when the original string has: 
        #(1) space, which should be converted to 'plus' sign instead of %20, and 
        #(2) percent '%'        
        return urllib.quote_plus(s, '%')

def make_string_http_safe(s):
        #replace special characters in output using %xx
        return urllib.quote(s)
        
def to_lower(s):
    return string.lower(s)
        
#Collected methods for trimming whitespace:
#--all spaces
def remove_whitespace(s):
    return re.sub('\s+','',s)
#--leading and trailing space only
def trim(s):
    trimmed = re.sub('^\s+','',s)
    trimmed = re.sub('\s+$','',trimmed)
    return trimmed
#--reduce multiple spaces to a single space
def squinch(s):
    return string.replace("  "," ",s)

#prints string as utf-16 to Windows console (which, by default, has code page cp437).  This means no exception gets raised by codecs (good!) and the wide characters are garbled.
#todo: print UTF-8 string to Windows console by first replacing wide characters with '?'
def print_safe(myString):
    #if this is a windows machine http://stackoverflow.com/questions/1325581/how-do-i-check-if-im-running-on-windows-in-python
    if os.name=="nt":
        print myString.encode('utf-16be')
    else:
        print myString

if __name__ == "__main__":
        print "strings.py contains utilities for string processing."
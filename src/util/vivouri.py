#!/usr/bin/python

#class VivoUri has static functions for handling Vivo URIs for harvester.  There should not be many classes here. (We should rely instead on what rdflib provides to handle URIs.) I don't expect this code will grow.
import re
import string
import requests
import logging
import uuid
import random

class VivoUriException(Exception):
    def __init__(self, message):
        logging.error(message)

class VivoUri:
        #create a new Vivo URI in the specified domain.  a DataSource would invoke this in order to create a new graph resource.
        #todo: figure out whether this is should be static or tied to a DataSource (which would have its own uniform Vivo Domain).
        @staticmethod
        def createUri(domain, prefix='n'):
            random.seed(uuid.uuid4())
            return VivoUri.encodeNasUri(domain,str(prefix)+str(random.randint(0,9999999999)))
        
        #given a Vivo URI string, extract the n# identifier
        @staticmethod
        def extractNfromUri(uriString):
                m = re.search("http://", uriString)
                if m and len(m.groups()) == 0:
                    parts = uriString.rsplit("/", 1)
                    return string.strip(parts[1]) 
                else:
                    raise VivoUriException(uriString+" is not a well-formed URI string")
                
        #create an output file name at the same path as the uri path, where the output file name is the name of the uri file prefixed by a label "toolname" for the tool that created the output file.  
        @staticmethod
        def createOutputFileName(uriString, toolname):
                parts = uriString.rsplit("/",1)
                return string.strip(parts[0]) + "/" + string.strip(toolname) + "-" + string.strip(parts[1])

                
        @staticmethod
        def extractUriPrefix(uriString):
                parts = uriString.rsplit("/", 1)
                return string.strip(parts[0])

        @staticmethod
        def extractNamespace(uriString):
                protocol_parts = uriString.split("http://", 1)
                uri_parts = protocol_parts[1].split("/",1)
                return "http://"+uri_parts[0]+"/"
                
                
        @staticmethod
        def hasHttpPrefix(uriString):
            if uriString is None or uriString=="":
                return False
            if re.search(r"http://", uriString):
                return True
            else:
                return False
                
        @staticmethod
        def hasFilePrefix(uriString):
            if re.search(r"file://",uriString):
                return True
            else:
                return False
       
        #TODO:  what is this for? is it for extracting quoted unicode from the string form of an RDFLib term?
        @staticmethod
        def extractUnicodeString(s):
            m = re.search(r"u'([^']+)'",s)
            
            if m:
                if m.groups > 1:
                    return string.strip(m.group(1))
                
            return ""
        
        #if we delete the suffix 'individual/' on vivoLocationPrefix, then pubgui.py or pubtool.py will break, so we preserve it. 
        @staticmethod
        def encodeNasUri(vivoLocationPrefix, n):
                m = re.match(r"^.+individual$", vivoLocationPrefix)
                
                if m:
                    return vivoLocationPrefix+"/"+n
                else:
                    return vivoLocationPrefix+'individual/' + n
                
                
        #send an HTTP request to a servlet and return the JSON response        
        @staticmethod
        def sendHttpRequest(HttpQueryString):
            try:
                        
                resp = requests.get(HttpQueryString)
                if (resp.status_code == 200):
                    data = resp.json()
                    print data
            except:
                raise VivoUriException("Couldn't get response to HTTP request, there was a connection error")
                
            #returns a multidimensional array (JSON format), where (in the case of Vivo) we are interested in row 0, the first record (which has data from the HTTP response) 
            return data    
                

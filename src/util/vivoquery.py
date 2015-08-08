#!/usr/bin/python
import json, urllib, logging
from strings import print_safe


class VIVOQueryException(Exception):
    pass

#Encapsulates info to query Vivo using Fuseki SPARQL endpoint and store results 
class VIVOQuery:

    #Location of the Fuseki service.  (note: it is not a triple quoted string, so we can interpolate a string value at %s)
    URL = 'http://myvivoschool:3030/VIVO/query?%s'



    def __init__(self):
        self._output = 'json'
        self._handle = None

    def _processQuery(self,query):
        params = urllib.urlencode({'query':query,'output':self._output})
        result = None
        try:
            self._handle = urllib.urlopen(VIVOQuery.URL % params)
            logging.debug(VIVOQuery.URL % params)
            result = self._handle.read()
            self._handle.close()
        except IOError as e:
            raise VIVOQueryException(str(e))
        except Exception as f:
            raise VIVOQueryException(str(f))
        return self._processResult(json.loads(result)['results']['bindings'])
    #learn: Obviously this method must be overridden, and there's no @override decoration.
    def _processResult(self, result):   
        return None

class VIVOAuthorName:
    def __init__(self, f, m, l):
        print 'first name: ',
        print_safe(f)
        print 'middle name: ',
        print_safe(m)
        print 'last name: ',
        print_safe(l)
        self.firstName = f
        self.middleName = m
        self.lastName = l
    
    def getFirstName(self):
        return self.firstName
    def getLastName(self):
        return self.lastName
    def getMiddleName(self):
        return self.middleName

class VIVOAuthorNameQuery(VIVOQuery):
    
    conn = None

    def __init__(self):
        VIVOQuery.__init__(self)

    def _processResult(self, result):
        if (len(result) > 0):
            logging.debug("VIVOAuthorNameQuery found a result "+str(result)+" for query")
            if ('middleName' in result[0]):
                return VIVOAuthorName(result[0]['firstName']['value'], result[0]['middleName']['value'], result[0]['lastName']['value'])
            else:
                return VIVOAuthorName(result[0]['firstName']['value'], "", result[0]['lastName']['value'])                
        return None

    def _query(self, uri):
        return "PREFIX foaf: <http://xmlns.com/foaf/0.1/> PREFIX vivo:<http://vivoweb.org/ontology/core#> SELECT DISTINCT ?firstName ?middleName ?lastName WHERE { <%s> foaf:firstName ?firstName . OPTIONAL{ <%s> vivo:middleName ?middleName . } <%s> foaf:lastName ?lastName . }" % (uri, uri, uri)
        
    @classmethod
    def getName(c, uri):
        print "-"*32
        print uri
        if c.conn == None:
            c.conn = c()
        return c.conn._processQuery(c.conn._query(uri))

class VIVOPublicationQuery(VIVOQuery):

    conn = None
    
    def __init__(self):
        VIVOQuery.__init__(self)
        
    def _processResult(self, result):
        if (len(result) > 0):
            logging.debug("VIVOPublicationQuery found a result "+str(result)+" for query")
            return result[0]['individual']['value']
        return None
        
    def _query(self, pub_uid, pub_uid_class="bibo:pmid"):
        return "PREFIX bibo:<http://purl.org/ontology/bibo/> SELECT DISTINCT ?individual WHERE { ?individual %s '%s' }" % (pub_uid_class, pub_uid)
        
    @classmethod
    def getURI(c, pub_uid, pub_uid_class="bibo:pmid"):
        print "-"*32
        print pub_uid
        print pub_uid_class
        if c.conn == None:
            c.conn = c()
        return c.conn._processQuery(c.conn._query(pub_uid, pub_uid_class))    

#goal: by accepting a query string as a param, allow querying on any class of individual
class VIVOIndividualQuery(VIVOQuery):
    
    conn = None
    
    def __init__(self):
        VIVOQuery.__init__(self)
        
    def _processResult(self, result):
        if (len(result)> 0 ):
            logging.debug("VIVOIndividualQuery found a result for query "+str(self._query))
            return result
        else:
            logging.debug("VIVOIndividualQuery found no result for query "+str(self._query))
            return None
            
    def _query(self, querystring):
        return querystring
        
    @classmethod
    def getURIs(c,querystring):
        print "-"*32
        if c.conn == None:
            c.conn = c()
        return c.conn._processQuery(c.conn._query(querystring))          
        
            
#test Vivo on a URI (is this an individual?)
#if it is the subject of at least one triple, it is
class VIVOIndividualPresentQuery(VIVOQuery):

    conn = None 

    def __init__(self):
        VIVOQuery.__init__(self)

    def _processResult(self, result):
        logging.debug("Found "+str(len(result))+" results for query")
        return (len(result) > 0)

    def _query(self, uri):
        return "SELECT * WHERE {<%s> ?p ?o }" % uri
        
    @classmethod
    def isPresent(c,uri):
        if c.conn == None:
            c.conn = c()
        return c.conn._processQuery(c.conn._query(uri))

        
#query Vivo on DOI 
class VIVODOIPresentQuery(VIVOQuery):

    #is this a class field or instance field?
    conn = None 

    def __init__(self):
        VIVOQuery.__init__(self)

    def _processResult(self, result):
        return (len(result) > 0)

    def _query(self, doi):
        return "PREFIX bibo:<http://purl.org/ontology/bibo/> SELECT DISTINCT ?individual WHERE { ?individual bibo:doi '%s' }" % doi
        
    @classmethod
    def isPresent(c,doi):
        if c.conn == None:
            c.conn = c()
        return c.conn._processQuery(c.conn._query(doi))
        
        
#query Vivo on PMID, an identifier# of PubMed publications 
class VIVOPMIDPresentQuery(VIVOQuery):

    #is this a class field or instance field?
    conn = None 

    def __init__(self):
        VIVOQuery.__init__(self)

    def _processResult(self, result):
        return (len(result) > 0)

    def _query(self, pmid):
        return "PREFIX bibo:<http://purl.org/ontology/bibo/> SELECT DISTINCT ?individual WHERE { ?individual bibo:pmid '%s' }" % pmid

    #like an instance method accepts an instance as the first argument (usually 'self'), 
    #a class method accepts a class as the first argument.
    #Like a function decorated with @staticmethod (analogous to the Java static keyword), this decorated function can be called on an instance or a class.  However, a @staticmethod decorated function does *not* accept an implied first argument (the first arg in the formal parameter list is "implied" when it is omitted from the actual parameter list of the calling function).  In other words, it's often said that @staticmethod on method() tells Python not to create a bound method when you call object_instance.method().
    #
    #So...why decorate with @classmethod here?
    #1.  only one attr conn per class c, not per instance of vivo query
    #2.  a connection must be instantiated by calling the constructor for this class , c()
    #3.  a connection both prepares the query and processes it
    @classmethod
    def isPresent(c,pmid):
        if c.conn == None:
            c.conn = c()
        return c.conn._processQuery(c.conn._query(pmid))
        
    
        
#Query Vivo on ISSN #, an identifier of pub venues      
class VIVOIssnQuery(VIVOQuery):

    #is this a class field or instance field?
    conn = None 

    def __init__(self):
        VIVOQuery.__init__(self)

    def _processResult(self, result):
        return (len(result) > 0)

    def _query(self, issn):
        return "PREFIX bibo:<http://purl.org/ontology/bibo/> SELECT DISTINCT ?individual WHERE { ?individual bibo:issn '%s' }" % issn

    #like an instance method accepts an instance as the first argument (usually 'self'), 
    #a class method accepts a class as the first argument.
    #Like a function decorated with @staticmethod (analogous to the Java static keyword), this decorated function can be called on an instance or a class.  However, a @staticmethod decorated function does *not* accept an implied first argument (the first arg in the formal parameter list is "implied" when it is omitted from the actual parameter list of the calling function).
    #So...why decorate with @classmethod here?
    @classmethod
    def isPresent(c,issn):
        if c.conn == None:
            c.conn = c()
        return c.conn._processQuery(c.conn._query(issn))
        
        
class VIVOAuthorAsCitedQuery(VIVOQuery):

    #is this a class field or instance field?
    conn = None 

    def __init__(self):
        VIVOQuery.__init__(self)

    def _processResult(self, result):
        return (len(result) > 0)

    def _query(self):
        return "PREFIX rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#> PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> PREFIX vivo:<http://vivoweb.org/ontology/core#> SELECT ?author ?author_label ?authorship ?author_as_listed WHERE { ?authorship rdf:type vivo:Authorship . ?authorship vivo:linkedAuthor ?author . ?authorship rdfs:label ?author_as_listed . OPTIONAL { ?author rdfs:label ?author_label } }"

    #like an instance method accepts an instance as the first argument (usually 'self'), 
    #a class method accepts a class as the first argument.
    #Like a function decorated with @staticmethod (analogous to the Java static keyword), this decorated function can be called on an instance or a class.  However, a @staticmethod decorated function does *not* accept an implied first argument (the first arg in the formal parameter list is "implied" when it is omitted from the actual parameter list of the calling function).
    #So...why decorate with @classmethod here?
    @classmethod
    def isPresent(c):
        if c.conn == None:
            c.conn = c()
        return c.conn._processQuery(c.conn._query())        
       
if __name__ == '__main__':

    print "usage: except for testing, don't call vivoquery.py as a script.\n"
    
    #Invoke class methods (no object instances are created)
    print "Getting author name info for: "
    print VIVOAuthorNameQuery.getName('http://vivo.health.unm.edu/individual/n4013')
    print "\n"
    #print "Checking for ISSN 1097-6825:"
    #print "-" * 32 
    #print VIVOIssnQuery.isPresent('1097-6825')
    #print "\n"
    #print "Is indiv http://unr.vivo.ctr-in.org/individual/n6130 present?"
    #print "-" * 32
    #print str(VIVOIndividualPresentQuery.isPresent('http://unr.vivo.ctr-in.org/individual/n6130')) 
    #print "\n"
    #print "Getting author name info for: "
    #print VIVOAuthorNameQuery.getName('http://unr.vivo.ctr-in.org/individual/n6130')
    #print "\n"
    print "Getting all Vivo authors, as cited"
    VIVOAuthorAsCitedQuery.isPresent()

    
    #Helpful? resources
    #=================
    #http://stackoverflow.com/questions/114214/class-method-differences-in-python-bound-unbound-and-static
    #http://2ndscale.com/rtomayko/2004/the-static-method-thing
    
    

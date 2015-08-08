#!/usr/bin/python
import logging
import rdflib

from rdflib import plugin
from rdflib.graph import Graph
from rdflib.namespace import Namespace
from pprint import pprint
from vivouri import VivoUri
from vivoquery import VIVOIndividualPresentQuery

#vivodata.py (v0.2) differs from the earlier versions not only because it can handle RDF edits involving
#Collaborations (as vivodata.py v0.1 can), but it does not call removeCollaboration() when removePublication() is called. 


plugin.register(
    'sparql', rdflib.query.Processor,
    'rdfextras.sparql.processor', 'Processor')

plugin.register(
    'sparql', rdflib.query.Result,
    'rdfextras.sparql.query', 'SPARQLQueryResult')

class DataSourceException(Exception):
    def __init__(self, message):
        logging.error(message)
    
class NSManager:
    ns={}

    def __init__(self):
        NSManager.ns['vivo'] = 'http://vivoweb.org/ontology/core#'
        NSManager.ns['rdfs'] = 'http://www.w3.org/2000/01/rdf-schema#'
        NSManager.ns['foaf'] = 'http://xmlns.com/foaf/0.1/'
        NSManager.ns['bibo'] = 'http://purl.org/ontology/bibo/'
        NSManager.ns['rdf'] = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
    
class DataSource:
    VIVO = Namespace('http://vivoweb.org/ontology/core#')
    RDFS = Namespace('http://www.w3.org/2000/01/rdf-schema#')
    FOAF = Namespace('http://xmlns.com/foaf/0.1/')
    BIBO = Namespace('http://purl.org/ontology/bibo/')
    RDF = Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
    
    nsmanager = NSManager()

    #a string uri must be converted to correct argument type for the remove* methods by calling DataSource.uri_literal_as_ref(stringUri)
    #TODO: this is very confusing. I need a doc to explain the difference between a URI string and a RDF Lib term (like a URI reference or Literal).
    @staticmethod
    def uri_literal_as_ref(string):  
        return rdflib.term.URIRef(string)
        
    @staticmethod
    def string_as_literal(string):
        return rdflib.term.Literal(string)
    
    @staticmethod
    def pretty_print_rdf_term(rdf_term):
        label=""
        if (rdf_term is None):
            label = "[]"
        elif not VivoUri.hasHttpPrefix(rdf_term):
            #must be some label
            label=unicode(rdf_term).encode("utf-8")
        else:
            label=unicode(VivoUri.extractNfromUri(rdf_term)).encode("utf-8")
            if label=="":
                #TODO: decide how to handle RDFLib terms that don't seem to have unicode strings
                label=""
            if VivoUri.hasHttpPrefix(label):
                label=unicode(VivoUri.extractNfromUri(label)).encode("utf-8") 
        return label
    
    #Some core methods that don't care about the kind of Vivo individual (i.e. the Class URI).
    #These are likely to be kept.
    def __init__(self, inputfile=None):
        self._graph = Graph()
        if inputfile is not None:
            try:
                self._graph.parse(inputfile)
                self._filename = inputfile
            except:
                logging.getLogger(__name__).exception("there was a problem opening "+inputfile+" as a datasource")
                raise DataSourceException("there was a problem opening "+inputfile+" as a datasource")

    def serialize(self, filename):
        try:
            logging.debug("writing graph to this file: "+filename)
            self._graph.serialize(filename)
        except Exception as e:
            logging.getLogger(__name__).exception("there was a problem saving "+filename+": "+str(e))
            raise DataSourceException("there was a problem saving "+filename+": "+str(e))

    def remove(self, subj, pred, obj):  
        #logging.debug('remove(): removing (%s, %s, %s)', DataSource.pretty_print_rdf_term(subj), pred, DataSource.pretty_print_rdf_term(obj))
        try:
            logging.getLogger(__name__).debug("len graph: "+str(len(self._graph)))        
            self._graph.remove((subj, pred, obj))
            logging.getLogger(__name__).debug("after remove, len graph: "+str(len(self._graph)))
        except Exception as e:
            logging.getLogger(__name__).exception("there was a problem removing. "+str(e))
            raise DataSourceException("there was a problem removing. "+str(e))
            
    def add(self, subj, pred, obj):
        #logging.debug('add(): adding (%s, %s, %s)', DataSource.pretty_print_rdf_term(subj), pred, DataSource.pretty_print_rdf_term(obj))
        try:
            logging.getLogger(__name__).debug("len graph: "+str(len(self._graph)))
            self._graph.add((subj, pred, obj))
            logging.getLogger(__name__).debug("after add, len graph: "+str(len(self._graph)))
        except Exception as e:
            logging.getLogger(__name__).exception("there was a problem adding. "+str(e))
            raise DataSourceException("there was a problem adding. "+str(e))
        
    def removeItem(self, uri, force = False):
        # Make sure allowed ref count
        if (not force) and (self.objReferenceCount(uri) > 0):
            logging.warn("removeItem(): I cannot remove "+VivoUri.extractNfromUri(uri)+" as it's referenced as an object in some triple...")
            return

        logging.info('removeItem(): removing item ' + VivoUri.extractNfromUri(uri) + ' with obj ref count '+ str(self.objReferenceCount(uri)) + ', subj ref count '+str(self.subReferenceCount(uri))) 
        self._graph.remove((uri,None,None))
        self._graph.remove((None, None, uri))
        
        
    def subReferenceCount(self, uri):
        result = len(list(self._graph.objects(uri,None)))
        return result

    def objReferenceCount(self, uri):
        result = len(list(self._graph.subjects(None, uri)))
        return result
        
#the following few methods have a different naming convention (lower case underscore) because I'd like vivodata to follow their example.
#vivodata should work at a higher level of abstraction, that is, not have several add and remove methods for each Vivo Class URI
    def get_subgraph_by_class(self, class_uri_string):
        if class_uri_string is None:
            return self._graph
        q ="""CONSTRUCT {{
            ?s rdf:type {0} .
            ?s ?p ?o .
            ?a ?b ?s .
        }}
        WHERE {{
            ?s rdf:type {0} .
            ?s ?p ?o .
            ?a ?b ?s .
        }}
        """.format(class_uri_string)
        try:
            results = self._graph.query(q, initNs = dict(rdf = self.RDF,vivo = self.VIVO))
            print "graph has "+str(len(self._graph))+" elements"
            #print "subgraph has "+str(len(results))+" elements"
        except Exception as e:
            logging.error("there was a problem with the SPARQL query: "+str(e))
            return self._graph
        logging.debug("rsults: "+str(len(results)))
        return results.graph
    
    def get_subgraph_by_class_by_prop(self, class_uri_string, prop_uri_string, prop_val_string):
        #check whether prop_val_string converts to a URIRef or a Literal first
        #return a graph of only class instances whose property takes the particular value. e.g. bibo:pmid has value 12345
        pass
    
    #replace getLabel()
    def get_resource_label(uri_string):
        #check whether this uri_string is a URIRef?
        pass
        
    @staticmethod
    def subtract_graph(g1, g2):
        if len(g1)==0 or len(g2)==0:
            return g1
        logging.debug("original graph: "+str(len(g1)))
        for trip in g2:
            g1.remove(trip)
        logging.debug("after removes, graph: "+str(len(g1)))
        return g1
        
    def subtract(self, g):
        if len(g)==0:
            return
        logging.debug("original graph: "+str(len(self._graph)))
        for trip in g:
            self._graph.remove(trip)
        logging.debug("after removes, graph: "+str(len(self._graph)))
    
    
    def get_subgraph_by_indivs(self, dict_of_individuals, domain):
        if len(dict_of_individuals)==0:
            return self._graph
        else:
            logging.debug("trying to select statements about "+str(len(dict_of_individuals))+" individuals from graph")
        g= Graph()
        for individual in dict_of_individuals:
            q ="""CONSTRUCT {{
                <{0}> ?p ?o .
                ?a ?b <{0}> .
            }}
            WHERE {{
                <{0}> ?p ?o .
                ?a ?b <{0}> .
            }}
            """.format(VivoUri.encodeNasUri(domain, individual))        
            try:
                results = self._graph.query(q)
            except Exception as e:
                logging.error("there was a problem with the SPARQL query "+q+": "+str(e))
                return self._graph
            #learn: note use of graph union operator
            g = g + results.graph
        return g
    
    #todo:  make this work.  I.e., figure out why the sparqlqueryresult can't be iterated over / what use the describe query is
    def describe_individuals(self, dict_of_individuals, domain):
        if len(dict_of_individuals)==0:
            return self._graph
        g = Graph()
        for individual in dict_of_individuals:
            q="""DESCRIBE <{0}>""".format(VivoUri.encodeNasUri(domain, individual))
            try:
                results = self._graph.query(q)
                print "result type: "+str(type(results))
                for result in results:
                    print result
            except Exception as e:
                logging.error("there was a problem with the SPARQL query "+q+": "+str(e))
                return self._graph
        return results.graph
        
    def count_individuals(self, class_uri):
        individuals = list(self._graph.subjects(self.RDF['type'], class_uri))
        print "found "+str(len(individuals))+" individuals"
        
    def individual_is_present(self, indiv_uri_string):
        if indiv_uri_string=="":
            return False
        q ="""SELECT *
        WHERE {{
            <{0}> ?p ?o .
        }}
        """.format(indiv_uri_string)
        try:
            results = self._graph.query(q)
            #print "graph has "+str(len(self._graph))+" elements"
            #print "subgraph has "+str(len(results))+" elements"
        except Exception as e:
            logging.error("there was a problem with the SPARQL query: "+str(e))
            return False
        logging.debug("rsults: "+str(len(results)))
        return(len(results) > 0)        
        
    #assumes we are creating a resource for a Vivo instance, not just a resource for this particular DataSource, so we have to see if that individual already exists in Vivo.
    #Note that this method takes the codebase away from simply wrapping Vivo Harvester, because we can introduce entities that we didn't translate from 
    #PubMed/WOS exoort, but which came from e.g. a CSV file.
    def create_resource(self, domain, class_uri, label, indiv_uri_string=None):
        if indiv_uri_string is None:
            indiv_uri_string = VivoUri.createUri(domain)
            count=0
            while (count < 29 and (VIVOIndividualPresentQuery.isPresent(indiv_uri_string) or self.individual_is_present(indiv_uri_string))):
                indiv_uri_string = VivoUri.createUri(domain)
                count += 1
            if (VIVOIndividualPresentQuery.isPresent(indiv_uri_string) or self.individual_is_present(indiv_uri_string)):
                raise DataSourceException("couldn't assign a unique id to "+label)
        #assign a label and class URI to this resource within this DataSource, return the indiv URI...
        #todo: don't encapsulate URIRef and Literal datatypes using vivodata, in all cases just use the rdflib ones
        self._graph.add((rdflib.term.URIRef(indiv_uri_string), self.RDFS['label'], rdflib.term.Literal(label)))
        prefix = class_uri.rsplit(":",1)[0].lower()
        type = class_uri.rsplit(":",1)[1]
        #print self.nsmanager.ns[prefix]+type
        self._graph.add((rdflib.term.URIRef(indiv_uri_string), self.RDF['type'], rdflib.term.URIRef(self.nsmanager.ns[prefix]+type)))
        return rdflib.term.URIRef(indiv_uri_string)
    
    #learn: is there any point to having the domain as a param?  should the method add statements about individuals in arbitrary domains to THIS graph?
    def add_triple(self, indiv_uri_string, predicate, object):
        if indiv_uri_string is None or not VivoUri.hasHttpPrefix(indiv_uri_string):
            logging.debug("subject uri string ill formed: "+indiv_uri_string)
            return
        if VivoUri.hasHttpPrefix(object):
            predparts = predicate.rsplit(":",1)
            if len(predparts) != 2:
                logging.debug("object ok, but predicate string ill formed: "+predicate)
            else:
                self._graph.add((rdflib.term.URIRef(indiv_uri_string),rdflib.term.URIRef(self.nsmanager.ns[predparts[0].lower()]+predparts[1]), rdflib.term.URIRef(object)))
                return
        objparts = object.rsplit(":",1)
        if len(objparts)!=2:
            predparts = predicate.rsplit(":",1)
            if len(predparts) != 2:
                logging.debug("predicate string ill formed: "+predicate+" obj string ill formed: "+object)
            else:
                self._graph.add((rdflib.term.URIRef(indiv_uri_string),rdflib.term.URIRef(self.nsmanager.ns[predparts[0].lower()]+predparts[1]), rdflib.term.Literal(unicode(object).encode("utf-8"))))
        else:
            predparts = predicate.rsplit(":",1)
            if len(predparts) != 2:
                logging.debug("abbreviated object ok, but predicate string ill formed: "+predicate)
            else:
                self._graph.add((rdflib.term.URIRef(indiv_uri_string),rdflib.term.URIRef(self.nsmanager.ns[predparts[0].lower()]+predparts[1]), rdflib.term.URIRef(self.nsmanager.ns[objparts[0].lower()]+objparts[1])))            
        
    #Some remove methods for different kinds of individuals 
    #The uri argument must be a string that is converted to the correct argument type by calling DataSource.uri_literal_as_ref(stringUri)
    #Changes 12/15/2014: Remove linked info resources and author rank in publication
    def removeAuthorship(self, uri):
        
        pubUris = list(self._graph.objects(uri, self.VIVO['linkedInformationResource']))
        for pubUri in pubUris:
            self.remove(uri, self.VIVO['linkedInformationResource'], pubUri)
            self.removeItem(pubUri)
            
        rankData = list(self._graph.objects(uri, self.VIVO['authorRank']))            
        for rank in rankData:
            self.remove(uri, self.VIVO['authorRank'], rank)
    
        authorUris = list(self._graph.objects(uri,self.VIVO['linkedAuthor']))
        for authorUri in authorUris:
            self.remove(uri, self.VIVO['linkedAuthor'], authorUri)
            self.remove(authorUri, self.VIVO['authorInAuthorship'], uri)
            self.removeItem(authorUri)

        self.removeItem(uri, True)


        
    def removeCollaboration(self, uri):
        #Remove each collaborator for a collaboration uri, then the collaboration
        #Changes 12/15/2014: Remove linked info resources and collaborator rank in publication
        
        pubUris = list(self._graph.objects(uri, self.VIVO['linkedInformationResourceForCollaboration']))
        for pubUri in pubUris:
            self.remove(uri, self.VIVO['linkedInformationResourceForCollaboration'], pubUri)
            self.removeItem(pubUri)

        rankData = list(self._graph.objects(uri, self.VIVO['collaboratorRank']))            
        for rank in rankData:
            self.remove(uri, self.VIVO['collaboratorRank'], rank)

        collaboratorUris = list(self._graph.objects(uri,self.VIVO['linkedCollaborator']))
        for collaboratorUri in collaboratorUris:
            self.remove(uri, self.VIVO['linkedCollaborator'], collaboratorUri)
            self.remove(collaboratorUri, self.VIVO['collaboratorInCollaboration'], uri)
            self.removeItem(collaboratorUri)

        self.removeItem(uri, True)      
    

    def removePublication(self, pub):
    
        if (type(pub) is not rdflib.term.URIRef):
            logging.warn("warning: uri "+pub+" must be type rdflib.term.URIRef, trying to convert...")
            pub = rdflib.term.URIRef(pub)
    
        logging.debug('removing pub '+pub)
        
        
        # Retrieve Date Time & Wipe it
        URIs = list(self._graph.objects(pub,self.VIVO['dateTimeValue']))
        for uri in URIs: 
            self.remove(pub, self.VIVO['dateTimeValue'], uri) 
            self.removeItem(uri)

        #Remove publication venue. (Note that multiple venues per publication are allowed here, but I'm not sure that's a great idea.)
        #(The venue won't be removed if there are other references to it in the graph)  
        URIs = list(self._graph.objects(pub,self.VIVO['hasPublicationVenue']))
        for uri in URIs: 
            self.remove(pub, self.VIVO['hasPublicationVenue'], uri)
            self.remove(uri, self.VIVO['publicationVenueFor'], pub)
            self.removeItem(uri)
        
        # Remove resource in authorships
        URIs = list(self._graph.objects(pub,self.VIVO['informationResourceInAuthorship']))
        for uri in URIs: 
            self.remove(None, self.VIVO['informationResourceInAuthorship'], uri)
            self.removeAuthorship(uri)
        
        # Remove resource in collaborations
        URIs = list(self._graph.objects(pub,self.VIVO['informationResourceInCollaboration']))
        for uri in URIs: 
            self.remove(None, self.VIVO['informationResourceInCollaboration'], uri)
            self.removeCollaboration(uri)

        self.removeItem(pub, True)
        logging.debug('pub %s removed.  it''s subject reference count is %d', pub, self.subReferenceCount(pub))     

    def removePublications(self, pubs):
        for pub in pubs:
            self.removePublication(pub)
            
    def linkedAuthors(self):
        result = self._graph.query(
            """SELECT DISTINCT ?linkedAuthor
               WHERE {
                ?linkedAuthor vivo:authorInAuthorship ?authorship .
                           }""",    
            initNs = dict(
                rdf = self.RDF,
                vivo = self.VIVO
            )
        )
        links = []
        for row in result:
            links.append(str[row[0]])   
        return links
    
        
    def linkedCollaborators(self):
        result = self._graph.query(
            """SELECT DISTINCT ?linkedCollaborator
               WHERE {
                ?linkedCollaborator vivo:collaboratorInCollaboration ?pub .
                           }""",    
            initNs = dict(
                rdf = self.RDF,
                vivo = self.VIVO
            )
        )
        links = []
        for row in result:
            links.append(str[row[0]])   
        return links    
        
    
    def labeledItems(self):
        result = self._graph.query(
            """SELECT DISTINCT ?label
               WHERE {
                ?item rdfs:label ?label
                           }""",    
            initNs = dict(  
                rdf = self.RDF
            )
        )
        items = []
        for row in result:
            items.append(str[row[0]])   
        return items

    #This sparql works at the endpoint, but not with rdflib!
    def queryAuthorships(self, keyidentifier="bibo:pmid"):
        try:
            sparqlquery = "SELECT ?pmid ?au ?ship WHERE {?pub %s ?pmid . ?pub vivo:informationResourceInAuthorship ?ship . ?ship rdf:type vivo:Authorship . ?ship vivo:linkedAuthor ?au .}" % keyidentifier
            result = self._graph.query(
                sparqlquery,

                initNs = dict(
                    rdf = self.RDF,
                    vivo = self.VIVO
                )
            )
        except Exception as e:
            raise DataSourceException (str(e)+": I couldn't parse this SPARQL query.  You could try to get more information on the problem by querying against a live Vivo endpoint.")
        ships = []
        
        for row in result:
            cols = []
            for col in row:
                cols.append(col)
            ships.append(cols)
            
        return ships
    
    #try to return authorship URIs that relate authorURI to information resource key (a DOI or a PMID)
    def getAuthorToInformationResource(self, authorURI, key, keyidentifier="bibo:pmid"):
        try:
            sparqlquery = "SELECT ?ship WHERE {?pub %s \"%s\" . ?pub vivo:informationResourceInAuthorship ?ship . ?ship rdf:type vivo:Authorship . ?ship vivo:linkedAuthor <%s> .}" % (keyidentifier, key, authorURI)
            result = self._graph.query(
                sparqlquery,
                initNs = dict(
                    rdf = self.RDF,
                    vivo = self.VIVO,
                    bibo = self.BIBO
                )
            )
        except Exception as e:
            raise DataSourceException (e+": I couldn't parse this SPARQL query.  You could try to get more information on the problem by querying against a live Vivo endpoint.")
        ships = []

        for row in result:
            cols = []
            for col in row:
                cols.append(col)
            ships.append(cols)
            
        return ships
        
  
    def queryCollaborations(self, keyidentifier="bibo:pmid"):
        sparqlquery = "SELECT DISTINCT ?pmid ?co ?tion ?rank WHERE {  ?pub %s ?pmid .  ?pub vivo:informationResourceInCollaboration ?tion .  ?tion rdf:type vivo:Collaboration .  ?tion vivo:linkedCollaborator ?co .  ?tion vivo:collaboratorRank ?rank . OPTIONAL {?pub rdf:type bibo:AcademicArticle }  }  ORDER BY ?rank  " % keyidentifier        
        try:
            result = self._graph.query(
                sparqlquery,
                initNs = dict(
                    rdf = self.RDF,
                    bibo = self.BIBO,
                    vivo = self.VIVO,
                )
            )
        except:
            raise DataSourceException ("I couldn't parse this SPARQL query.  You could try to get more information on the problem by querying against a live Vivo endpoint.")
        
        collabs = []
        
        for row in result:
            cols = []
            for col in row:
                cols.append(col)
            collabs.append(cols)
            
        return collabs
        
    #Unfortunately RdfLib doesn't support BIND(REPLACE(STR(?authorship_label), "Authorship for ", "") AS ?author_as_listed)
    def queryAuthorsAsCited(self):
        try:
            result = self._graph.query(
            """SELECT ?author ?author_label ?authorship ?author_as_listed
                WHERE{
                    ?authorship rdf:type vivo:Authorship .
                    ?authorship vivo:linkedAuthor ?author .
                    ?authorship rdfs:label ?author_as_listed .
                    OPTIONAL { ?author rdfs:label ?author_label } 
                }
                """,
                initNs = dict(
                    rdf = self.RDF,
                    rdfs = self.RDFS,
                    vivo = self.VIVO,
                )    
    
            )
        except:
            raise DataSourceException ("I couldn't parse this SPARQL query.  You could try to get more information on the problem by querying against a live Vivo endpoint.")
            
        authors_as_listed = []
        
        for row in result:
            cols = []
            for col in row:
                cols.append(col)
            authors_as_listed.append(cols)
            
        return authors_as_listed

    #return canonical names of faculty, as found in Vivo
    #todo: rename as queryUrisOfType and parameterize on rdf:type e.g. vivo:FacultyMember, foaf:Person
    def queryFacultyNames(self):
        try:
            result = self._graph.query(
            """SELECT ?author ?author_label
                WHERE{
                    ?author rdfs:label ?author_label .
                    ?author rdf:type vivo:FacultyMember .
                }
                """,
                initNs = dict(
                    rdf = self.RDF,
                    rdfs = self.RDFS,
                    vivo = self.VIVO,
                )    
    
            )
        except:
            raise DataSourceException ("I couldn't parse this SPARQL query.  You could try to get more information on the problem by querying against a live Vivo endpoint.")
            
        faculty = []
        
        for row in result:
            cols = []
            for col in row:
                cols.append(col)
            faculty.append(cols)
            
        return faculty

    #return canonical names of any persons, as found in Vivo
    def queryPersonNames(self):
        try:
            result = self._graph.query(
            """SELECT ?author ?author_label
                WHERE{
                    ?author rdfs:label ?author_label .
                    ?author rdf:type foaf:Person .
                }
                """,
                initNs = dict(
                    rdf = self.RDF,
                    rdfs = self.RDFS,
                    foaf = self.FOAF,
                )    
    
            )
        except:
            raise DataSourceException ("I couldn't parse this SPARQL query.  You could try to get more information on the problem by querying against a live Vivo endpoint.")
            
        persons = []
        
        for row in result:
            cols = []
            for col in row:
                cols.append(col)
            persons.append(cols)
            
        return persons
        
    #Why have a set of query* functions?  Fulfill supporting roles?  does only reporter.py use them?
    #The function stores a canned query and returns a two-dimensional array (row by column) that 
    #could be rendered as a csv (by reporter.py).  The headers of the data returned are publication,issn,publication venue
    #TODO: think about whether the query* functions could be encapsulated as VivoQuery objects and the header string could then be get/set  
    def queryPublicationsForVenues(self):
                
        try:
            result = self._graph.query(
            """SELECT ?pub ?pvid ?pv
                WHERE{
                    ?pv bibo:issn ?pvid .
                    ?pv vivo:publicationVenueFor ?pub . 
                    OPTIONAL {?pub rdf:type bibo:AcademicArticle }
                }
                """,
                initNs = dict(
                    rdf = self.RDF,
                    bibo = self.BIBO,
                    vivo = self.VIVO,
                )
            )
        except:
            raise DataSourceException ("I couldn't parse this SPARQL query.  You could try to get more information on the problem by querying against a live Vivo endpoint.")
        
        pubs = []
       
        for row in result:
            cols = []
            for col in row:
                cols.append(col)
            pubs.append(cols)
            
        return pubs

    def queryPublicationsForDateTimes(self):
                
        try:
            result = self._graph.query(
            """SELECT ?pub ?pmid ?dt
                WHERE{
                    ?pub vivo:dateTimeValue ?dte .
                    ?dte vivo:dateTime ?dt . 
                    OPTIONAL { ?pub bibo:pmid ?pmid }
                    OPTIONAL {?pub rdf:type bibo:AcademicArticle }
                }
                """,
                initNs = dict(
                    rdf = self.RDF,
                    bibo = self.BIBO,
                    vivo = self.VIVO,
                )
            )
        except:
            raise DataSourceException ("I couldn't parse this SPARQL query.  You could try to get more information on the problem by querying against a live Vivo endpoint.")
        
        pubs = []
       
        for row in result:
            cols = []
            for col in row:
                cols.append(col)
            pubs.append(cols)
            
        return pubs
        
        
        
    #find publication with more than one venue per publication, and return publications.  For example, used by deduper.py.  This query only works at the fuseki endpoint, otherwise rdflib ignores the filter and the function returns the same results as queryVenues()... 
    def getPubsWithDuplicateVenues(self):
                
        try:
            result = self._graph.query(
            """SELECT DISTINCT ?pub
                WHERE{
                    ?pv bibo:issn ?pvid .
                    ?pv vivo:publicationVenueFor ?pub . 
                    OPTIONAL {?pub rdf:type bibo:AcademicArticle }
                }
                GROUP BY ?pub
                HAVING (COUNT(?pv) > 1)
                """,
                initNs = dict(
                    rdf = self.RDF,
                    bibo = self.BIBO,
                    vivo = self.VIVO,
                    foaf = self.FOAF
                )
            )
        except:
            raise DataSourceException ("I couldn't parse this SPARQL query.  You could try to get more information on the problem by querying against a live Vivo endpoint.")
        
        pubs = []
        
        for row in result:
            pubs.append(str(row[0]))
            
        return pubs   

     
        
    def getAuthorPubsWithDuplicateAuthorships(self, keyidentifier="bibo:pmid"):
        sparqlquery = "SELECT ?au ?pub  WHERE{  ?pub %s ?pmid ;  vivo:informationResourceInAuthorship ?ship .  ?ship rdf:type vivo:Authorship ;  vivo:linkedAuthor ?au .  OPTIONAL {?au rdf:type foaf:Agent} .  OPTIONAL {?pub rdf:type bibo:AcademicArticle }  }  GROUP BY ?au ?pub  HAVING (COUNT(?ship)  > 1)  " % keyidentifier        
        try:
            result = self._graph.query(
            sparqlquery,
                initNs = dict(
                    rdf = self.RDF,
                    bibo = self.BIBO,
                    vivo = self.VIVO,
                    foaf = self.FOAF
                )
            )
        except:
            raise DataSourceException ("I couldn't parse this SPARQL query.  You could try to get more information on the problem by querying against a live Vivo endpoint.")
        
        authorpubs = []
        
        for row in result:
            cols = []
            for col in row:
                cols.append(col)
            authorpubs.append(cols)
            
        return authorpubs    
        
    
        
    def getPublicationURIs(self, keyidentifier="bibo:pmid"):
        sparqlquery = "SELECT ?pub WHERE {  ?pub %s ?uid . OPTIONAL { ?pub rdf:type bibo:AcademicArticle } } ORDER BY ?uid " % keyidentifier
        result = self._graph.query(
                sparqlquery,
                initNs = dict(
                    bibo = self.BIBO,
                    rdf = self.RDF 
                )
            )
        uris = []
        for row in result:
            uris.append(str(row[0]))
        return uris
        
    #doesn't assume exactly one VIVO URI per publication UID.
    def getPublicationURI(self, key, keyidentifier="bibo:pmid"):
        sparqlquery = "SELECT ?pub WHERE {  ?pub %s \"%s\" . OPTIONAL { ?pub rdf:type bibo:AcademicArticle } } " % (keyidentifier, key)
        result = self._graph.query(
                sparqlquery,
                initNs = dict(
                    bibo = self.BIBO,
                    rdf = self.RDF 
                )
            )
        uris = []

        for row in result:
            cols = []
            for col in row:
                cols.append(col)
            uris.append(cols)
            
        return uris
       
        
    #The following change* methods make use of the all the methods declared below them...
    #they could be called instead changeAuthorInAuthorship since it is the Author Uri that
    #is changed, not the Authorship uri.
    def changeAuthorship(self, authorshipUri, newAuthorUri, authorshipLabel = rdflib.term.Literal('')):
        currentAuthorUri = self.getAuthorURIFromAuthorship(authorshipUri)
        logging.debug('current author: %s', currentAuthorUri)
        if currentAuthorUri != newAuthorUri:
            logging.debug('changing current author from %s to %s', currentAuthorUri, newAuthorUri)
            self.addLabelToAuthorship(authorshipUri, authorshipLabel)
            self.addAuthorToAuthorship(authorshipUri, newAuthorUri)
            self.addAuthorshipToAuthor(newAuthorUri, authorshipUri)            
            #self.removeLabelFromAuthorship(authorshipUri)
            self.removeAuthorFromAuthorship(authorshipUri, currentAuthorUri)
            self.removeAuthorshipFromAuthor(currentAuthorUri, authorshipUri)
            if not self.authorHasAuthorships(currentAuthorUri):
                self.removeAuthor(currentAuthorUri)

        else:
            logging.debug('no change to current author')
        
    def changeCollaboration(self, collaborationUri, newCollaboratorUri, collaborationLabel = rdflib.term.Literal('')):
        currentCollaboratorUri = self.getCollaboratorURIFromCollaboration(collaborationUri)
        logging.debug('current collaborator: %s', currentCollaboratorUri)
        if currentCollaboratorUri != newCollaboratorUri:
            logging.debug('change current collaborator from %s to %s', currentCollaboratorUri, newCollaboratorUri)
            self.addLabelToCollaboration(collaborationUri, collaborationLabel)
            self.addCollaborationToCollaborator(newCollaboratorUri, collaborationUri)
            self.addCollaboratorToCollaboration(collaborationUri, newCollaboratorUri)
            #self.removeLabelFromCollaboration(collaborationUri)
            self.removeCollaboratorFromCollaboration(collaborationUri, currentCollaboratorUri)
            self.removeCollaborationFromCollaborator(currentCollaboratorUri, collaborationUri)            
            if not self.collaboratorHasCollaborations(currentCollaboratorUri):
                self.removeCollaborator(currentCollaboratorUri)            
        else:
            logging.debug('no change to current collaborator')
    
    
    #this differs from changeCollaboration because the current uri to be changed is passed in  
    def changePublicationVenue(self, publicationUri, currentPubVenueUri, newPubVenueUri):
        logging.debug('changing venue for publication... ')
        logging.debug('current publication venue: %s', currentPubVenueUri)
        self.removePublicationFromVenue(currentPubVenueUri, publicationUri)
        self.removeVenueFromPublication(publicationUri, currentPubVenueUri)
        if not self.venueHasPublications(currentPubVenueUri):
            self.removeVenue(currentPubVenueUri)
        self.addVenueToPublication(publicationUri, newPubVenueUri)
        self.addPublicationToVenue(newPubVenueUri, publicationUri)

    

    def addAuthorToAuthorship(self, authorshipUri, authorUri):
        self.add(
            authorshipUri,
            self.VIVO['linkedAuthor'],
            authorUri
        )
        
    def addCollaboratorToCollaboration(self, collaborationUri, collaboratorUri):
        self.add(
            collaborationUri,
            self.VIVO['linkedCollaborator'],
            collaboratorUri
        ) 

    def addVenueToPublication(self, publicationUri, venueUri):
        self.add(
            publicationUri,
            self.VIVO['hasPublicationVenue'],
            venueUri
        )
        
    #Why not have one function addRelationToRole and add the arg authorInAuthorship as appropriate?
    def addAuthorshipToAuthor(self, authorUri, authorshipUri):
        self.add(
            authorUri,
            self.VIVO['authorInAuthorship'],
            authorshipUri
        )

        
    def addCollaborationToCollaborator(self, collaboratorUri, collaborationUri):
        self.add(
            collaboratorUri,
            self.VIVO['collaboratorInCollaboration'],
            collaborationUri
        )   
    
    def addPublicationToVenue(self, venueUri, publicationUri):
        self.add(
            venueUri,
            self.VIVO['publicationVenueFor'],
            publicationUri
        )   

    

    def removeLabelFromAuthorship(self, authorshipUri, authorshipLabel=None):
        self.remove(
            authorshipUri,
            self.RDFS['label'],
            authorshipLabel
        )

        
    def removeLabelFromCollaboration(self, collaborationUri):
        self.remove(
            collaborationUri,
            self.RDFS['label'],
            None
        )   
    
 
        
    def addLabelToAuthorship(self, authorshipUri, label):
        self.add(
            authorshipUri,
            self.RDFS['label'],
            label
        )
    
    
    def addLabelToCollaboration(self, collaborationUri, label):
        self.add(
            collaborationUri,
            self.RDFS['label'],
            label
        )
    
    

    def removeAuthorFromAuthorship(self, authorshipUri, authorUri):
        logging.debug('removing author ('+VivoUri.extractNfromUri(authorUri)+') from authorship('+VivoUri.extractNfromUri(authorshipUri)+')')
        self.remove(
            authorshipUri,
            self.VIVO['linkedAuthor'],
            authorUri
        )

    def removeAuthorshipFromAuthor(self, authorUri, authorshipUri):
        logging.debug('removing authorship ('+VivoUri.extractNfromUri(authorshipUri)+') from author('+VivoUri.extractNfromUri(authorUri)+')')
        self.remove(
            authorUri,
            self.VIVO['authorInAuthorship'],
            authorshipUri
        )    
        
    def removeCollaboratorFromCollaboration(self, collaborationUri, collaboratorUri):
        logging.debug('removing collaborator ('+VivoUri.extractNfromUri(collaboratorUri)+') from collaboration('+VivoUri.extractNfromUri(collaborationUri)+')')
        self.remove(
            collaborationUri,
            self.VIVO['linkedCollaborator'],
            collaboratorUri
        )
        
    def removeCollaborationFromCollaborator(self, collaboratorUri, collaborationUri):
        logging.debug('removing collaboration('+VivoUri.extractNfromUri(collaborationUri)+') from collaborator ('+VivoUri.extractNfromUri(collaboratorUri)+ ')')
        self.remove(
            collaboratorUri,
            self.VIVO['collaboratorInCollaboration'],
            collaborationUri
        )
        
    def removeVenueFromPublication(self, pubUri, venueUri):
        logging.debug('removing venue ('+VivoUri.extractNfromUri(venueUri)+') from pub ('+VivoUri.extractNfromUri(pubUri)+')')        
        self.remove(
            pubUri,
            self.VIVO['hasPublicationVenue'],
            venueUri
        )

    
    def removePublicationFromVenue(self, venueUri, pubUri):
        logging.debug('removing pub ('+VivoUri.extractNfromUri(pubUri)+') from venue ('+VivoUri.extractNfromUri(venueUri)+')') 
        self.remove(
            venueUri,
            self.VIVO['publicationVenueFor'],
            pubUri
        )   

    def removePubFromCollaboration(self, collabUri, pubUri):
        logging.debug("removing pub ("+VivoUri.extractNfromUri(pubUri)+") from collaboration ("+VivoUri.extractNfromUri(collabUri)+")") 
        self.remove(
            collabUri,
            self.VIVO['linkedInformationResourceForCollaboration'],
            pubUri
        )
        
    def removeCollaborationFromPub(self, pubUri, collabUri):
        logging.debug('removing collaboration ('+VivoUri.extractNfromUri(collabUri)+') from publication ('+VivoUri.extractNfromUri(pubUri)+')') 
        self.remove(
            pubUri,
            self.VIVO['informationResourceInCollaboration'],
            collabUri
        )                  
    
    
    
    def authorHasAuthorships(self, authorUri):
        gen = self._graph.objects(
            rdflib.term.URIRef(authorUri),
            self.VIVO['linkedAuthor']
        )
        return len(list(gen)) > 0

        
    def collaboratorHasCollaborations(self, collaboratorUri):
        gen = self._graph.objects(
            rdflib.term.URIRef(collaboratorUri),
            self.VIVO['linkedCollaborator']
        )
        return len(list(gen)) > 0       

    
    def venueHasPublications(self, venueUri):
        gen = self._graph.objects(
            rdflib.term.URIRef(venueUri),
            self.VIVO['publicationVenueFor']
        )
        return len(list(gen)) > 0
        
        
    
    def removeAuthor(self, authorUri):
        #TODO This function assumes author has no authorships, otherwise
        #     we have to remove those as well
        #     raise exception if has authorships
        logging.debug("--------> remove Author")
        if self.authorHasAuthorships(authorUri):
            raise DataSourceException('Author to delete has authorships')
        logging.debug('firing remove command')
        self.removeItem(authorUri)
        logging.debug('subject count: '+str(self.subReferenceCount(authorUri)))
        
        
    def removeCollaborator(self, collaboratorUri):
        #TODO This function assumes collaborator has no collaborations, otherwise
        #     we have to remove those as well
        #     raise exception if has collaborations
        logging.debug("--------> remove Collaborator")
        if self.collaboratorHasCollaborations(collaboratorUri):
            raise DataSourceException ('Collaborator to delete has collaborations')
        logging.debug('firing remove command')
        self.removeItem(collaboratorUri)
        logging.debug('subject count: '+str(self.subReferenceCount(collaboratorUri)))
        
        
    def removeVenue(self, venueUri):
        #TODO This function assumes venue has no publications, otherwise
        #     we have to remove those as well
        #     raise exception if has publications
        logging.debug("--------> remove Venue")
        #TODO: venueHasPublications() was already called, should we be this defensive??
        if self.venueHasPublications(venueUri):
            raise DataSourceException ('venue to delete has publications')
        logging.debug('firing remove command')
        self.removeItem(venueUri)
        logging.debug('subject count:' + str(self.subReferenceCount(venueUri)))
    
    def getLabel(self, uri):
        gen = self._graph.objects(
            rdflib.term.URIRef(uri),
            self.RDFS['label']
        )
        objs = list(gen)
        if len(objs) == 0:
            return ''
        return (objs[0])        
    
                        
    def getAuthorURIFromAuthorship(self, authorshipUri):
        gen = self._graph.objects(
            rdflib.term.URIRef(authorshipUri),
            self.VIVO['linkedAuthor']
        )
        objs = list(gen)
        if len(objs) == 0:
            return ''
        return (objs[0])

    #This ok, except it is only returning the first collaborator uri... 
    def getCollaboratorURIFromCollaboration(self, collaborationUri):
        gen = self._graph.objects(
            rdflib.term.URIRef(collaborationUri),
            self.VIVO['linkedCollaborator']
        )
        objs = list(gen)
        if len(objs) == 0:
            return ''
        return (objs[0])

    def getAllAuthorURIFromAuthorship(self, authorshipUri):
        gen = self._graph.objects(
            rdflib.term.URIRef(authorshipUri),
            self.VIVO['linkedAuthor']
        )
        objs = list(gen)
        if len(objs) == 0:
            return ''
        return (objs)        

    def getAllCollaboratorURIFromCollaboration(self, collaborationUri):
        gen = self._graph.objects(
            rdflib.term.URIRef(collaborationUri),
            self.VIVO['linkedCollaborator']
        )
        objs = list(gen)
        if len(objs) == 0:
            return ''
        return (objs)
        
    
    def getRank(self, uriString, field='collaboratorRank'):
        gen = self._graph.objects(
            rdflib.term.URIRef(uriString),
            self.VIVO[field]
        )   
        #print "getRank "+str(uriString)
        objs = list(gen)
        if len(objs) == 0:
            return ''
        #print " has coll rank "+str(objs[0])  
        return (objs[0])
        
        
    def getPublicationPMID(self, uri):
        gen = self._graph.objects(
            rdflib.term.URIRef(uri),
            self.BIBO['pmid']
        )
        objs = list(gen)
        if len(objs) == 0:
            return ''
        return str(objs[0])

    def getPublicationDOI(self, uri):
        gen = self._graph.objects(
            rdflib.term.URIRef(uri),
            self.BIBO['doi']
        )
        objs = list(gen)
        if len(objs) == 0:
            return ''
        return str(objs[0])
    
        
    def getPublicationTitle(self, uri):
        gen = self._graph.objects(
            rdflib.term.URIRef(uri),
            self.VIVO['Title']
        )
        
        objs = list(gen)
        if len(objs) == 0:
            return ''
        return str(objs[0]) 

    def getAllPublicationVenueURIs(self):
    
        queryText = "SELECT ?pv WHERE{?pv vivo:publicationVenueFor ?ir .}"
        
        result = self._graph.query(
                queryText,
                initNs = dict(
                    rdf = self.RDF,
                    vivo = self.VIVO
                )
            )   
        venues = []
        for row in result:
            venues.append(str(row[0]))
        return venues


    
    #can't this be done like getPublicationPMID (e.g. using self._graph), instead of appending strings?
    def getPublicationVenueURIs(self, uri):
    
        queryText = "SELECT DISTINCT ?pv WHERE{?pv bibo:issn ?pvid . ?pv vivo:publicationVenueFor <%s> .}"
        
        result = self._graph.query(
                queryText % (uri),
                initNs = dict(
                    bibo = self.BIBO,
                    rdf = self.RDF,
                    vivo = self.VIVO
                )
            )   
        venues = []
        for row in result:
            venues.append(str(row[0]))
        return venues



        
        
        
    def getPublicationVenueISSN(self, uri):

        gen = self._graph.objects(
            rdflib.term.URIRef(uri),
            self.BIBO['issn']
        )
        objs = list(gen)
        if len(objs) == 0:
            return ''
        return str(objs[0])
  

    
    def getPublicationAuthorURIs(self, uri):
        queryText = """SELECT DISTINCT ?author
                   WHERE {
                    <%s> vivo:informationResourceInAuthorship ?authorship .
                    ?authorship vivo:linkedAuthor ?author .
                   }"""
        result = self._graph.query(
                queryText % (uri),
                initNs = dict(
                    bibo = self.BIBO,
                    vivo = self.VIVO
                )
            )
        authors = []
        for row in result:
            authors.append(str(row[0]))
        return authors
        
        
        
        
        
    def getPublicationCollaboratorURIs(self, uri):
        queryText = """SELECT DISTINCT ?collaborator
                   WHERE {
                    <%s> vivo:informationResourceInCollaboration ?collaboration .
                    ?collaboration vivo:linkedCollaborator ?collaborator .
                   }"""
        result = self._graph.query(
                queryText % (uri),
                initNs = dict(
                    bibo = self.BIBO,
                    vivo = self.VIVO
                )
            )
        authors = []
        for row in result:
            authors.append(str(row[0]))
        return authors
    
    def getPublicationAuthorshipURIs(self, uri):
        queryText = """SELECT DISTINCT ?authorship
                   WHERE {
                    <%s> vivo:informationResourceInAuthorship ?authorship .
                   }"""
        result = self._graph.query(
                queryText % (uri),
                initNs = dict(
                    vivo = self.VIVO
                )
            )
        authorships = []
        for row in result:
            authorships.append(str(row[0]))
        return authorships
        
    def getPublicationCollaborationURIs(self, uri):
        queryText = """SELECT DISTINCT ?collaboration
                   WHERE {
                    <%s> vivo:informationResourceInCollaboration ?collaboration .
                   }"""
        result = self._graph.query(
                queryText % (uri),
                initNs = dict(
                    vivo = self.VIVO
                )
            )
        collaborations = []
        for row in result:
            collaborations.append(str(row[0]))
        return collaborations

    #get all authorship nodes in the graph.
    #In Python, we can't call this getAuthorshipURIs and let the args it takes distinguish it from the other getAuthorshipURIs 
    def getAllAuthorshipURIs(self):
    
        queryText = "SELECT DISTINCT ?authorship WHERE {?authorship rdf:type vivo:Authorship .}"
        #print queryText % (authorUri)       
        result = self._graph.query(
            queryText,
            initNs = dict(
                vivo = self.VIVO
            )
        )
        
        authorships = []
        for row in result:
        #    print "result row:"+row
            authorships.append(str(row[0]))
        #print "I found "+str(len(authorships))+" authorships"   
        return authorships      
        
    #get authorship nodes for an author (perhaps for a publication)
    def getAuthorshipURIs(self, authorUri, pubUri=None):
    
        if pubUri is not None:
            queryText = "SELECT DISTINCT ?authorship WHERE {?authorship rdf:type vivo:Authorship . ?authorship vivo:linkedInformationResource <%s> . ?authorship vivo:linkedAuthor <%s> }"
            # queryText = """SELECT DISTINCT ?authorship
                       # WHERE {
                    # ?authorship rdf:type vivo:Authorship .
                    # ?authorship vivo:linkedInformationResource <%s> .
                    # ?authorship vivo:linkedAuthor <%s> 
                   # }"""
            #print queryText % (pubUri, authorUri)       
            result = self._graph.query(
                queryText % (authorUri, pubUri),
                initNs = dict(
                    vivo = self.VIVO
                    )
                )
        else:
            queryText = "SELECT DISTINCT ?authorship WHERE {?authorship rdf:type vivo:Authorship . ?authorship vivo:linkedInformationResource ?pub . ?authorship vivo:linkedAuthor <%s> }"
            #print queryText % (authorUri)       
            result = self._graph.query(
                queryText % (authorUri),
                initNs = dict(
                    vivo = self.VIVO
                )
            )
        
        authorships = []
        for row in result:
        #    print "result row:"+row
            authorships.append(str(row[0]))
        #print "I found "+str(len(authorships))+" authorships"   
        return authorships      

    def getAllCollaborationURIs(self):
    
        queryText = "SELECT DISTINCT ?collaboration WHERE {?collaboration rdf:type vivo:Collaboration .}"
        result = self._graph.query(
            queryText,
            initNs = dict(
                vivo = self.VIVO
            )
        )
        
        collaborations = []
        for row in result:
            collaborations.append(str(row[0]))
        return collaborations

    def getCollaborationURIs(self, collabUri, pubUri=None):
    
        if pubUri is not None:
            queryText = "SELECT DISTINCT ?collaboration WHERE {?collaboration rdf:type vivo:Collaboration . ?collaboration vivo:linkedInformationResourceForCollaboration <%s> . ?collaboration vivo:linkedCollaborator <%s> }"
            result = self._graph.query(
                queryText % (pubUri, collabUri),
                initNs = dict(
                    vivo = self.VIVO
                    )
                )
        else:
            queryText = "SELECT DISTINCT ?collaboration WHERE {?collaboration rdf:type vivo:Collaboration . ?collaboration vivo:linkedInformationResourceForCollaboration ?pub . ?collaboration vivo:linkedCollaborator <%s> }"
            result = self._graph.query(
                queryText % (collabUri),
                initNs = dict(
                    vivo = self.VIVO
                )
            )
        
        collaborations = []
        for row in result:
            collaborations.append(str(row[0]))
        return collaborations

    #TODO: currently generates an object that is actually given a name in vivoquery.py.  Better way?
    #Returns an RDFLib Term/Dict.  To access Person name parts more easily, use getLastName() et al.
    def getAuthorName(self, uri):
        
        gen = self._graph.objects(
            rdflib.term.URIRef(uri),
            self.FOAF['firstName']
        )
        objs = list(gen)
        if len(objs) == 0:
            return uri
        firstName = objs[0]
        
        gen = self._graph.objects(
            rdflib.term.URIRef(uri),
            self.VIVO['middleName']
        )   
        objs = list(gen)
        if len(objs) == 0:
            middleName=''
        else:   
            middleName = objs[0]
        
        
        gen = self._graph.objects(
            rdflib.term.URIRef(uri),
            self.FOAF['lastName']
        )
        objs = list(gen)
        if len(objs) == 0:
            return uri
        lastName = objs[0]
        return {'fname' : firstName, 'mname': middleName, 'lname' : lastName}        
#        return {'fname' : unicode(firstName).encode("utf-8"), 'mname': unicode(middleName).encode("utf-8"), 'lname' : unicode(lastName).encode("utf-8")}
    
    
    def getFirstName(self, personUri):
        gen = self._graph.objects(
            rdflib.term.URIRef(personUri),
            self.FOAF['firstName']
        )
        objs = list(gen)
        if len(objs) == 0:
            return ""
        firstName = objs[0]
        return unicode(firstName).encode("utf-8")
        
    def getMiddleName(self, personUri):
        gen = self._graph.objects(
            rdflib.term.URIRef(personUri),
            self.VIVO['middleName']
        )
        objs = list(gen)
        if len(objs) == 0:
            return ""
        middleName = objs[0]
        return unicode(middleName).encode("utf-8")
        
    def getLastName(self, personUri):
        gen = self._graph.objects(
            rdflib.term.URIRef(personUri),
            self.FOAF['lastName']
        )
        objs = list(gen)
        if len(objs) == 0:
            return ""
        lastName = objs[0]
        return unicode(lastName).encode("utf-8")        
    
    #TODO: why is this defined if it's not needed for persistence?    
    def commit(self):
        self._graph.commit()  
   
    #TODO: why is this defined if it's not needed for persistence?  
    def close(self):
        #close and commitPendingTransactions=True
        self._graph.close(True)
        
        
if __name__ == '__main__':

    print "usage: except for testing, don't call vivodata.py as a script.\n"
    logging.basicConfig(filename='vivodata.log', filemode='w', level=logging.DEBUG)
    logging.debug("usage: except for testing, don't call vivodata.py as a script.\n")
    
    #ds=DataSource('../../rsc/rdf/unm/vivo-additions.rdf.xml')
        
    #ds.changeAuthorship(
    #   rdflib.term.URIRef('http://vivo.health.unm.edu/individual/n1984839530'),
    #   rdflib.term.URIRef('http://vivo.health.unm.edu/individual/n4013')
    #)
    #ds.removePublication(rdflib.term.URIRef('http://vivo.health.unm.edu/individual/n406701577'))
    #ds.serialize('pd-vivo-additions.rdf.xml')

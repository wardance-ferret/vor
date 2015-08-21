#! /usr/bin/python
# -*- coding: utf-8 -*-
import csv
import re
import getopt
import logging
import strings
import sys
from vivodata import DataSource
from vivouri import VivoUri
from vivoquery import VIVOAuthorName, VIVOAuthorNameQuery, VIVOIndividualPresentQuery


logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', filename='../../logs/refsplitter.log', filemode='w', level=logging.INFO)
logger = logging.getLogger(__name__)

class RefSplitterException(Exception):
    def __init__(self, message):
        logger.error(message)
        
#A class for splitting co-references for probable distinct individuals, for review e.g. in a gui tool.
#refsplitter.py splits references to individuals (Faculty, John or Faculty, Jane) by comparing the rdfs label for the person (either in the input model or in the vivo model) against the rdfs label for the authorship.
#For example, an authorship "Authorship for Faculty, Jane" may be lumped with faculty "Faculty, John."
#The class will check [ describe here how it checks for bad lumps and de-lumps them ]
#The program will not break on empty rdfs labels, but will be constrained by them.
#RefSplitter balances Harvester's liberal tendency on certain names, particularly short surnames like Lee or Li, to lump authorships with the wrong individual.
#However, because Harvester's algorithm can be tuned with parameters, and this one can't, it'd be better to use this class carefully.  Try running it after Harvester has already done name matching, and after you've run coreffer.py to correct possible splitting errors.
#
class RefSplitter:

    def __init__(self, domain, filename, keyidentifier, workflowcode):
        self._domain = domain
        try:
            self._datasource = DataSource(filename)
        except:
            raise RefSplitterException("error: there was a problem opening "+filename+" as a data source")
        self._inputfilename = filename
        #a file of name variations that are considered aliases although one is not a prefix of the other e.g. Jenny/Jennifer
        self._blackfilename = "./BLACKLIST-refsplitter.txt"
        self._outputfilename = VivoUri.createOutputFileName(filename, workflowcode)
        print "output will be written to "+self._outputfilename+"\n"
        self._keyidentifier=keyidentifier
        
        #THE CACHES
        #cache each (person) author URI for which a name template is already made. 
        self._cachedPersonURIs={}
        #cache each name template for which a (person) author URI is already assigned.
        self._cachedNameTemplates={}
        #cache URIs to mentions which are blacklisted
        self._blacklist={}
        
        #read from csv file into blacklist (too bad blacklist cannot be an RDF graph that makes anti-statements, it would dovetail nicely with our DataSource model)
        with open(self._blackfilename, "rb") as csvfile:
            csvReader = csv.reader(csvfile, delimiter="\t")
            rows=list(csvReader)
            if (len(rows)<1):
                logging.error("error: there was a problem opening "+self._blackfilename+" as a blacklist")
                raise RefSplitterException("error: there was a problem opening "+self._blackfilename+" as a blacklist")
            logging.info("rows in blacklist, including header: "+str(len(rows)))
            csvHeader = rows.pop(0)
            #validate the header
            if ((csvHeader[0] != "VivoURI" ) or (csvHeader[1] != "LastName") or (csvHeader[2] != "FirstName") or (csvHeader[3] != "MiddleName")):
                logging.error("error: invalid header in "+self._blackfilename);
                raise RefSplitterException("error: invalid header in "+self._blackfilename)
            
            for row in rows:
                if len(row) < 4:
                    continue
                nameString = RefSplitter.getNameTemplateAsString(RefSplitter.makeNameTemplate(row[1], row[2], row[3]))
                authorUri = DataSource.uri_literal_as_ref(row[0])
                if authorUri in self._blacklist:
                    if nameString in self._blacklist[authorUri]:
                        continue;
                    else:
                        self._blacklist[authorUri][nameString]=1
                else:
                    self._blacklist[authorUri]={}
                    self._blacklist[authorUri][nameString]=1

    @staticmethod
    def getNameTemplateAsString(nameTemplate):
        if (nameTemplate is None) or (len(nameTemplate)!=3) :
            logging.debug("name template is not initialized, returning empty string")
            return ""
        nameString=""
        nameString += nameTemplate['lname']
        nameString+="_"
        nameString += nameTemplate['fname']
        if (nameTemplate['mname'] != ""):
            nameString+="_"
            nameString += nameTemplate['mname']
        return nameString
    
    @staticmethod
    def makeNameTemplate(lastName, firstName, middleName):
        nameTemplate={}
        nameTemplate['lname'] = lastName
        nameTemplate['fname'] = firstName
        nameTemplate['mname'] = middleName
        return nameTemplate
    
    #This method translates the object returned by getAuthorName() from a DataSource(defined in vivodata.py) into the required nameTemplate dict for Coreffer.
    #TODO: I'll need to rework vivodata.py next time so that this object has one and only one type (a dict, never an RDFLib URI Ref or a string)
    @staticmethod
    def makeNameTemplateFromDataSource(vivodata_author_name):
        nameTemplate={}
        if not isinstance(vivodata_author_name, dict):
            #we don't know if vivodata_author_name is a string, but if looks like an empty string, then stop
            if (strings.remove_whitespace(str(vivodata_author_name))==""):
                return None

            logging.debug("For author ["+str(vivodata_author_name)+"] I got an object of type "+str(type(vivodata_author_name))+", not a dict.")
            logging.debug("Harvester didn't provide the first and last name for person "+str(vivodata_author_name)+ " in the input graph.  I'll therefore try to query Vivo to recover first and last name")
            #TODO: decide if the next line is really necessary (should be uncommented)
            #authorName = VIVOAuthorName("","")
            authorName = VIVOAuthorNameQuery.getName(vivodata_author_name)
            logging.debug("authorName returned by VIVOAuthorNameQuery.getName(vivodata_author_name) is type: "+str(type(vivodata_author_name))) 
            if authorName is None and VIVOIndividualPresentQuery.isPresent(vivodata_author_name):
                logging.debug("Vivo knows author "+str(vivodata_author_name)+" but cannot get the author's name. Either there is no first or last name, or the indiv is an Org")
                return None
            elif authorName is None:
                logging.debug("Vivo doesn't know author "+str(vivodata_author_name))
                return None
            else:
                nameTemplate['fname'] = authorName.getFirstName()
                nameTemplate['lname'] = authorName.getLastName()
                nameTemplate['mname'] = authorName.getMiddleName()
        else:
            nameTemplate['fname'] = vivodata_author_name['fname']
            nameTemplate['lname'] = vivodata_author_name['lname']
            nameTemplate['mname'] = vivodata_author_name['mname']
        return nameTemplate
        
    @staticmethod
    def ruleNameNotInPrefixChain(authorUri, inVivoName, asListedName):
        #either return a key value which is identical to authorUri, or the empty string, in which case we create a new distinct authorUri for the author as listed
        #
        logging.debug("in vivo: " + inVivoName['lname'])
        logging.debug("as cited: "+ asListedName['lname'])
        
        #Vivo Name, lowercased
        lnv=inVivoName['lname'].lower()
        fnv=inVivoName['fname'].lower()
        mnv=inVivoName['mname'].lower()
        #As Listed Name, lowercased
        lnl=asListedName['lname'].lower()
        fnl=asListedName['fname'].lower()
        mnl=asListedName['mname'].lower()
        
        someOtherUri=""
        if (lnv != lnl):
            logging.debug("lastnames didn't match!")
            return someOtherUri
        #William Kelly and H William Kelly should not be de-lumped, although they are not in the same prefix chain
        if ((len(fnl)==1 and len(mnl)>1 and mnl==fnv) or (len(fnv)==1 and len(mnv)>1 and mnv==fnl)):
            logging.debug("author doesn't appear to go by first name, handling that as optional!")
            return authorUri
        if (mnv !="" and mnl != "" and not mnv.startswith(mnl) and not mnl.startswith(mnv)):
            logging.debug("middle inits couldn't be reconciled!")
            return someOtherUri
        if (not fnv.startswith(fnl) and not fnl.startswith(fnv)):
            logging.debug("first names couldn't be reconciled!")
            return someOtherUri
        return authorUri
        
    #this function should be made generic, so either coreffer or refsplitter could use it
    def applyRule(self, uris, ruleName="NameNotInPrefixChain"):
            for uri in uris:
                logging.debug("applying rule "+ruleName+" to URI "+uri)
                
                authUri=self._datasource.getAuthorURIFromAuthorship(uri)
                if authUri is None:
                    authUri=self._datasource.getCollaboratorURIFromCollaboration(uri)
                if authUri is None:
                    continue
                    
                parts = self._datasource.getAuthorName(authUri)                
                
                authorAsListed=re.sub(u'^Authorship\s+for\s+(.+)$',"\\1",self._datasource.getLabel(uri))
                authorAsListed=authorAsListed.strip() 
                if (len(authorAsListed.rsplit(",",1))!=2):
                    continue
                lastName = authorAsListed.rsplit(",",1)[0].strip()
                foreName = authorAsListed.rsplit(",",1)[1].strip()
                
                if (len(foreName.split(" ",1))==2):
                    firstName = strings.trim(foreName.split(" ",1)[0])
                    middleName = foreName.split(" ",1)[1]
                    logging.debug("foreName: "+foreName)
                    logging.debug("middleName: "+middleName)
                else:
                    firstName = foreName
                    middleName = ""
                asListed = RefSplitter.makeNameTemplate(lastName, firstName, middleName)
                if (asListed is None) or (len(asListed)!=3):
                    logging.debug("couldn't include author as listed for author: "+authUri)
                    logging.debug("an associative array of three name parts must be stored in asListed nameTemplate")
                    continue
                
                if authUri not in self._cachedPersonURIs:
                    nameTemplate = RefSplitter.makeNameTemplateFromDataSource(parts)
                    self._cachedPersonURIs[authUri]=nameTemplate
                else:
                    logging.debug("retrieving cached name for author "+authUri)
                    #print "retrieving cached name for author "+authUri
                    nameTemplate = self._cachedPersonURIs[authUri]
                
                nameString=RefSplitter.getNameTemplateAsString(nameTemplate)
                
                if (nameTemplate is None) or (len(nameTemplate)!=3) or (nameString==""):
                    logging.debug("couldn't include name for author: "+authUri)
                    logging.debug("an associative array of three name parts must be stored in inVivo nameTemplate")
                    continue
                 
                if (ruleName=="NameNotInPrefixChain"):
                    keyvalue=RefSplitter.ruleNameNotInPrefixChain(authUri, nameTemplate, asListed)
                    if keyvalue=="":
                        logging.info("author name proposed by Vivo Harvester or found in Vivo itself: "+nameString)
                        logging.info("author name as listed in the original citation: "+RefSplitter.getNameTemplateAsString(asListed))
                        logging.debug("rule returned uri <"+keyvalue+">")
                    else:
                        logging.debug("author name proposed by Vivo Harvester or found in Vivo itself: "+nameString)
                        logging.debug("author name as listed in the original citation: "+RefSplitter.getNameTemplateAsString(asListed))                
                        logging.debug("rule returned uri <"+keyvalue+">")
                else:
                    continue
                new_uri = None    
                if keyvalue=="":
                    if RefSplitter.getNameTemplateAsString(asListed) not in self._cachedNameTemplates:
                        new_uri=self._datasource.create_resource(self._domain, "foaf:Person", authorAsListed)
                        logging.info("delumping "+RefSplitter.getNameTemplateAsString(asListed)+" from "+authUri+", new uri: "+new_uri)
                        self._cachedNameTemplates[RefSplitter.getNameTemplateAsString(asListed)] = new_uri
                        logging.debug("cacheNameTemplates:"+str(len(self._cachedNameTemplates))+" members")
                        self._datasource.add_triple(new_uri, "foaf:firstName", firstName)
                        if middleName != "":
                            self._datasource.add_triple(new_uri, "vivo:middleName", middleName)
                        self._datasource.add_triple(new_uri, "foaf:lastName", lastName)
                        self._datasource.changeAuthorship(DataSource.uri_literal_as_ref(uri), new_uri, self._datasource.getLabel(uri))
                    else:
                        new_uri=self._cachedNameTemplates[RefSplitter.getNameTemplateAsString(asListed)]
                        logging.info("delumping "+RefSplitter.getNameTemplateAsString(asListed)+" from "+authUri+", new uri: "+new_uri)
                        self._datasource.changeAuthorship(DataSource.uri_literal_as_ref(uri), new_uri, self._datasource.getLabel(uri))
                    logging.info("-"*65)
                #since we are not really doing collisions, this is redundant
                #if keyvalue not in self._theData:
                #    self._theData[keyvalue]={}
                #if authUri not in self._theData[keyvalue]:
                #    self._theData[keyvalue][authUri]={}
                #if nameString not in self._theData[keyvalue][authUri]:
                #    self._theData[keyvalue][authUri][nameString] = {}
                #    self._theData[keyvalue][authUri][nameString]=0
                #self._theData[keyvalue][authUri][nameString] += 1

                
    """For the author URI assigned by Vivo Harvester, the PubMed authorship may list the author's name in a suspiciously different way from the name associated with that URI.  "Suspiciously different" will be defined by rule initially, and judged by thresholded edit distance metrics in future.  Create a dictionary of the author names, where the two different names are looked up by author uri.  For each distinct author name, record 0 if the author name was recovered from the authorship label and 1 otherwise.  0 means the form of the name is not canonical, if you like."""
    def collidePersons(self, ruleName="NameNotInPrefixChain"):
    
        pubUris = self._datasource.getPublicationURIs(self._keyidentifier)
        
        self._theData={}
        
        for pubUri in pubUris:
            #Pull all authorship/coll uris as links to person uris
            shipUris = self._datasource.getPublicationAuthorshipURIs(pubUri)
            self.applyRule(shipUris, ruleName)
               
        theReport={}                    
        return theReport            
                    
def main():
    domain=None
    keyidentifier="bibo:pmid"
    try:
        (options, arguments) = getopt.getopt(sys.argv[1:],'i:d:k')
    except getopt.GetoptError:
        print "\n\nThere was an error in your options.\n\nusage: refsplitter.py -i <inputfile> -d <vivo domain URI> -k {\"pmid\"|\"doi\"}\n\t-> <inputfile> should be an absolute or relative path with the / separator, either on Windows or Unix.\n\n"
        sys.exit(2)
    for opt, arg in options:
        if opt in ("-i"):
            inputfile=arg
        elif opt in ("-d"):
            domain=arg
        elif opt in ("-k"):
            if arg in ("pmid", "doi"):
                keyidentifier="bibo:"+arg
            else:
                print "\n\nyou must specify pmid (PubMed Identifer) or doi (Digital Object Identifier) as the unique identifier for publications, using the -k option.\nIf you omit the -k option, pmid is the default.\n\n"
                sys.exit(2)
        
            
    n = RefSplitter(domain, inputfile, keyidentifier, 'pn1')
    outfile = n._outputfilename
    
    collisions=n.collidePersons()
    #for uri in collisions:
    #    logging.info("uri: "+str(uri))
    #    for item in collisions[uri]:
    #        logging.info("item: "),
    #        logging.info(item)
    #        logging.info(str(collisions[uri][item]))
            
    n._datasource.serialize(outfile)    

if __name__=='__main__':
    main()

#Questions
#I added a black list to protect coreffer.py (and Vivo Harvester) mention classes from delumping.  Should I at least have coreffer.py tell this program what its results were?  It seems like both coreffer and refsplitter deal with Vivo Harvester problems, and they should relate as peers, yet refsplitter can undo what coreffer does.
#I minted new Vivo URIs, new to both Vivo and the input model.  Is 

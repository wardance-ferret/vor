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

class CorefferException(Exception):
    def __init__(self, message):
        logging.error(message)

#A class for generating person name co-reference classes for review e.g. in a gui tool.
#Coreffer.py co-references different name mentions (John Public, John Q Public, J Q Public) to a unique URI.
#Coreffer balances Harvester's conservative tendency, which is to treat name mention differences as distinct individuals.
#However, because Harvester's algorithm can be tuned with parameters, and this one can't, it'd be better to use this class carefully.  Try running it after Harvester has already done name matching.
#


class Coreffer:

    def __init__(self, filename, keyidentifier, workflowcode='pn0'):
        try:
            self._datasource = DataSource(filename)
        except:
            raise CorefferException("error: there was a problem opening "+filename+" as a data source")
        self._inputfilename = filename
        self._blackfilename = "./BLACKLIST-coreffer.txt"
        self._outputfilename = VivoUri.createOutputFileName(filename, workflowcode)
        print "output will be written to "+self._outputfilename+"\n"
        self._keyidentifier=keyidentifier
        #cache each (person) author URI for which a name template is already made. 
        self._cachedPersonURIs={}
        #cache URIs to mentions which are blacklisted
        self._blacklist={}
        #read from csv file into blacklist (too bad blacklist cannot be an RDF graph that makes anti-statements, it would dovetail nicely with our DataSource model)
        with open(self._blackfilename, "rb") as csvfile:
            csvReader = csv.reader(csvfile, delimiter="\t")
            rows=list(csvReader)
            if (len(rows)<2):
                logging.error("error: there was a problem opening "+self._blackfilename+" as a blacklist")
                raise CorefferException("error: there was a problem opening "+self._blackfilename+" as a blacklist")
            logging.info("rows in blacklist, including header: "+str(len(rows)))
            csvHeader = rows.pop(0)
            #validate the header
            if ((csvHeader[0] != "VivoURI" ) or (csvHeader[1] != "LastName") or (csvHeader[2] != "FirstName") or (csvHeader[3] != "MiddleName")):
                logging.error("error: invalid header in "+self._blackfilename);
                raise CorefferException("error: invalid header in "+self._blackfilename)
            
            for row in rows:
                if len(row) < 4:
                    continue
                nameString = Coreffer.getNameTemplateAsString(Coreffer.makeNameTemplate(row[1], row[2], row[3]))
                authorUri = DataSource.uri_literal_as_ref(row[0])
                if authorUri in self._blacklist:
                    if nameString in self._blacklist[authorUri]:
                        continue;
                    else:
                        self._blacklist[authorUri][nameString]=1
                else:
                    self._blacklist[authorUri]={}
                    self._blacklist[authorUri][nameString]=1
                
        
    def _isBlacklisted(self, authorUri, nameString):
        logging.debug("nameString: "+strings.to_lower(nameString)+" authorUri: "+DataSource.uri_literal_as_ref(authorUri))
        if DataSource.uri_literal_as_ref(authorUri) in self._blacklist:
            if strings.to_lower(nameString) in self._blacklist[DataSource.uri_literal_as_ref(authorUri)]:
                return True
        return False
    
    #rewrite rules 
    @staticmethod
    def normalize(s):
        normalized = re.sub(u'^[Dd]([ie])\s+(.+$)', "d\\1\\2", s)        
        normalized = strings.to_lower(normalized)
        normalized = re.sub(u'í',"i",normalized)
        normalized = re.sub(u'ć',"c",normalized)
        normalized = re.sub(r"[`']","'",normalized)
        normalized = re.sub(r'\\.\b',"", normalized)
        #logging.debug("normalize(): "+s.encode('utf-8') + " --> " + normalized.encode('utf-8'))
        return normalized
        
    #it'd be nicer if we could abstract away from these cases, and separate phonetic variation from things like official name change.
    @staticmethod
    def normalizeForNameChange(lastName, firstName, middleName):
        parts = [lastName, firstName, middleName]
        s = " ".join(parts)
        normalized = strings.to_lower(s)
        normalized = Coreffer.normalize(normalized)
        normalized = re.sub(u'^agsalda(\s+m.+$)', "agsalda-garcia\\1", normalized)
        normalized = re.sub(u'^ananworonich(\s+j.+$)', "ananworanich\\1", normalized)
        normalized = re.sub(u'^boonchokchai(\s+.+$)', "boonchokechai\\1", normalized)
        #TODO:shouldn't these rules use the primary author's URI to disambiguate, rather than always applying?
        #e.g. Garcia who co-authored with URI XXX is not the one who married and changed names to Klein.
        normalized = re.sub(u'^wishcamper(\s+c\S*\s+a?\S*$)',"beamer\\1",normalized)
        #logging.info("normalizeForNameChange(): "+s.encode('utf-8') + " --> " + normalized.encode('utf-8'))
        return normalized
        
    #rule returns a keyval to collide Persons on
    @staticmethod
    def ruleSameLastSameFirstInit(lastName, firstName, middleName):
        if len(firstName):
            keyvalue = Coreffer.normalize(firstName[0])+"_"+Coreffer.normalize(lastName)
        else:
            keyvalue = Coreffer.normalize(lastName)
        return keyvalue
        
    @staticmethod    
    def ruleForLastNameChange(lastName, firstName, middleName):
        if len(firstName):
            keyvalue = Coreffer.normalizeForNameChange(lastName, firstName, middleName)
        else:
            keyvalue = Coreffer.normalizeForNameChange(lastName)
        return keyvalue
    
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
            logging.debug("-"*30)
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

                    
    def applyRule(self, uris, ruleName="SameLastSameFirstInit"):
            
            for uri in uris:
                authorName=None
                #get a person URI, whether it's an author or collaborator
                authUri=self._datasource.getAuthorURIFromAuthorship(uri)
                if authUri is None:
                    authUri=self._datasource.getCollaboratorURIFromCollaboration(uri)
                if authUri is None:
                    continue
                    
                parts = self._datasource.getAuthorName(authUri)
                
                
                if authUri not in self._cachedPersonURIs:
                    nameTemplate = Coreffer.makeNameTemplateFromDataSource(parts)
                    self._cachedPersonURIs[authUri]=nameTemplate
                else:
                    logging.debug("retrieving cached name for author "+authUri)
                    #print "retrieving cached name for author "+authUri
                    nameTemplate = self._cachedPersonURIs[authUri]
                
                nameString=Coreffer.getNameTemplateAsString(nameTemplate)
                
                if (nameTemplate is None) or (len(nameTemplate)!=3) or (nameString==""):
                    logging.debug("couldn't include name for author: "+authUri)
                    logging.debug("an associative array of three name parts must be stored in nameTemplate")
                    continue
                
                logging.debug("found authorship name mention: "+nameString)                
                 
                if (ruleName=="SameLastSameFirstInit"):
                    keyvalue=Coreffer.ruleSameLastSameFirstInit(nameTemplate['lname'],nameTemplate['fname'],nameTemplate['mname'])
                    #if black listed for the authUri, don't collide nameString under keyvalue in _theData
                elif ruleName=="ForLastNameChange":
                    keyvalue=Coreffer.ruleForLastNameChange(nameTemplate['lname'], nameTemplate['fname'], nameTemplate['mname'])
                else:
                    continue
                
                if keyvalue not in self._theData:
                    self._theData[keyvalue]={}
                if authUri not in self._theData[keyvalue]:
                    self._theData[keyvalue][authUri]={}
                if nameString not in self._theData[keyvalue][authUri]:
                    self._theData[keyvalue][authUri][nameString] = {}
                    self._theData[keyvalue][authUri][nameString]=0
                self._theData[keyvalue][authUri][nameString] += 1     
    
    
    #force persons to collide in theData e.g. if they have the same lastname and first initial.
    #a string for the ruleName is optional
    def collidePersons(self, ruleName="SameLastSameFirstInit"):
        
        pubUris = self._datasource.getPublicationURIs(self._keyidentifier)
        
        self._theData={}
        
        
        for pubUri in pubUris:
            #Pull all authorship/coll uris as links to person uris
            shipUris = self._datasource.getPublicationAuthorshipURIs(pubUri)
            tionUris = self._datasource.getPublicationCollaborationURIs(pubUri)
            self.applyRule(shipUris, ruleName)
            self.applyRule(tionUris, ruleName)

                
        theReport={}
        
        #logging.info("Your input file "+self._datasource._filename+" had "+str(len(self._theData))+" people, ")
        
        for keyvalue in self._theData:
            if len(self._theData[keyvalue])>1:
                theReport[keyvalue]=self._theData[keyvalue]
        logging.info("-"*65)
        logging.info("Your input file "+self._datasource._filename+" had "+str(len(self._theData)+len(theReport))+" people, where a person has a foaf:lastName.  The coreffer.py rule "+ruleName+" thinks that "+str(len(theReport))+" people were assigned multiple URIs by Harvester and there are really "+str(len(self._theData))+" people.")
        logging.info("-"*65)
        
        return theReport
    
    
    def updatePersonURIs(self, UrisToMentions, uniqueUri):
        for person in UrisToMentions:
            if len(UrisToMentions[person].keys())!=1:
                raise CorefferException("error: person uri "+person+" should have a unique name mention associated with it.  Found instead: "+str(UrisToMentions[person].keys()))
            mention=UrisToMentions[person].keys()[0]
        
            if (self._isBlacklisted(uniqueUri,mention)):
                logging.info(person+" cannot be merged with "+uniqueUri+"...")
                continue
            elif(person!=uniqueUri):
                #logging breaks on unicode mention string: logging.info(mention+" will merge with "+uniqueUri+"...")  
                logging.info(person+" will merge with "+uniqueUri+"...")            

            authorships = self._datasource.getAuthorshipURIs(person)
            collaborations = self._datasource.getCollaborationURIs(person)
            parts = self._datasource.getAuthorName(person)
            nameTemplate = Coreffer.makeNameTemplateFromDataSource(parts)
            if nameTemplate is None:
                continue            
            authNameString = "Authorship for "+nameTemplate['lname']+", "+nameTemplate['fname']
            collNameString = "Collaboration for "+nameTemplate['lname']+", "+nameTemplate['fname']
            if nameTemplate['mname']:
                authNameString = authNameString + " " + nameTemplate['mname']
                collNameString = collNameString + " " + nameTemplate['mname']
            for authorship in authorships:
                self._datasource.changeAuthorship(DataSource.uri_literal_as_ref(authorship),DataSource.uri_literal_as_ref(uniqueUri), DataSource.string_as_literal(authNameString))
            for collaboration in collaborations:
                self._datasource.changeCollaboration(DataSource.uri_literal_as_ref(collaboration),DataSource.uri_literal_as_ref(uniqueUri), DataSource.string_as_literal(collNameString))
        self._datasource.serialize(self._outputfilename)    
    
    

    #a method to map name mentions to a single uri HERE.  you can apply a simple rule (pick the longest mention), or simply pick
    #the first uri encountered as unique(less desirable).  
    #Any other uri mentioned in the RDF file will need to be pointed to the new unique URI
    @staticmethod
    def mapMentionsToUniqueURI(UrisToMentions, keyval="", strategy="pickLongestMention"):
        uriToReturn=""
        if strategy=="pickLongestMention":
            longestMention=""
            for uri in UrisToMentions:
                if len(UrisToMentions[uri].keys())!=1:
                    raise CorefferException("error: uri "+uri+" should have a unique name mention associated with it.  Found instead: "+str(UrisToMentions[uri].keys()))
                mention=UrisToMentions[uri].keys()[0]
                if len(mention)>len(longestMention):
                    longestMention=mention
                    uriToReturn=uri
        elif strategy=="pickCollidingKeyValue":
            foundKeyVal=False 
            for uri in UrisToMentions:
                if len(UrisToMentions[uri].keys())!=1:
                    raise CorefferException("error: uri "+uri+" should have a unique name mention associated with it.  Found instead: "+str(UrisToMentions[uri].keys()))
                #return the (unique) nameString mention for that candidate uri   
                mention=Coreffer.normalize(UrisToMentions[uri].keys()[0])
                logging.debug("mapMentionsToUniqueURI(): comparing mention "+str(mention)+ " to keyval "+keyval)
                if mention==keyval:
                    foundKeyVal=True
                    uriToReturn = uri
            if foundKeyVal==False:
                #just return the first URI
                uriToReturn = UrisToMentions.keys()[0]
        else:
            #you passed in some nonempty string, but the func doesn't recognize it. 
            if len(UrisToMentions.keys()[0]):
                uriToReturn = UrisToMentions.keys()[0]
        #return unique uri
        return uriToReturn
        

def main():
    
        logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', filename='../../logs/coreffer.log', filemode='w', level=logging.INFO)
        
        print "usage: coreffer.py -t -i <inputfile> -k {\"pmid\"|\"doi\"}, use -t option if you want to co-reference the names in the test data instead of <inputfile>.  <inputfile> should be an absolute or relative path with the / separator, either on Windows or Unix.\n\n"

        test=False
        inputfile='../../rsc/rdf/umt/mizner-rl-vivo-additions.rdf.xml'
        keyidentifier="bibo:pmid"
    
        try:
            (options, arguments) = getopt.getopt(sys.argv[1:],'ti:k:')
        except getopt.GetoptError:
            print "\n\nThere was an error in your options.\n\nusage: coreffer.py -t -i <inputfile> -k {\"pmid\"|\"doi\"}\n\n\t-> use the -t option if you want to dedupe the test data instead of <inputfile>.\n\t-> <inputfile> should be an absolute or relative path with the / separator, either on Windows or Unix.\n\n"
            sys.exit(2)
        for opt, arg in options:
            if opt in ("-i"):
                inputfile=arg
            elif opt in ("-t"):
                test=True
            elif opt in ("-k"):
                if arg in ("pmid", "doi"):
                    keyidentifier="bibo:"+arg
                else:
                    print "\n\nyou must specify pmid (PubMed Identifer) or doi (Digital Object Identifier) as the unique identifier for publications, using the -k option.\nIf you omit the -k option, pmid is the default.\n\n"
                    sys.exit(2)                
        if test:
            print "no tests set up, exiting..."
            sys.exit(-1)
        else:
            n = Coreffer(inputfile, keyidentifier, 'pn0')
            outfile = n._outputfilename
            collisions = n.collidePersons()
            for item in collisions:
                logging.info("collided person name mentions on this key: "+unicode(item))
                for uri in collisions[item]:
                    logging.info("uri: "),
                    logging.info(uri)
                    logging.info(str(collisions[item][uri]))
                uniqueUri = Coreffer.mapMentionsToUniqueURI(collisions[item],keyval=item, strategy="pickLongestMention")
                logging.info("uniqueUri: "+str(uniqueUri))   
                logging.info("")
                n.updatePersonURIs(collisions[item], uniqueUri)
            logging.info("-"*65)
            
            # collisions = n.collidePersons("ForLastNameChange")
            # for item in collisions:
                # logging.info("keyvalue: "+str(item))
                # for uri in collisions[item]:
                    # logging.info("uri: "),
                    # logging.info(uri)
                    # logging.info(str(collisions[item][uri]))
                # uniqueUri = Coreffer.mapMentionsToUniqueURI(collisions[item], keyval=item, strategy="pickCollidingKeyValue")
                # logging.info("uniqueUri: "+str(uniqueUri))   
                # logging.info("")
                # n.updatePersonURIs(collisions[item], uniqueUri)
                    
                    
if __name__=='__main__':
    main()
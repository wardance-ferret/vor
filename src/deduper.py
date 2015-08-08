#!/usr/bin/python

import getopt
import logging
import sys
from vivodata import DataSource
from vivouri import VivoUri
from vivoquery import VIVOIndividualPresentQuery, VIVOIssnQuery, VIVOPMIDPresentQuery, VIVODOIPresentQuery
import string
from testme import TestMe


#Deduper.py removes duplicate uris from a DataSource; 
#Let's keep it to one DataSource, one Deduper.
#These (may) be duplicate uris already in Vivo (established by SPARQL query to a live endpoint) or in
#the vivo-additions.rdf.xml file from Harvester (established by SPARQL query).  The functions in this utility
#will try to make sense of both. 
#This should be considered a utility, not a workflow-tool (as pubgui.py is)
#Revised dedupePubsPerAuthorship 4/14/14 to check whether runnerUpUri hasHttpPrefix is true

class DeduperException(Exception):
    def __init__(self, message):
        logging.error(message)

class Deduper:
    
    _mux_joinchar = "_"
    
    _namespace = ""
    
    @staticmethod
    def _mux_UriPair(uri_1, uri_2):
        if(uri_1=="" or uri_2==""):
            raise DeduperException("SEVERE, Empty URI: cannot mux URIs ("+uri_1+") and ("+uri_2+")")    
        if VivoUri.extractUriPrefix(uri_1) != VivoUri.extractUriPrefix(uri_2):
            raise DeduperException("SEVERE: cannot mux URIs "+str(uri_1)+" and "+str(uri_2)+" Please that all URIs to mux are in the same namespace!")
    
        return VivoUri.extractNfromUri(uri_1) + Deduper._mux_joinchar + VivoUri.extractNfromUri(uri_2)
    

    @staticmethod
    def _demux_UriPair(uri_pair):
        
        parts=uri_pair.split(Deduper._mux_joinchar)
        
        uri_1 = VivoUri.encodeNasUri(Deduper._namespace, parts[0])
        uri_2 = VivoUri.encodeNasUri(Deduper._namespace, parts[1])
        
        return [uri_1, uri_2]


        
    def __init__(self, filename, keyidentifier, workflowcode='pd0'):
        try:
            self._datasource = DataSource(filename)
        except Exception as e:
            raise DeduperException("there was a problem opening "+filename+" as a datasource")
        self._outputfilename = VivoUri.createOutputFileName(filename, workflowcode)
        self._keyidentifier=keyidentifier
        pubs = self._datasource.getPublicationURIs(self._keyidentifier)
        Deduper._namespace=VivoUri.extractNamespace(pubs[0])
        logging.info("output will be written to "+self._outputfilename+"\n")
    

    
    
    
    #this is a variation on authorshipsPerAuthorPublication() to push limits of rdflib's support of sparql.
    def dedupeAuthorships(self):
    
        pubs = self._datasource.getPublicationURIs(self._keyidentifier)
    
        #theData lets us dedupe the authorships against author-pub pairs, but it uses string uris rather than the graph nodes managed by rdflib.  That is, you must then use DataSource.uri_literal_as_ref(string) to add, change or remove a uri from the graph...
        theData={}
    
        for pub in pubs: 
            
        
            #get distinct authorships.  We can now either check for non-unique linkedInformationResource, or non-unique linkedAuthor, or (for this function) a redundant authorship connecting author and pub. 
            authorships = self._datasource.getPublicationAuthorshipURIs(pub)

           
            for authorship in authorships:
            
                author = self._datasource.getAuthorURIFromAuthorship(authorship)
                keyvalue = Deduper._mux_UriPair(author,pub)
                
                if keyvalue not in theData:
                    theData[keyvalue] = []
                
                
                theData[keyvalue].append(authorship)
                logging.debug("dedupeAuthorships(): " + keyvalue + " has "+str(len(theData[keyvalue]))+" members")

        exclusion_list = {}
        
        for keyvalue in theData:        
        
            if len(theData[keyvalue])>1:
            
                authorships = theData[keyvalue]
                
                for ship in authorships:
                
                    if not VIVOIndividualPresentQuery.isPresent(ship):
                        parts = Deduper._demux_UriPair(keyvalue)
                        logging.debug("duplicate authorship "+ship+" not found in vivo, will delete. will not delete the author uri.")
                        exclusion_list[ship] = VivoUri.encodeNasUri(Deduper._namespace, parts[0]) 
                 
                    else:
                        logging.debug("duplicate authorship "+ship+" was found in vivo.  I won't exclude this uri from the input model.")
        
        
        for ship in exclusion_list:
            self._datasource.removeAuthorFromAuthorship(DataSource.uri_literal_as_ref(ship), DataSource.uri_literal_as_ref(exclusion_list[ship]))
            self._datasource.removeAuthorship(DataSource.uri_literal_as_ref(ship))
           
        
        
        self._datasource.serialize(self._outputfilename)
    

    #The * notation implies that a list (or dictionary) passed in will be treated as a tuple (pg. 103 Harms/McDonald, _Quick Python_),
    #but we're not using it, so the list (or dictionary) will be treated like what it is... 
    def findMinimumRankUri(self, field, collaborationUriStrings):
        minimumRank = 1000000
        resultUriString=""
        if len(collaborationUriStrings)==0:
            return resultUriString
        for uriString in list(collaborationUriStrings):
            if (self._datasource.getRank(uriString, field) < minimumRank):
                #note how field is the second parameter in this function call (it is optional)
                minimumRank = self._datasource.getRank(uriString,field)
                resultUriString = uriString
        logging.debug(resultUriString+" has coll rank "+str(minimumRank))        
        return resultUriString
    
    
    
    #It's a good idea to run dedupeCollaboratorsPerCollaboration() first before dedupeCollaborations.   
    def dedupeCollaborations(self):
   
        pubs = self._datasource.getPublicationURIs(self._keyidentifier)
    
        #TODO: Explain what the following means or come up with something that doesn't need explanation -- the dictionary (theData) dedupes the collaborations against collaborator-pub pairs, but it uses string uris rather than the graph nodes managed by rdflib.  That is, you must then use DataSource.uri_literal_as_ref(string) to add, change or remove a uri from the graph...
        theData={}
    
        for pub in pubs: 
       
            #get distinct collaborations.  We can now check for a redundant collaboration connecting collaborator and pub. 
            collaborations = self._datasource.getPublicationCollaborationURIs(pub)
            logging.debug("dedupeCollaborations(): pub "+pub+" has "+str(len(collaborations))
            +" collaborations")
           
            for collaboration in collaborations:
                if len(self._datasource.getAllCollaboratorURIFromCollaboration(collaboration)) > 1:
                    logging.error("dedupeCollaborations():  found more than one collaborator for collaboration "+collaboration+".  It's a good idea to run dedupeCollaboratorsPerCollaboration() first.")
                    raise DeduperException("dedupeCollaborations():  found more than one collaborator for collaboration "+collaboration+".  It's a good idea to run dedupeCollaboratorsPerCollaboration() first.")
                elif len(self._datasource.getAllCollaboratorURIFromCollaboration(collaboration)) == 0:
                    raise DeduperException("dedupecollaborations(): found no collaborator for collaboration "+collaboration)
                collaborator = self._datasource.getCollaboratorURIFromCollaboration(collaboration)    
                keyvalue = Deduper._mux_UriPair(collaborator,pub)
                
                if keyvalue not in theData:
                    theData[keyvalue] = []
                
                theData[keyvalue].append(collaboration)
                logging.debug("dedupeCollaborations(): "+keyvalue + " has "+str(len(theData[keyvalue]))+" members: ")
                for member in theData[keyvalue]:
                    logging.debug("\t"+member)

        exclude_by_uri = {}
        foundInVivo={}
        
        for keyvalue in theData:        
        
            if len(theData[keyvalue])>1:
            
                collaborations = theData[keyvalue]
                
                for tion in collaborations:
                
                    if not VIVOIndividualPresentQuery.isPresent(tion):

                        parts = Deduper._demux_UriPair(keyvalue) 
                        logging.debug("This duplicate "+tion+" collaboration wasn't found in vivo. Will delete all collaborations except for the highest-ranked one, but will not delete the collaborator uri.")
                        #(Keyed on the collaboration URI, the first part is the collaborator URI
                        #and the second part is the pub URI -- currently not used.)
                        if tion not in exclude_by_uri:
                            exclude_by_uri[tion]=[]
                        exclude_by_uri[tion].append(VivoUri.encodeNasUri(Deduper._namespace, parts[0]))
                        exclude_by_uri[tion].append(VivoUri.encodeNasUri(Deduper._namespace, parts[1]))
                        
                    else:
                        logging.debug("This duplicate "+tion+" collaboration was found in vivo. Will remove any other collaborations.")
                        foundInVivo[keyvalue]=1
        
        #The logic from this point is different from redundantAuthorships().  It's because we expect duplicate collaborations from bad PubMed source, not only because a collaboration is already in Vivo (although it may be!)
       
        for keyvalue in theData:        
        
            if len(theData[keyvalue])>1:
            
                collaborations = theData[keyvalue]
                                    
                if (keyvalue in foundInVivo):
                                        
                    for tion in exclude_by_uri:
                        self._datasource.removeCollaboratorFromCollaboration(DataSource.uri_literal_as_ref(tion), DataSource.uri_literal_as_ref(exclude_by_uri[tion][0]))
                        self._datasource.removeCollaboration(DataSource.uri_literal_as_ref(tion))
                    
                else:
                    #get the excluded collaboration URIs into a list form so I can iterate over them
                    newCollabs = []
                    for collab in collaborations:
                        if collab in exclude_by_uri:
                            newCollabs.append(collab)
                    
                    
                    minRankCollab = self.findMinimumRankUri('collaboratorRank', newCollabs) 
        
                    for collab in newCollabs:
                        logging.debug("comparing minimum rank collaboration: "+minRankCollab+" to "+collab)
                        if (collab==minRankCollab):
                            logging.debug("***found minimum rank collaboration!")
                            continue
                        else:
                            self._datasource.removeCollaboratorFromCollaboration(DataSource.uri_literal_as_ref(collab), DataSource.uri_literal_as_ref(exclude_by_uri[collab][0]))
                            self._datasource.removeCollaboration(DataSource.uri_literal_as_ref(collab))
       
        self._datasource.serialize(self._outputfilename)
    
    
    #removes a collaboration if a person and publication are already linked by an authorship.  It uses strings rather than uri's, therefore you must use DataSource.uri_literal_as_ref(string) to add, change or remove a uri from the graph.
    #5/7/2014:  Won't do coreference if an author and collaborator have separate URIs, but whose names match
    def removeCollaborationIfExistingAuthorship(self):
        pubs = self._datasource.getPublicationURIs(self._keyidentifier)

        theAuthorships={}
        theCollaborations={}
        exclusion_list = {}
    
        for pub in pubs: 

            #get distinct collaborations.  In general, we do this to check for non-unique linkedInformationResource, or non-unique linkedCollaborator, or (in this particular function) a redundant collaboration connecting collaborator and pub. 
            collaborations = self._datasource.getPublicationCollaborationURIs(pub)
            authorships = self._datasource.getPublicationAuthorshipURIs(pub)
            logging.debug("removeCollaborationIfExistingAuthorship(): pub "+VivoUri.extractNfromUri(pub)+" has "+str(len(collaborations))
            +" collaborations")
           
            for collaboration in collaborations:
                collaborator = self._datasource.getCollaboratorURIFromCollaboration(collaboration)
                keyvalue = Deduper._mux_UriPair(collaborator,pub)
            
                if keyvalue not in theCollaborations:
                    theCollaborations[keyvalue] = []
                else:
                    logging.error("removeCollaborationIfExistingAuthorship() on key-value "+keyvalue+": please call the dedupeCollaborations() method first so there's exactly one collaboration for the person/pub pair")
                    raise Exception("removeCollaborationIfExistingAuthorship(): please call the dedupeCollaborations() method first so there's exactly one collaboration for the person/pub pair")                
                theCollaborations[keyvalue].append(collaboration)
                logging.debug("removeCollaborationIfExistingAuthorship(): " + keyvalue + " has "+str(len(theCollaborations[keyvalue]))+" members: ")
                for member in theCollaborations[keyvalue]:
                    logging.debug("\t"+VivoUri.extractNfromUri(member))
            
            for authorship in authorships:
                author = self._datasource.getAuthorURIFromAuthorship(authorship)
                keyvalue =  Deduper._mux_UriPair(author,pub)
                
                if keyvalue not in theAuthorships:
                    theAuthorships[keyvalue] = []
                theAuthorships[keyvalue].append(authorship)
            
                
        for keyvalue in theCollaborations:        
            if len(theCollaborations[keyvalue])!=1:
                logging.error("removeCollaborationIfExistingAuthorship() on key-value "+keyvalue+": please call the dedupeCollaborations() method first so there's exactly one collaboration for the person/pub pair")
                raise Exception("removeCollaborationIfExistingAuthorship(): please call the dedupeCollaborations() method first so there's exactly one collaboration for the person/pub pair")
            else:
                tion = theCollaborations[keyvalue][0]
                if keyvalue in theAuthorships:
                        parts = Deduper._demux_UriPair(keyvalue)
                        logging.debug("muxed URI: "+keyvalue )
                        logging.debug("demux URI, part 1: "+VivoUri.extractNfromUri(parts[0]))
                        logging.debug("demux URI, part 2: " +VivoUri.extractNfromUri(parts[1]))
                        logging.debug("a collaboration "+VivoUri.extractNfromUri(tion)+" was found that duplicates the authorship uri for the person pub pair "+keyvalue+".  Keeping authorship uri, removing collaboration uri.")
                        logging.debug("namespace:"+Deduper._namespace)
                        exclusion_list[tion] = VivoUri.encodeNasUri(Deduper._namespace, parts[0]) 
  
        #The logic from this point is different from dedupeAuthorships or dedupeCollaborations, because we expect a person to be duplicated as author and collaborator on a publication in PubMed
               
        #for ex in exclusion_list.iterkeys():
        #    print "exclude: "+ex
       
        for uri in exclusion_list:
            self._datasource.removeCollaboratorFromCollaboration(DataSource.uri_literal_as_ref(uri), DataSource.uri_literal_as_ref(exclusion_list[uri]))
            #why don't we need to remove the pub from the collaboration too??
            self._datasource.removeCollaboration(DataSource.uri_literal_as_ref(uri))
       
        
        self._datasource.serialize(self._outputfilename)    
 
        
       
    
    #query authorships with (authors per authorship > 1) and give a unique author...
    #TODO: (in the future, do the person coreference that Harvester failed to do)
    def dedupeAuthorsPerAuthorship(self):
        pubUris = self._datasource.getPublicationURIs(self._keyidentifier) 
        
        keepUri=""
        exclusion_list=[]
        keeperFound = False
        
        for uri in pubUris:
            
            authUris = self._datasource.getPublicationAuthorshipURIs(uri)
            
            for auth in authUris:
            
                personUris = self._datasource.getAllAuthorURIFromAuthorship(auth)
                
                if len(personUris) > 1:
                
                    for per in personUris:
                        
                        if VIVOIndividualPresentQuery.isPresent(per):
                            keeperFound=True
                        else:
                            exclusion_list.append(per)
                    #if there are multiple linked authors in an authorship, we'd expect exactly one of these to be in Vivo.
                    #if it's not the case, then we arbitrarily pick the first one in the input model...
                    if not keeperFound:
                        keepUri=personUris[0]
                        keeperFound=True
                        
                    for excluded in exclusion_list:
                        if keeperFound and keepUri!="" and excluded==keepUri:
                            continue
                        else:
                            #remove authors(s) from authorship
                            self._datasource.removeAuthorFromAuthorship(DataSource.uri_literal_as_ref(auth), DataSource.uri_literal_as_ref(excluded))
                            #remove the author
                            self._datasource.removeAuthor(DataSource.uri_literal_as_ref(excluded))
        
        self._datasource.serialize(self._outputfilename)

    #Here I'm interested in collaborations with more than 1 collaborator per collaboration,
    #method: get unique collaborations with non-unique linkedCollaborator, and return a unique linkedCollaborator. 
    def dedupeCollaboratorsPerCollaboration(self):
        
        pubUris = self._datasource.getPublicationURIs(self._keyidentifier) 
        

        
        for uri in pubUris:
            
            collabUris = self._datasource.getPublicationCollaborationURIs(uri)
            
            for collab in collabUris:
                keepUri=""
                exclusion_list=[]
                keeperFound = False            
            
                personUris = self._datasource.getAllCollaboratorURIFromCollaboration(collab)
                
                if len(personUris) > 1:
                    logging.debug("This collaboration had multiple collaborators: "+collab)
                    for per in personUris:
                    #if there are multiple linked collaborators in a collaboration, we'd expect exactly one of these to be in Vivo.  Ordinarily that is the case.                        
                        if VIVOIndividualPresentQuery.isPresent(per):
                            keeperFound=True
                        else:
                            exclusion_list.append(per)

                    #if it's not the case, then we arbitrarily pick the first one in the input model...
                    if not keeperFound:
                        keepUri=personUris[0]
                        keeperFound=True
                        
                    for excluded in exclusion_list:
                        if keeperFound and keepUri!="" and excluded==keepUri:
                            logging.debug("will keep collaborator "+keepUri+" for collaboration "+collab)
                        else:
                            #remove collaborator(s) from collaboration
                            self._datasource.removeCollaboratorFromCollaboration(DataSource.uri_literal_as_ref(collab), DataSource.uri_literal_as_ref(excluded))
                            #remove the collaborator
                            self._datasource.removeCollaborator(DataSource.uri_literal_as_ref(excluded))
        self._datasource.serialize(self._outputfilename)

        
        

        
 
        
    #query publications where publications per authorship > 1 by looking for duplicate PubMed IDs.  For those, give a unique pub uri for a PubMed ID (preferably the uri already in Vivo).  Finally, remove authorships in Vivo that point to the other pubs with a call to self._datasource.removePublication() for each pub. 
    #This is basically an abstraction of what pubgui.py and pubtool1.py do.  Note that we don't try to do coreference on the publication title, hence our need for a PubMed ID...
    def dedupePubsPerAuthorship(self):
    
        print "\n\ndeduper.py performs deduplication on a Vivo additions rdf file according to a duplication key (either a Pubmed ID or a DOI).\n\t->For example, dedupePubsPerAuthorship() will change publication uris in the input file that have duplicate key so that they point to the unique uri already in Vivo.\n\t->It assumes that it will find a matching uri in the input file.\n\t->Also, it assumes the number of authorships of this uri will be greater than or equal to those of the unique uri in Vivo.\n\t->Unfortunately, it doesn't check whether Vivo has a unique uri."
        
        pubUris = self._datasource.getPublicationURIs(self._keyidentifier)
        
        theData={}
        keeper_list = []
 
        for uri in pubUris:
            if self._keyidentifier=="bibo:pmid":
                uid = self._datasource.getPublicationPMID(uri)
            elif self._keyidentifier=="bibo:doi":
                uid = self._datasource.getPublicationDOI(uri)
                
            if uid not in theData:
                theData[uid] = []

            theData[uid].append(uri)

                
        for uid in theData:

            keeperFound=False
            uidFound = False
            numberOfAuthorships=0
            keepUri=""
            runnerUpUri=""
        
            if len(theData[uid])>1:
            
                for uri in theData[uid]:
                    if self._keyidentifier=="bibo:pmid":
                        uidFound=VIVOPMIDPresentQuery().isPresent(uid)
                    elif self._keyidentifier=="bibo:doi":
                        uidFound=VIVODOIPresentQuery().isPresent(uid)
                    
                    if not uidFound:
                        logging.error("couldn't find publication "+uid+" in Vivo, yet it is duplicated in the Input.  Will pick one in the Input...")
                        if not keeperFound:
                            keeper_list.append(uri)
                            keeperFound=True
                    else:
                        #TODO: pick uri with greater authorship count for uid
                        logging.info("found pub "+uid+" in Vivo, examining individual "+VivoUri.extractNfromUri(uri)+" in the input...")
                        
                        results = self._datasource.getPublicationAuthorshipURIs(uri)
                        collabs = self._datasource.getPublicationCollaborationURIs(uri)
                        logging.info("pub uri: "+uri+" has "+str(len(results))+" authorships and "+str(len(collabs))+" collaborations...")
                        
                        #we always want the pub uri with the greater number of authorships...
                        if len(results) > numberOfAuthorships:
                           numberOfAuthorships = len(results)
                           keepUri = uri
                        elif len(results) and len(results)==numberOfAuthorships:
                            runnerUpUri = uri
                        
                        
                
                if keeperFound==False:
                    for uri in theData[uid]:
                        if  keepUri != "" and uri==keepUri:
                            logging.debug("keepUri: "+keepUri+" has "+str(numberOfAuthorships)+" authorships")
                            if not VIVOIndividualPresentQuery().isPresent(uri):
                                if VivoUri.hasHttpPrefix(runnerUpUri) and not VIVOIndividualPresentQuery().isPresent(runnerUpUri):
                                    raise DeduperException("SEVERE:  pub uri "+uri+" and pub uri "+runnerUpUri+" both had the largest number of authorships for that uid, so we can't pick only one uri for uid "+uid+", but neither was found in Vivo.  Perhaps you should check the data in Vivo to see if it has changed, or re-run Harvester...")
                                elif VivoUri.hasHttpPrefix(runnerUpUri):
                                    uri=runnerUpUri
                            keeper_list.append(uri)
            
            elif len(theData[uid])==1:
                #always keep the pub uri if there is no duplication
                keeper_list.append(theData[uid][0])   
        
        if len(keeper_list)==len(pubUris):
            logging.info("***Keeping all publications found in the input file...")
        else:
            for uri in pubUris:
            
                if uri in keeper_list:
                    logging.info("keeper_list:  will not remove pub uri: "+uri)
                else:
                    logging.info("removing pub uri: "+uri+" ...")            
                    self._datasource.removePublication(DataSource.uri_literal_as_ref(uri))
                        
        logging.info("All Done!")
        self._datasource.serialize(self._outputfilename)

    def removePubFoundInVivo(self):
        pubUris = self._datasource.getPublicationURIs(self._keyidentifier)
        
        #for each pubUri, do a Vivo lookup on PMID
        for uri in pubUris:
                if self._keyidentifier=="bibo:pmid":
                    uid = self._datasource.getPublicationPMID(uri)
                elif self._keyidentifier=="bibo:doi":
                    uid = self._datasource.getPublicationDOI(uri)
                uidFound=False
                if self._keyidentifier=="bibo:pmid":
                    uidFound=VIVOPMIDPresentQuery().isPresent(uid)
                elif self._keyidentifier=="bibo:doi":
                    uidFound=VIVODOIPresentQuery().isPresent(uid)
                if (uidFound):
                    logging.info("found in Vivo, removing pub uri from in vivo-additions.rdf.xml: "+uri+" ...")            
                    self._datasource.removePublication(DataSource.uri_literal_as_ref(uri))
                    self._datasource.serialize(self._outputfilename)
    
        
    #TODO: insert the rules for collaborations here...
    def dedupePubsPerCollaboration(self):
        pass
        
    #TODO: we need to query for multiple dates, volumes, starting pages et al. and not introduce duplicates (i.e. in this case, just pick the Vivo version)  Caution: if the values for these fields are already in Vivo, Harvester might still fail to duplicate them in vivo-additions.rdf.xml.
    def dedupeNumericsPerPub(self):
        pass
      
        
    #query publications with (venues Per publication > 1) and do something about it...  
    def dedupeVenuesPerPub(self):
    
        #Unfortunately, self._datasource.getPubsWithDuplicateVenues()
        #sends a query that returns everything (though the query *does* work on fuseki).  Maybe someday this can be made to work?
        #pubs = self._datasource.getPubsWithDuplicateVenues()
        
        #get all pub uris in the input file.        
        all_pub_uris = self._datasource.getPublicationURIs(self._keyidentifier)        
        logging.info(str(len(all_pub_uris))+" publications found in the file")
        
        #we'll keep a dictionary of venues keyed on pub uri
        input_venues = {}
        
        for pub_uri in all_pub_uris:
            #must extract the unicode string as the uri because pub_uri is a Python list element which is a URI ref, not a URI literal (string).
            #TODO: figure out why rdflib doesn't provide a way to get the string from the pub uri?
            #pub_string = VivoUri.extractUnicodeString(str(pub_uri))
            
            logging.debug('reading venues for pub %s (%s) from input %s', str(pub_uri), pub_uri, self._datasource._filename) 
            
            if string.strip(pub_uri)=="":
                    continue
            else:
                #get the multiple venue uris for the pub...
                venue_uris = self._datasource.getPublicationVenueURIs(pub_uri)
            
                if not len(venue_uris):
                    logging.warning("No venue found in the input file for pub "+pub_uri)
                    continue
                else:
                    #update a pub uri in the venues dict with information on its venue uris, found in the input file... 
                    input_venues[pub_uri] = []
                    for venue_uri in venue_uris:
                        input_venues[pub_uri].append(venue_uri)
        
        #create an exclusion list for venues, adding a venue uri to the list if its issn was found in vivo.
        #TODO: if it seems slow to check exclusion_list for an element, use a hash rather than an array...
        #NOTE: vivo_venues is a counterpart to input_venues which helps us decide which venue uris get excluded.
        exclude_list = []
        vivo_venues = {}
        
        
        logging.debug("processing venues dictionary, checking for each publication's venues in Vivo...")
        
        for pub_uri in input_venues:
            #give me another publication with a problem, and do the whole loop again...        
            logging.debug("publication:"+pub_uri)
            if pub_uri not in vivo_venues:
                vivo_venues[pub_uri]=[]
            
            if len(input_venues[pub_uri])==0:
                logging.warn("publication "+pub_uri+" had no venues.")
            elif len(input_venues[pub_uri]) == 1:
                logging.debug("publication "+pub_uri+" had one venue: "+str(input_venues[pub_uri]))
            else:
                #Begin a command line dialogue
                print("The input file says that publication "+pub_uri+" has these venues:")  
                for venue in input_venues[pub_uri]:
                    print(venue)
                    #this comparison between the data source (input) and the live vivo
                    #should be here, not in vivodata.py
                    issn=self._datasource.getPublicationVenueISSN(venue)
                    if issn=='':
                        continue
                    if VIVOIssnQuery.isPresent(issn):
                        if not VIVOIndividualPresentQuery.isPresent(venue):
                            exclude_list.append(venue)
                        else:
                            logging.info('Pub %s published in ISSN %s',pub_uri,issn)
                            if venue not in vivo_venues[pub_uri]:
                                vivo_venues[pub_uri].append(venue)
                        #what does this mean?  obviously we'd want a new pub to have the link
                        #to the pub venue already in vivo, given the match on issn, so we don't exclude all uri references to the vivo pub venue when we save out the input data.
               
                print("venues in vivo related to pub "+pub_uri +":")
                for known_venue in vivo_venues[pub_uri]:
                    print(known_venue)
              
                        #change pub venues to the existing vivo uri, or, if none exists, print a warning.
                if len(vivo_venues[pub_uri])==0:
                    print ("this publication venue wasn't found by ISSN query in Vivo.  this util will pick one uri conveniently and rewrite all the others")
                    new_venue_uri = input_venues[pub_uri][0]
                    for uri in input_venues[pub_uri]:
                                if (new_venue_uri != uri):
                                    self._datasource.changePublicationVenue(DataSource.uri_literal_as_ref(pub_uri), DataSource.uri_literal_as_ref(uri), DataSource.uri_literal_as_ref(new_venue_uri))
                                    
                elif len(vivo_venues[pub_uri])>1:
                    #TODO: this condition is never met, although we could return multiple 
                    #Vivo venues for pub_uri. Besides that, this is really a problem with Vivo itself.
                    print("multiple publication venue uris were already found in Vivo.  Please resolve this problem (i.e. pick one uri already in Vivo for this resource) before adding the new data")
                    
                    got_input=False
                    
                    while not got_input:
                        user_n_input=raw_input("\nEnter an n##### string you have found in Vivo to create a single uri in the input file:")
                        user_decision=raw_input('You entered %s. Hit <Enter> to rewrite the input file so it maps onto this uri, otherwise type <n><Enter>' % user_n_input)
                        if user_decision=='n' or user_decision=='N':
                            got_input=True
                            continue
                        new_venue_uri=VivoUri.encodeNasUri("http://vivo.health.unm.edu/", user_n_input)
                        if not VIVOIndividualPresentQuery.isPresent(new_venue_uri):
                            print "\n\n***ERROR: I couldn't find uri %s in Vivo!\n\n" % new_venue_uri
                        else:
                            got_input=True
                            for uri in venues[pub_uri]:
                                if (new_venue_uri != uri):
                                    self._datasource.changePublicationVenue(DataSource.uri_literal_as_ref(pub_uri), DataSource.uri_literal_as_ref(uri), DataSource.uri_literal_as_ref(new_venue_uri))
                                    
                else:
                    new_venue_uri = vivo_venues[pub_uri][0]
                    
                    for uri in input_venues[pub_uri]:
                    
                        if (new_venue_uri != uri):
                            self._datasource.changePublicationVenue(DataSource.uri_literal_as_ref(pub_uri), DataSource.uri_literal_as_ref(uri), DataSource.uri_literal_as_ref(new_venue_uri))  
        
        logging.info("All Done!")
        print "\n\nHere are the unique identifiers of publications, found in the file:"
        count=0
        for pub in all_pub_uris:
            count+=1
            print str(count)+".  ",
            print str(pub)+" has "+self._keyidentifier+" ",
            if self._keyidentifier=="bibo:pmid":
                print str(self._datasource.getPublicationPMID(DataSource.uri_literal_as_ref(pub)))
            elif self._keyidentifier=="bibo:doi":
                print str(self._datasource.getPublicationDOI(DataSource.uri_literal_as_ref(pub)))
        
        
        self._datasource.serialize(self._outputfilename)    

        
    def removeAllOtherCollaborations(self, collaboratorUriToKeep):
        pubUris = self._datasource.getPublicationURIs(self._keyidentifier)
        for uri in pubUris:
            collaborations = self._datasource.getPublicationCollaborationURIs(uri)
            for collaboration in collaborations:
                collaborator = self._datasource.getCollaboratorURIFromCollaboration(collaboration)
                logging.debug("collaborator examined: "+str(collaborator))
                logging.debug("collaborator to keep: "+str(collaboratorUriToKeep))
                if str(collaborator) == str(collaboratorUriToKeep):
                    logging.debug("keeping collaboration "+str(collaboration)+" for collaborator URI "+str(collaborator))
                    continue
                else:
                    self._datasource.removeCollaboration(DataSource.uri_literal_as_ref(collaboration))
                    self._datasource.serialize(self._outputfilename)
        
        
        
    def removeAllOtherAuthorships(self, authorUriToKeep):
        pubUris = self._datasource.getPublicationURIs(self._keyidentifier)
        for uri in pubUris:
            authorships = self._datasource.getPublicationAuthorshipURIs(uri)
            for authorship in authorships:
                author = self._datasource.getAuthorURIFromAuthorship(authorship)
                if str(author) == str(authorUriToKeep):
                    logging.debug("keeping authorship "+str(authorship)+" for author URI "+str(author))
                    continue
                else:
                    #logging.debug("removing authorship "+str(authorship)+".  author URI "+str(author)+" !== "+str(authorUriToKeep))
                    self._datasource.removeAuthorship(DataSource.uri_literal_as_ref(authorship))
                    self._datasource.serialize(self._outputfilename)


        
    def close(self):
        pass
        #self._datasource.close()
        
def main():
    
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', filename='../../logs/deduper.log', filemode='w', level=logging.INFO)
    
    #The default is not to run on test data, but to run on the output of pubtool 1...
    testmode=False
    inputfile='../../rsc/rdf/unm/pt1-vivo-additions.rdf.xml'
    keyidentifier="bibo:pmid"
    
    try:
        (options, arguments) = getopt.getopt(sys.argv[1:],'i:k:t')
    except getopt.GetoptError as err:
        print str(err)
        print "\n\nThere was an error in your options.\n\nusage: deduper.py -t -i <inputfile> -k {\"pmid\"|\"doi\"}\n\n\t-> use the -t option if you want to dedupe the test data instead of <inputfile>.\n\t-> <inputfile> should be an absolute or relative path with the / separator, either on Windows or Unix.\n\n"
        sys.exit(2)
    for (opt, arg) in options:
        if opt in ("-i"):
            inputfile=arg
        elif opt in ("-t"):
            testmode=True
        elif opt in ("-k"):
            if arg not in ("pmid", "doi"):
                print "\n\nyou must specify pmid (PubMed Identifer) or doi (Digital Object Identifier) as the unique identifier for publications, using the -k option.\nIf you omit the -k option, pmid is the default.\n\n"
                sys.exit(2)
            else:
                keyidentifier="bibo:"+arg
        else:
            print "unhandled option!"
            sys.exit(2)
        
    if testmode:    
        #TODO: put into a testing framework using node-counting rdflib (rather than text-counting count.py) where we get or don't get the expected node counts, and assume a particular Fuseki endpoint
        
        #does eliminating duplicate publications eliminate duplicate authorships?
        dd = Deduper('../../rsc/rdf/test/testinput-harvesterdupespubs-vivo-additions.rdf.xml', keyidentifier)
        origCount = len(dd._datasource.getPublicationURIs())
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-harvesterdupespubs-vivo-additions.rdf.xml",491,len(dd._datasource.getAllAuthorshipURIs()))
        dd.dedupePubsPerAuthorship()
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-harvesterdupespubs-vivo-additions.rdf.xml",origCount/2,len(dd._datasource.getPublicationURIs()))
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-harvesterdupespubs-vivo-additions.rdf.xml",243,len(dd._datasource.getAllAuthorshipURIs()))
        
        dd = Deduper('../../rsc/rdf/test/testinput-harvesterdupespubs-vivo-additions.rdf.xml', keyidentifier)
        dd.removePubFoundInVivo()
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-harvesterdupespubs-vivo-additions.rdf.xml",0,len(dd._datasource.getPublicationURIs()))
        

        dd = Deduper('../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml', keyidentifier)
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml",2,len(dd._datasource.getPublicationURIs()))
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml",8,len(dd._datasource.getAllAuthorshipURIs()))
        dd.dedupePubsPerAuthorship() 
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml",2,len(dd._datasource.getPublicationURIs()))
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml",8,len(dd._datasource.getAllAuthorshipURIs()))


        dd = Deduper('../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml', keyidentifier)
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml",8,len(dd._datasource.getAllAuthorshipURIs()))
        dd.dedupeAuthorships() 
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml",2,len(dd._datasource.getPublicationURIs()))
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml",6,len(dd._datasource.getAllAuthorshipURIs()))
        
        #run dd.dedupeAuthorsPerAuthorship()
        dd = Deduper('../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml', keyidentifier)
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml",8,len(dd._datasource.getAllAuthorshipURIs()))
        dd.dedupeAuthorsPerAuthorship()
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml",8,len(dd._datasource.getAllAuthorshipURIs()))
                
        
        

        #Is running dd.dedupeAuthorsPerAuthorship() first obligatory?
        dd = Deduper('../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml', keyidentifier)
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml",8,len(dd._datasource.getAllAuthorshipURIs()))
        dd.dedupeAuthorsPerAuthorship()
        dd.dedupeAuthorships() 
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pt1-vivo-additions.rdf.xml",6,len(dd._datasource.getAllAuthorshipURIs()))
        

        

        dd = Deduper('../../rsc/rdf/test/testinput-pg-vivo-additions.rdf.xml', keyidentifier)
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pg-vivo-additions.rdf.xml",2,len(dd._datasource.getAllPublicationVenueURIs()))
        dd.dedupeVenuesPerPub()
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-pg-vivo-additions.rdf.xml",1,len(dd._datasource.getAllPublicationVenueURIs()))
        

        
        dd = Deduper('../../rsc/rdf/test/testinput-dt1-vivo-additions.rdf.xml', keyidentifier)
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-dt1-vivo-additions.rdf.xml",285,len(dd._datasource.getAllCollaborationURIs()))
        dd.dedupeCollaboratorsPerCollaboration()        
        dd.dedupeCollaborations()
        TestMe.testMessage("deduper.py","../../rsc/rdf/test/testinput-dt1-vivo-additions.rdf.xml",262,len(dd._datasource.getAllCollaborationURIs()))
        
    else:
        #Use real data, not test data.
        logging.info("pd0.  Dedupe Publications per Authorship")
        dd = Deduper(inputfile, keyidentifier, 'pd0')
        outfile = dd._outputfilename
        dd.dedupePubsPerAuthorship()

        #Deduplication order is important!  There was a case with a co-collaborator who had both
        #duplicate collaborations and duplicate collaborators per collaboration.
        #removeCollaborationIfExistingAuthorship() would throw a exception because the collaboration was not unique #for that person/pub pair.  Deduping collaborators per collaboration *before* deduping collaborations removed the error.
        #TODO:  work out how to configure process order (decouple it from the script)
        # ##
        logging.info('-'*65)
        logging.info("pd1.  Dedupe Authors per Authorship (and deal with Collaborators in parallel)")
        dd = Deduper(outfile, keyidentifier, 'pd1')
        outfile = dd._outputfilename
        dd.dedupeAuthorsPerAuthorship()
        dd.removeAllOtherCollaborations("http://vivo.health.unm.edu/individual/n0")
        dd.dedupeCollaboratorsPerCollaboration()
        
        # ##
        logging.info('-'*65)
        logging.info("pd2.  Dedupe Authorships (and Collaborations)")
        dd = Deduper(outfile, keyidentifier, 'pd2')
        outfile = dd._outputfilename
        dd.dedupeAuthorships()
        dd.dedupeCollaborations()
        
        # ##
        logging.info('-'*65)
        logging.info("pd3.  Dedupe Venues per Publication")
        dd = Deduper(outfile, keyidentifier, 'pd3')
        outfile = dd._outputfilename
        dd.dedupeVenuesPerPub()
        
        logging.info('-'*65)
        logging.info("pd4.  Remove Collaboration if there is an Authorship")
        dd = Deduper(outfile, keyidentifier, 'pd4')
        outfile = dd._outputfilename
        dd.removeCollaborationIfExistingAuthorship()

        #removes a Publication (and its Authorships) from the additions file if they are already in Vivo
        #but weren't the time the additions file was created, so there is nothing to dedupe.
        
        logging.info('-'*65)
        logging.info("pd5.  Remove Publication and Authorships if they got added to Vivo after vivo-additions.rdf.xml got created.")
        dd = Deduper(outfile, keyidentifier, 'pd5')        
        outfile = dd._outputfilename
        dd.removePubFoundInVivo()
        
        #Define manual edits to the RDF here, if needed.
        
        
if __name__=='__main__':
    main()



    
    
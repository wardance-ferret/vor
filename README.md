Vivo Ongoing Refiner (VOR)
==========================
Orig. 10/21/2014, rev. 8/7/2015

A Sanity Checker for Data Ingest to the Vivo Research Networking Platform.

Tested with Vivo Harvester 1.5 (https://github.com/vivo-project/VIVO-Harvester), by appropriately adding or replacing the scripts or configurations in the harvester_mods folder.

When running Harvester, you are editing an RDF file that represents publications, authorships and authors for harvest into an instance of Vivo.  To help address certain problems, here are three command-line scripts: deduper.py, coreffer.py and refsplitter.py 

Because this was developed to harvest data from PubMed, the scripts allow you to harvest data about investigators as well as authors.  However, if your Vivo doesn't have the two additional classes vivo:Collaborator and vivo:Collaboration in the core ontology, the scripts ignore that data. [To do:  shift the classes Collaborator and Collaboration into a local ontology, from the core ontology.]

-Uses rdfLib python library (which depends on isodate, pyparsing, requests, rdfextras). 

-Uses logging, getopts.

-All three scripts require a Fuseki SPARQL endpoint for the Vivo you are harvesting to.

Vivo Harvester creates duplicate entities (the same individual has two URIs), because
it has no logic for merging old and new information.  What might help clean up this mess?

deduper.py
----------
<br>
<code>
Usage: deduper.py -i \<inputfile\> -k {"pmid"|"doi"}.  
</code>
<br>
<br>
For all three scripts, \<inputfile\> should be the file vivo-additions.rdf.xml created by Vivo Harvester, or an edited version of the same.  \<inputfile\> should be an absolute or relative path with the / separator, either on Windows or Unix.

You must specify pmid (PubMed Identifier) or doi (Digital Object Identifier) as the unique identifier for publications, using the -k option.  If you omit the -k option, pmid is the default.

Vivo Harvester 1.5 tends to output RDF files with a lot of duplication in the URIs, e.g. if publications are already in Vivo.  This is a healthy sign. In the case of publications, it means that Vivo Harvester found a unique identifier match, so it will create an old and a new record for that publication.  This script prefers the existing record in Vivo, in that case.  (Adequate, though not very sophisticated merging logic yet.)

The order of method calls has evolved over time.  Because the purpose is to help a human being review not only the RDF file, but the method calls themselves, the data is not piped through.  Each method call writes out an intermediate file with a prefix (pd0, ... pd4, ...) that gives its order in the workflow.  Other duplicates targeted by the script include:

<ul>
-Duplicate Journals linked to a Publication
<br>
-Duplicate Authorships linked to an Publication
<br>
-Duplicate Authors linked to an Authorship
<br>
-Duplicate Authorships (Included are the corresponding duplicates of Collaborators/Collaborations)
<br> 
-Redundant Collaboration if an Authorship already exists for a Publication
</ul>
<br>
Author or Collaborator name variation is addressed in coreffer.py, as that can't be resolved here by a unique ID.

For the future, I'd like to decouple the ordered method calls in deduper.py from the code, and define workflows.
Resolving duplicate journal to single URIs also seems overly complex, especially in the case where Deduper finds more than one match in Vivo on ISSN.

Suppose you've used Vivo Harvester to get back a dozen publications for Jane Faculty, and there is a co-author in that set identified both as John Q Public and JQ Public.  Yet, Vivo Harvester has assigned what probably is a single person two different URIs.  What to do about Vivo Harvester's "splitting" errors?  You could tune the weights and thresholds in the configuration file, but maybe we'd just like to apply a simple rule in this case.

coreffer.py
-----------
<br>
<code>
Usage: coreffer.py -i \<inputfile\> -k {"pmid"|"doi"}.
</code>
<br>
<br>
\<inputfile\> should be an absolute or relative path with the / separator, either on Windows or Unix.

You must specify pmid (PubMed Identifier) or doi (Digital Object Identifier) as the unique identifier for publications, using the -k option.  If you omit the -k option, pmid is the default.

Coreffer co-references different person name mentions (John Public, John Q Public, J Q Public) to a unique URI.  If one exists, that is the URI already in Vivo.  It queries the Fuseki SPARQL endpoint by URI for the names of known persons, so that all person URIs have names and can be co-referenced, not only the unknown novel persons. 

Coreffer uses hard-and-fast rules, and there are currently only two.  You can't really read them neatly as rules, because they are implemented in the code.  But, if you could, consider the rule "IF X has the same first initial AND same last name as Y THEN assign X and Y to one URI."  I've found that rule helpful when harvesting the publication/co-author graph for a single author.  I advise against using that rule on less bounded graphs.

Coreffer balances Vivo Harvester's out-of-the-box conservative tendency to treat most name mention differences as distinct individuals. However, because Harvester's algorithm can be tuned with parameters, and this one can't, it'd be better to use this class carefully.  It's better probably to run the script after Vivo Harvester has first scored and matched person names with its out-of-the-box parameter settings.

Here are some possibly helpful resources that may help with adding rules:
<ul>
http://www.census.gov/topics/population/genealogy/data/2000_surnames.html
http://www.pbs.org/pov/thesweetestsound/popularityindex.php
</ul>
Vivo Harvester also tends to commit "lumping" errors.  If you retrieve a set of publications for the author Jane Faculty, you may find a coauthor Brian Lee who has been assigned the URI of a person previously known as Kate Lee. Is there something we can do with the output, apart from twiddling the parameter settings of Vivo Harvester and running it again?

refsplitter.py
--------------
<br>
<code>
Usage: refsplitter.py -i \<inputfile\> -k {"pmid"|"doi"} -d "<http://myvivoschool.edu/>".
</code>
<br>
<br>
\<inputfile\> should be an absolute or relative path with the / separator, either on Windows or Unix.

Refsplitter splits references to individuals (Faculty, John or Faculty, Jane) by comparing the rdfs label for the person (either in the input model or in the vivo model) against the rdfs label for the authorship.  For example, an authorship "Authorship for Faculty, Jane" may be lumped with faculty "Faculty, John."  RefSplitter balances Harvester's liberal tendency on certain names, particularly short surnames like Lee or Li, to lump authorships with the wrong individual.  However, because Harvester's algorithm can be tuned with parameters, and this one can't, it'd be better to use this class carefully.  Try running it after Harvester has already done name matching, and after you've run coreffer.py to correct possible splitting errors.

Future work:
------------
I'd like to decouple the rules from the code in coreffer.py.  I'd like to define workflows independently of the code in deduper.py.
Refsplitter reuses a lot of the same code as Coreffer, and the two should be refactored accordingly.

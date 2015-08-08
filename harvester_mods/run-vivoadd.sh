#!/bin/bash

#Copyright (c) 2010-2011 VIVO Harvester Team. For full list of contributors, please see the AUTHORS file provided.
#All rights reserved.
#This program and the accompanying materials are made available under the terms of the new BSD license which accompanies this distribution, and is available at http://www.opensource.org/licenses/bsd-license.html

# set to the directory where the harvester was installed or unpacked
# HARVESTER_INSTALL_DIR is set to the location of the installed harvester
#	If the deb file was used to install the harvester then the
#	directory should be set to /usr/share/vivo/harvester which is the
#	current location associated with the deb installation.
#	Since it is also possible the harvester was installed by
#	uncompressing the tar.gz the setting is available to be changed
#	and should agree with the installation location
export HARVESTER_INSTALL_DIR=/usr/local/vivo/harvester
export HARVEST_NAME=ctsc
export DATE=`date +%Y-%m-%d'T'%T`

# Add harvester binaries to path for execution
# The tools within this script refer to binaries supplied within the harvester
#	Since they can be located in another directory their path should be
#	included within the classpath and the path environment variables.
export PATH=$PATH:$HARVESTER_INSTALL_DIR/bin
export CLASSPATH=$CLASSPATH:$HARVESTER_INSTALL_DIR/bin/harvester.jar:$HARVESTER_INSTALL_DIR/bin/dependency/*
export CLASSPATH=$CLASSPATH:$HARVESTER_INSTALL_DIR/build/harvester.jar:$HARVESTER_INSTALL_DIR/build/dependency/*

# Exit on first error
# The -e flag prevents the script from continuing even though a tool fails.
#	Continuing after a tool failure is undesirable since the harvested
#	data could be rendered corrupted and incompatible.
set -e

# Now that the changes have been applied to the previous harvest and the harvested data in vivo
#	agree with the previous harvest, the changes are now applied to the vivo model.
# Apply Subtractions to VIVO model
#harvester-transfer -o vivo.model.xml -r data/vivo-subtractions.rdf.xml -m
# Apply Additions to VIVO model
harvester-transfer -o vivo.model.xml -r data/vivo-additions.rdf.xml

#Output some counts
PUBS=`cat data/vivo-additions.rdf.xml | grep pmid | wc -l`
PEOPLE=`cat data/vivo-additions.rdf.xml | grep 'http://xmlns.com/foaf/0.1/Person' | wc -l`
ORGANIZATIONS=`cat data/vivo-additions.rdf.xml | grep 'http://xmlns.com/foaf/0.1/Organization' | wc -l`
AUTHORSHIPS=`cat data/vivo-additions.rdf.xml | grep "Authorship for" | wc -l`
COLLABORATIONS=`cat data/vivo-additions.rdf.xml | grep "Collaboration for" | wc -l`
JOURNALS=`cat data/vivo-additions.rdf.xml | grep 'http://purl.org/ontology/bibo/Journal' | wc -l`

echo "Imported $PUBS publications, $PEOPLE person authors or collaborators, $ORGANIZATIONS organization authors or collaborators, $AUTHORSHIPS authorships, $COLLABORATIONS collaborations, and $JOURNALS journals."
echo 'Harvest completed successfully'

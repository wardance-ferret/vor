#!/usr/bin/python

import os, strings, csv, sys, getopt

def main(argv):
        inputfile = ""
        mode=""
        print "csv2httpquery transforms a single column CSV of pubmed queries into an HTTP-safe pubMed queries.  If the original list has duplicate PMIDs, these will be deduplicated."  
        try:
                opts, args = getopt.getopt(argv,"pi:",["ifile="])
        except getopt.GetoptError:
                print 'csv2httpquery.py -i <inputfile>. Use the -p option if the CSV is a single column of PMIDs'
                sys.exit(2)
        for opt, arg in opts:
                if opt in ("-i", "--file"):
                        inputfile = arg
                if opt in ("-p"):
                        mode="pmid"
                
        PMIDs = {}
        with open(inputfile,"rb") as csvfile:
                idReader = csv.reader(csvfile)
                for row in idReader:
                        row[0].replace(" ","") 
                        if len(row[0]) == 0: 
                                continue
                        if row[0] not in PMIDs:
                                PMIDs[row[0]]=1

        

                        
        output = "[pmid] OR ".join(PMIDs.keys()) + "[pmid]"
        #replace special characters in output using %xx, except when the original string has: 
        #(1) space, which should be converted to 'plus' sign instead of %20, and 
        #(2) percent '%'
        output = strings.make_query_string_http_safe(output)
        
        #todo: parameterize the path separator (here it only works for Windows) 
        if os.name=="nt":
        	folder_separator_pat = "\\"
        else:
		folder_separator_pat = "/"

        path = inputfile.rsplit(folder_separator_pat, 1)

        
        if len(path)==2:
            outputfile = path[0] + folder_separator_pat + "query." + path[1]
        else:
            outputfile = "query."+inputfile
        
        try:
                with open(outputfile, "wb") as queryfile:
                        queryfile.write(output)
        except IOError:
                print "couldn't open "+outputfile
                
        print("All Done.")

if __name__ == "__main__":
        main(sys.argv[1:])

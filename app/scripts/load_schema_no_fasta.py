#!/usr/bin/env python3

import os
import argparse
import requests
import time
import sys
path_2_app=os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(path_2_app)
from app import app

baseURL=app.config['BASE_URL']

def main():
	parser = argparse.ArgumentParser(
        description="This program prepares a schema")
	parser.add_argument('-i', nargs='?', type=str, help='path to folder containg the schema fasta files ( alternative a list of fasta files)', required=True)
	parser.add_argument('-sp', nargs='?', type=str, help='species id', required=True)
	#~ parser.add_argument('-sc', nargs='?', type=str, help='schema id', required=True)
	parser.add_argument('-t', nargs='?', type=str, help='token', required=True)
	parser.add_argument('--sname', nargs='?', type=str, help='schema name', required=True)

	args = parser.parse_args()
	geneFiles = args.i
	species = args.sp
	token = args.t
	schema_name = args.sname
	
	
	listGenes=[]
	gene_fp = open( geneFiles, 'r')
	for gene in gene_fp:
		gene = gene.rstrip('\n')
		listGenes.append(gene)
	gene_fp.close()	
	listGenes.sort()
    
	
	print ("Processing the fastas")
    
    #build dictionary gene_name --> locus_id
	allLociList=baseURL+"species/"+species+"/loci"
    
	dictLoci={}
	r = requests.get(allLociList)
	result=r.json()
    
	result=result["Loci"]
    
	for locus in result:
		dictLoci[str(locus['name']['value'])]=str(locus['locus']['value'])
    

    
    #create new schema called wgMLST and get schema id
	params = {}
	params['name'] = schema_name
	headers = {'Authentication-Token': token}
#~ 
	url = baseURL+"species/"+species+"/schemas"
	print (url)
	r = requests.post(url, data=params,headers=headers)
	schema_url= r.text.replace('"', '').strip()
    
	print (schema_url)
    
	#~ schema_url="http://137.205.69.51/app/v1/NS/species/1/schemas/2"
    
	for gene in listGenes:

		print(gene)
		params = {}
		loci_id=(dictLoci[gene].split("/"))[-1]
		params['loci_id'] = loci_id
		headers = {'Authentication-Token': token}

		url = schema_url+"/loci"
        
		req_success=False
		sleepfactor=4
		while not req_success:
		
			r = requests.post(url, data=params,headers=headers, timeout=10)
			if r.status_code > 201:
				print("failed sending sequence, retrying in seconds "+str(sleepfactor))
				time.sleep(sleepfactor)
				sleepfactor=sleepfactor*2
			else:
				req_success=True
        
        

if __name__ == "__main__":
    main()

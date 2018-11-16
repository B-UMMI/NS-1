#!/usr/bin/env python3

from Bio.Seq import Seq
from Bio import SeqIO
from Bio.Alphabet import generic_dna

import os
import argparse

import requests
import time
import multiprocessing

import sys
path_2_app=os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(path_2_app)
from app import app

baseURL=app.config['BASE_URL']


def translateSeq(DNASeq):

    seq = DNASeq
    tableid = 11
    try:
        myseq = Seq(seq)
        protseq = Seq.translate(myseq, table=tableid, cds=True)
    except:
        try:
            seq = reverseComplement(seq)
            myseq = Seq(seq)
            protseq = Seq.translate(myseq, table=tableid, cds=True)
        except:
            try:
                seq = seq[::-1]
                myseq = Seq(seq)
                protseq = Seq.translate(myseq, table=tableid, cds=True)
            except:
                try:
                    seq = seq[::-1]
                    seq = reverseComplement(seq)
                    myseq = Seq(seq)
                    protseq = Seq.translate(myseq, table=tableid, cds=True)
                except Exception as e:
                    #~ print("translation error")
                    #~ print(e)
                    raise

    return myseq

def reverseComplement(strDNA):
    basecomplement = {'A': 'T', 'C': 'G', 'G': 'C', 'T': 'A'}
    strDNArevC = ''
    for l in strDNA:
        strDNArevC += basecomplement[l]

    return strDNArevC[::-1]


def send_post(loci_uri,sequence,token,noCDSCheck):
	
	params = {}
	params['sequence'] = sequence
	
	if not noCDSCheck:
		params['enforceCDS'] = "False"
	
	headers={'Authentication-Token': token}
	url = loci_uri+"/alleles"
		
	req_success=False
	sleepfactor=4
	while not req_success:
		try:
			r = requests.post(url, data=params,headers=headers,timeout=30)
			if r.status_code > 201:
				print(r)
				print("failed sending sequence, retrying in seconds "+str(sleepfactor))
				time.sleep(sleepfactor)
				sleepfactor=sleepfactor*2
			else:
				req_success=True
		except:
			time.sleep(sleepfactor)
			sleepfactor=sleepfactor*2
			pass
	
	req_code=int(r.status_code)
	#~ allele_url=((r.content).decode("utf-8")).replace('"', '').strip()
	
	return req_code

def send_sequence(token,sequence,loci_uri,noCDSCheck):
		
	
	req_success=False
	sleepfactor=4
	while not req_success:
	
		reqCode=send_post(loci_uri,sequence,token,noCDSCheck)
		if reqCode > 201:
			print("failed, retrying in seconds "+str(sleepfactor))
			time.sleep(sleepfactor)
			sleepfactor=sleepfactor*2
		else:
			req_success=True
	
	
	#~ if reqCode==401:
		#~ print ("Token is not valid")
	#~ elif reqCode>201:
		#~ 
		#~ try:
			#~ allele_url,reqCode=send_post(loci_uri,sequence,token)
		#~ except:
			#~ print ("Server returned code "+str(reqCode))
			#~ print(loci_uri)
	#~ else:
		#~ new_allele_id=str(int(allele_url.split("/")[-1]))
	
	return reqCode

def process_locus(gene,token,loci_url,auxBar,noCDSCheck):
	
	for allele in SeqIO.parse(gene, "fasta", generic_dna):

		sequence=(str(allele.seq)).upper()
		try:
			sequence=translateSeq(sequence)
			sequence=str(sequence)
		except:
			continue
		
		reqCode=send_sequence(token,sequence,loci_url,noCDSCheck)
	
	if gene in auxBar:
		auxlen = len(auxBar)
		index = auxBar.index(gene)
		print("[" + "=" * index + ">" + " " * (auxlen - index) + "] Sending alleles " + str(
			int((index / auxlen) * 100)) + "%")
	
	return True
	

def check_if_list_or_folder(folder_or_list):
	list_files = []
	# check if given a list of genomes paths or a folder to create schema
	try:
		f = open(folder_or_list, 'r')
		f.close()
		list_files = folder_or_list
	except IOError:

		for gene in os.listdir(folder_or_list):
			try:
				genepath = os.path.join(folder_or_list, gene)
				
				if os.path.isdir(genepath):
					continue
				
				for allele in SeqIO.parse(genepath, "fasta", generic_dna):
					break
				list_files.append(os.path.abspath(genepath))
			except Exception as e:
				print (e)
				pass

	return list_files

def main():
	parser = argparse.ArgumentParser(
		description="This program loads a schema to the nomenclature server, given the fasta files")
	parser.add_argument('-i', nargs='?', type=str, help='path to folder containg the schema fasta files ( alternative a list of fasta files)', required=True)
	parser.add_argument('-sp', nargs='?', type=str, help='species id', required=True)
	parser.add_argument('-t', nargs='?', type=str, help='token', required=True)
	parser.add_argument('--sname', nargs='?', type=str, help='schema name', required=True)
	parser.add_argument('--sprefix', nargs='?', type=str, help='loci prefix, for instance ACIBA will produce ACIBA00001.fasta', required=True)
	parser.add_argument('--cpu', nargs='?', type=int, help='number of cpu', required=False, default=1)
	parser.add_argument('--keep', help='store original fasta name too', required=False,default=False,action='store_true')
	parser.add_argument('--notCDS', help='dont enforce the sequences to be cds', required=False,default=False,action='store_false')
	parser.add_argument('--cont', help='use this flag to continue a schema upload that crashed in between', required=False,default=False,action='store_true')

	args = parser.parse_args()
	geneFiles = args.i
	species = args.sp
	token = args.t
	schema_name = args.sname
	schema_prefix = args.sprefix
	cpu2Use=args.cpu
	keepFileName=args.keep
	continue_previous_upload=args.cont
	noCDSCheck=args.notCDS
	

	#check if user provided a list of genes or a folder
	geneFiles = check_if_list_or_folder(geneFiles)
	if isinstance(geneFiles, list):
		with open("listGenes.txt", "w") as f:
			for genome in geneFiles:
				f.write(genome + "\n")
		geneFiles = "listGenes.txt"
	
	
	#create list of genes and sort it by name
	listGenes=[]
	gene_fp = open( geneFiles, 'r')
	for gene in gene_fp:
		gene = gene.rstrip('\n')
		listGenes.append(gene)
	gene_fp.close()	
	listGenes.sort()
	
	try:
		os.remove("listGenes.txt")
	except:
		pass
	
	print ("Processing the fastas")
	
	#create new schema called wgMLST and get schema id
	params = {}
	params['name'] = schema_name
	headers = {'Authentication-Token': token}

	url = baseURL+"species/"+species+"/schemas"
	r = requests.post(url, data=params,headers=headers)
	#~ print (r)
	if r.status_code ==409:
		print("schema already exists")
		return 
	elif r.status_code >201:
		print(r.status_code)
		print("something went wrong, species probably not existant")
		return 
	
	schema_url= r.text.replace('"', '').strip()
		
	#get all loci from schema
	locus_already_schema=[]
	r = requests.get(schema_url+"/loci",timeout=30)
	req_code = int(r.status_code)
	result=r.json()
	
	try:
		for locus in result:
			locus_already_schema.append(locus['locus']['value'])
	except:
		pass
	
	
	# progress load bar
	auxBar = []
	orderedkeys = sorted(listGenes)
	step = int((len(orderedkeys)) / 10) + 1
	counter = 0
	while counter < len(orderedkeys):
		auxBar.append(orderedkeys[counter])
		counter += step
	
	pool = multiprocessing.Pool(cpu2Use)
	
	#process each locus
	for gene in sorted(listGenes):
		
		url = baseURL+"species/"+species+"/loci"
		
		#check if locus is already on the species database, the program crashed before uploading all the fasta or something
		loci_url=False
		
		if continue_previous_upload:
			try:
				for allele in SeqIO.parse(gene, "fasta", generic_dna):
					
					sequence=(str(allele.seq)).upper()
					try:
						sequence=translateSeq(sequence)
						sequence=str(sequence)
					except:
						continue
					
					params = {}
					params['sequence'] = sequence
					
					#request is done for the 1st allele sequence
					sucess_send = False
					waitFactor = 4
					while not sucess_send:
						r = requests.get(url,data=params,timeout=30)
						
						if r.status_code >201:
							print("Server returned code " + str(req_code))
							print("Retrying in seconds "+str(waitFactor))
							time.sleep(waitFactor)
							waitFactor = waitFactor * 2
						else:
							sucess_send=True
						
						req_code = int(r.status_code)
						result=r.json()
					
					#if try sucessfull, the locus is already on the species database, except will continue to start adding the locus to the server
					try:
						loci_url=result[0]['locus']['value']
					except:
						pass
					break
			except:
				continue
		
		#name=os.path.basename(gene)
		#print (name)
		
		#locus is not on the species database
		if not loci_url:
			#add locus to species
			params = {}
			params['prefix'] = schema_prefix
			headers = {'Authentication-Token': token}
			if keepFileName:
				params['locus_ori_name'] = os.path.basename(gene)
			
			sucess_send = False
			waitFactor = 4
			while not sucess_send:
				r = requests.post(url, data=params,headers=headers, timeout=30)
				
				if r.status_code == 409:
					print ("Locus already exists on species")
					return
				elif r.status_code == 404:
					print ("species not found")
					return
				
				elif r.status_code >201:
					print("Server returned code " + str(req_code))
					print("Retrying in seconds "+str(waitFactor))
					time.sleep(waitFactor)
					waitFactor = waitFactor * 2
				else:
					sucess_send=True
			
			
		
		# locus is on the species, now add locus to schema
		loci_url= r.text.replace('"', '').strip()
		
		if loci_url not in locus_already_schema:
		
			new_loci_id=str(int(loci_url.split("/")[-1]))
			params = {}
			params['loci_id'] = new_loci_id
			
			

			url = schema_url+"/loci"
			
			req_success=False
			sleepfactor=4
			while not req_success:
			
				r = requests.post(url, data=params,headers=headers, timeout=30)
				if r.status_code > 201:
					print("failed, retrying in seconds "+str(sleepfactor))
					time.sleep(sleepfactor)
					sleepfactor=sleepfactor*2
				else:
					req_success=True
			
		p = pool.apply_async(process_locus, args=[gene,token,loci_url,auxBar,noCDSCheck])
	   
	pool.close()
	pool.join()

if __name__ == "__main__":
	main()

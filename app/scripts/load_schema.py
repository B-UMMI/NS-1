#!/usr/bin/env python3

from Bio.Seq import Seq
from Bio import SeqIO
from Bio.Alphabet import generic_dna
import os
import argparse
import datetime
from SPARQLWrapper import SPARQLWrapper,JSON
import requests
import time

baseURL=''
defaultgraph="<http://localhost:8890/test>"
virtuoso_user=''
virtuoso_pass=''
virtuoso_server=SPARQLWrapper('http://localhost:8890/sparql')
uniprot_server=SPARQLWrapper('http://sparql.uniprot.org/sparql')

def send_data(sparql_query):
    url = 'http://localhost:8890/DAV/test_folder/data'
    headers = {'content-type': 'application/sparql-query'}
    try:
        r = requests.post(url, data=sparql_query, headers=headers, auth=requests.auth.HTTPBasicAuth(virtuoso_user, virtuoso_pass), timeout=10)
    except Exception as e:
        time.sleep(5)
        r = requests.post(url, data=sparql_query, headers=headers, auth=requests.auth.HTTPBasicAuth(virtuoso_user, virtuoso_pass), timeout=10)
    return r

def get_data(sparql_server, sparql_query):
    sparql_server.setQuery(sparql_query)
    sparql_server.setReturnFormat(JSON)
    sparql_server.setTimeout(10)
    try:
        result = sparql_server.query().convert()
    except:
        print ("request to uniprot timed out, trying new request")
        time.sleep(5)
        result = sparql_server.query().convert()
		
    return result

def translateSeq(DNASeq, verbose):
    if verbose:
        def verboseprint(*args):
            for arg in args:
                print (arg),
            print
    else:
        verboseprint = lambda *a: None  # do-nothing function

    seq = DNASeq
    tableid = 11
    inverted = False
    try:
        myseq = Seq(seq)
        protseq = Seq.translate(myseq, table=tableid, cds=True)
    except:
        try:
            seq = reverseComplement(seq)
            myseq = Seq(seq)
            protseq = Seq.translate(myseq, table=tableid, cds=True)
            inverted = True
        except:
            try:
                seq = seq[::-1]
                myseq = Seq(seq)
                protseq = Seq.translate(myseq, table=tableid, cds=True)
                inverted = True
            except:
                try:
                    seq = seq[::-1]
                    seq = reverseComplement(seq)
                    myseq = Seq(seq)
                    protseq = Seq.translate(myseq, table=tableid, cds=True)
                    inverted = False
                except Exception as e:
                    verboseprint("translation error")
                    verboseprint(e)
                    raise

    return str(protseq)

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
                for allele in SeqIO.parse(genepath, "fasta", generic_dna):
                    break
                list_files.append(os.path.abspath(genepath))
            except Exception as e:
                print (e)
                pass

    return list_files

def main():
    parser = argparse.ArgumentParser(
        description="This program prepares a schema")
    parser.add_argument('-i', nargs='?', type=str, help='path to folder containg the schema fasta files ( alternative a list of fasta files)', required=True)
    parser.add_argument('-sp', nargs='?', type=str, help='species id', required=True)
    #~ parser.add_argument('-sc', nargs='?', type=str, help='schema id', required=True)
    parser.add_argument('-t', nargs='?', type=str, help='token', required=True)
    parser.add_argument('--sname', nargs='?', type=str, help='schema name', required=True)
    parser.add_argument('--sprefix', nargs='?', type=str, help='loci prefix', required=True)

    args = parser.parse_args()
    geneFiles = args.i
    species = args.sp
    #~ schema = args.sc
    token = args.t
    schema_name = args.sname
    schema_prefix = args.sprefix

    geneFiles = check_if_list_or_folder(geneFiles)
    if isinstance(geneFiles, list):
        with open("listGenes.txt", "w") as f:
            for genome in geneFiles:
                f.write(genome + "\n")
        geneFiles = "listGenes.txt"
	
	
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
    params['description'] = schema_name
    headers = {'Authentication-Token': token}

    url = baseURL+"species/"+species+"/schemas"
    print (url)
    r = requests.post(url, data=params,headers=headers)
    #~ print (r)
    schema_url= r.text.replace('"', '').strip()
    #~ print(schema_url)
    
    #get number of sequences
    url=baseURL+"/sequences"
    r = requests.get(url, timeout=10)
    num_sequences= int(r.text.replace('"', '').strip())
    

    print (num_sequences)
    num_of_loci=0
    for gene in listGenes:
        params = {}
        name=os.path.basename(gene)
        print (name)

        
        params = {}
        params['prefix'] = schema_prefix
        headers = {'Authentication-Token': token}

        url = baseURL+"species/"+species+"/loci"
        try:
            r = requests.post(url, data=params,headers=headers, timeout=10)
        except:
            # add to end of the list and try next one
            listGenes.append(gene)
            continue
        
        #~ print (r)
        #~ asdsa
        
        if r.status_code == 409:
            print ("already exists")
            continue
        elif r.status_code == 404:
            print ("species not found")
            continue
        
        loci_url= r.text.replace('"', '').strip()
        
        new_loci_id=str(int(loci_url.split("/")[-1]))
        params = {}
        params['loci_id'] = new_loci_id

        url = schema_url+"/loci"
        try:
            r = requests.post(url, data=params,headers=headers, timeout=10)
        except:
            time.sleep(5)
            r = requests.post(url, data=params,headers=headers, timeout=10)
			
        print (r.text)
		
        if r.status_code > 201:
            return (r.status_code)
			
        #~ asdasd
		#~ allele_url=((r.content).decode("utf-8")).replace('"', '').strip()

        #~ new_allele_id=str(int(allele_url.split("/")[-1]))
        
                
        listRdfs2load=[]            
        rdf_header='PREFIX typon:   <http://purl.phyloviz.net/ontology/typon#> \nINSERT DATA IN GRAPH '+defaultgraph+' {\n'
        rdf_2_ins=rdf_header
        num_alleles=0
        for allele in SeqIO.parse(gene, "fasta", generic_dna):
            params = {}
            sequence=str(allele.seq)
            
            
            #translate and check if existant on uniprot

            new_seq_url=baseURL+"sequences/"+str(num_sequences+1)
            new_allele_url=loci_url+"/alleles/"+str(num_alleles+1)
            rdf_2_ins+='<'+new_seq_url+'> a typon:Sequence; typon:nucleotideSequence "'+sequence+'"^^xsd:string. <'+new_allele_url+'> a typon:Allele; typon:isOfLocus <'+loci_url+'>; typon:dateEntered "'+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+'"^^xsd:dateTime; typon:id "'+str(num_alleles+1)+'"^^xsd:integer ; typon:hasSequence <'+new_seq_url+'>. <'+loci_url+'> typon:hasDefinedAllele <'+new_allele_url+'>.\n'
            num_sequences+=1
            num_alleles+=1
            
            result=''
            try:
                proteinSequence=translateSeq(sequence,False)
                #~ query='PREFIX rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>  PREFIX up: <http://purl.uniprot.org/core/> select ?seq where { ?b a up:Simple_Sequence; rdf:value "'+proteinSequence+'". ?seq up:sequence ?b.}'
                query='PREFIX rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>  PREFIX up: <http://purl.uniprot.org/core/> PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> select ?seq ?label ?sname where { ?b a up:Simple_Sequence; rdf:value "'+proteinSequence+'". ?seq up:sequence ?b. OPTIONAL {?seq rdfs:label ?label.} OPTIONAL {?seq up:submittedName ?rname2. ?rname2 up:fullName ?sname.}}LIMIT 20'
                
                result = get_data(uniprot_server, query)
                url=result["results"]["bindings"][0]['seq']['value']
                rdf_2_ins+='<'+new_seq_url+'> typon:hasUniprotSequence <'+url+'>.'
                try:
                    url2=result["results"]["bindings"][0]['label']['value']
                    rdf_2_ins+='<'+new_seq_url+'> typon:hasUniprotLabel "'+url2+'"^^xsd:string.'
                except:
                    print ("no label associated")
                    pass
                try:
                    url2=result["results"]["bindings"][0]['sname']['value']
                    rdf_2_ins+='<'+new_seq_url+'> typon:hasUniprotSName "'+url2+'"^^xsd:string.'
                except:
                    print ("no submitted name associated")
                    pass
                    
            except Exception as e:
                print ("sequence is not in uniprot")
                pass
            
             #length of an rdf of a 8.8Mb fasta file is 9723207 and uploads ok
            if len(rdf_2_ins)> 9000000:
                rdf_2_ins+="\n}"
                listRdfs2load.append(rdf_2_ins)
                rdf_2_ins=rdf_header
        
        rdf_2_ins+="\n}"
        listRdfs2load.append(rdf_2_ins)
                    
        for rdf2send in listRdfs2load:
            #~ print (rdf_2_ins)
            send_data(rdf2send)

        num_of_loci+=1
    
    #update number of sequences
    try:
        url=baseURL+"/sequences"
        r = requests.get(url, timeout=10)
        result=r.json()
    except:
        time.sleep(5)
        url=baseURL+"/sequences"
        r = requests.get(url, timeout=10)
        result=r.json()  

if __name__ == "__main__":
    main()

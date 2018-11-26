import datetime
from app import db, app, virtuoso_server,uniprot_server, celery, dbpedia_server
from flask import abort,g,request, Response, stream_with_context, send_from_directory
from flask_restful import Resource, reqparse, marshal, fields
from app.models.models import User, Role, Auxiliar
from flask_security import Security, SQLAlchemyUserDatastore, auth_token_required
from SPARQLWrapper import JSON
from app.scripts.AuxFunctions import translateSeq
import requests,json
import sys
import os
import hashlib
import time
import urllib.request

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

baseURL=app.config['BASE_URL']
defaultgraph=app.config['DEFAULTHGRAPH']
virtuoso_user=app.config['VIRTUOSO_USER']
virtuoso_pass=app.config['VIRTUOSO_PASS']
url_send_local_virtuoso=app.config['URL_SEND_LOCAL_VIRTUOSO']

#### ---- AUX FUNCTIONS ---- ###

def get_read_run_info_ena(ena_id):

	url = 'http://www.ebi.ac.uk/ena/data/warehouse/filereport?accession=' + ena_id + 'AAA&result=read_run'

	read_run_info = False
	try:
		with urllib.request.urlopen(url) as url:
			read_run_info = url.read().splitlines()
			if len(read_run_info) <= 1:
				read_run_info = False
			else:
				read_run_info=True
	except Exception as error:
		print(error)
	
	return read_run_info

def get_read_run_info_sra(SRA_id):
	
	url = 'https://trace.ncbi.nlm.nih.gov/Traces/sra/sra.cgi?save=efetch&db=sra&rettype=runinfo&term=%20'+SRA_id
	
	read_run_info = False
	try:
		with urllib.request.urlopen(url,timeout = 2) as url:
			status_code=url.getcode()
			headers=url.info()
			
			#if the SRA_id is not found ncbi is very generous and may give a tsunami of info, limit that to 30k bytes if that's the case
			#we wont consider that ID
			read_run_info = url.read(30000)
			try:
				read_run_info=read_run_info.splitlines()
			except:
				return read_run_info

			
			#check if the ERR is on the second element of the list returned
			#thanks NCBI for returning wtv if the SRA_id is "LALA" or whatever I put there
			#very cranky bypass of this, change in the future
			
			if SRA_id in read_run_info[1].decode("utf-8") :
				read_run_info=True
			else:
				read_run_info=False
			
	except Exception as error:
		print(error)

	return read_run_info

#dirty way to check the disease URI is real, no pun intended :)))
def check_disease_resource(URI):
	try:
		
		print('http://www.ontobee.org/ontology/rdf/DOID?iri='+URI)
		r = requests.get('http://www.ontobee.org/ontology/rdf/DOID?iri='+URI)
		print(r.status_code)
		diseaseFound=False
		if int(r.status_code)<202:
			diseaseFound=True
	except Exception as e:
		print(e)
		diseaseFound=False
	return diseaseFound

def sanitize_input(mystring):
	print ("sanitizing")
	mystring=mystring.replace("'", "")
	mystring=mystring.encode('ascii', 'ignore')
	mystring=mystring.decode("utf-8")
	mystring=mystring.replace("\\", "") 
	return mystring

def send_data(sparql_query):
	url = url_send_local_virtuoso
	headers = {'content-type': 'application/sparql-query'}
	r = requests.post(url, data=sparql_query, headers=headers, auth=requests.auth.HTTPBasicAuth(virtuoso_user, virtuoso_pass))
		
	#sometimes virtuoso returns 405 God knows why ¯\_(ツ)_/¯ retry in 2 sec
	if r.status_code >201:
		time.sleep(2)
		r = requests.post(url, data=sparql_query, headers=headers, auth=requests.auth.HTTPBasicAuth(virtuoso_user, virtuoso_pass))
    
	return r


def get_data(server,sparql_query):
	try:
		server.setQuery(sparql_query)
		server.setReturnFormat(JSON)
		server.setTimeout(20)
		result = server.query().convert()
	except Exception as e:
		time.sleep(5)
		try:
			server.setQuery(sparql_query)
			server.setReturnFormat(JSON)
			server.setTimeout(20)
			result = server.query().convert()
		except Exception as e:
			result=e
		
	return result

#query when sequence is too large needs to be a POST
def send_big_query(server,sparql_query):
	try:
		server.setQuery(sparql_query)
		server.setReturnFormat(JSON)
		server.method ="POST"
		result = server.query().convert()
	except Exception as e:
		result=e
		
	return result

#### ---- CELERY QUEUES ---- ###

#queue to add alleles
@celery.task(time_limit=20)
def add_allele(new_locus_url,spec_id,loci_id,new_user_url,new_seq_url,isNewSeq,add2send2graph,sequence):
	
	query='SELECT ?alleles WHERE { ?alleles typon:isOfLocus <'+new_locus_url+'>; typon:hasSequence ?seq. ?seq a typon:Sequence; typon:nucleotideSequence "'+sequence+'"^^xsd:string.}'
		
	if len(sequence) > 9000:
		result=send_big_query(virtuoso_server,query)
	else:
		result = get_data(virtuoso_server,query)
	
	#if sequence exists return the allele uri, if not create new sequence
	try :
		new_allele_url = result["results"]["bindings"][0]['alleles']['value']
		return new_allele_url, 200
	
	except:
		pass
	
	#get number of alleles for locus
	result = get_data(virtuoso_server,'select (COUNT(?alleles) as ?count) where { ?alleles typon:isOfLocus <'+new_locus_url+'>.}')
	number_alleles_loci=int(result["results"]["bindings"][0]['count']['value'])
	new_allele_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(loci_id)+"/alleles/"+str(number_alleles_loci+1)
	
	#add allele to virtuoso
	if isNewSeq:
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_seq_url+'> a typon:Sequence '+add2send2graph+' ; typon:nucleotideSequence "'+sequence+'"^^xsd:string.<'+new_allele_url+'> a typon:Allele; typon:sentBy  <'+new_user_url+'> ;typon:isOfLocus <'+new_locus_url+'>; typon:dateEntered "'+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+'"^^xsd:dateTime; typon:id "'+str(number_alleles_loci+1)+'"^^xsd:integer ; typon:hasSequence <'+new_seq_url+'>. <'+new_locus_url+'> typon:hasDefinedAllele <'+new_allele_url+'>.}')
	
	#add new link from allele to sequence
	else:
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_allele_url+'> a typon:Allele; typon:sentBy  <'+new_user_url+'> ;typon:isOfLocus <'+new_locus_url+'>; typon:dateEntered "'+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+'"^^xsd:dateTime; typon:id "'+str(number_alleles_loci+1)+'"^^xsd:integer ; typon:hasSequence <'+new_seq_url+'>. <'+new_locus_url+'> typon:hasDefinedAllele <'+new_allele_url+'>.}')
	
	if result.status_code > 201 :
		return "Sum Thing Wong creating sequence 1", result.status_code
	else:
		return new_allele_url, result.status_code

	
#queue to add locus do schema
@celery.task(time_limit=20)
def add_locus_schema(new_schema_url,new_locus_url):	
	
	#get number of loci on schema and build the uri based on that number+1
	result = get_data(virtuoso_server,'select (COUNT(?parts) as ?count) where { <'+new_schema_url+'> typon:hasSchemaPart ?parts. }')
	number_schema_parts=int(result["results"]["bindings"][0]['count']['value'])
	
	new_schema_part_url=new_schema_url+"/loci/"+str(number_schema_parts+1)
	
	#send data to graph
	result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_schema_part_url+'> a typon:SchemaPart ; typon:index "'+str(number_schema_parts+1)+'"^^xsd:int ; typon:hasLocus <'+new_locus_url+'>.<'+new_schema_url+'> typon:hasSchemaPart <'+new_schema_part_url+'>.}')

	if result.status_code == 201 :
		return "Locus sucessfully added to schema", 201		
	else:
		return "Sum Thing Wong", result.status_code


#queue to add profile		
@celery.task(time_limit=20)
def add_profile(rdf_2_ins):
	
	result=send_data(rdf_2_ins)
	
	#try to send it a few times if error
	try:
		if result.status_code > 201 :
			time.sleep(2)
			result=send_data(rdf_2_ins)
			if result.status_code > 201 :
				print (result)
				return "Sum Thing Wong creating profile", result.status_code
			else:
				return True, result.status_code
				print (result)
		else:
			return True, result.status_code
	
	except Exception as e:
		try:
			if result.status_code > 201 :
				time.sleep(2)
				result=send_data(rdf_2_ins)
				if result.status_code > 201 :
					print (result)
					return "Sum Thing Wong creating profile", result.status_code
				else:
					return True, result.status_code
					print (result)
			else:
				return True, result.status_code
		except Exception as e:
			
			return e, 400
		return e, 400
	


#### ---- RESOURCES ---- ###

#@app.route('/NS/stats') 
class Statstypon(Resource):
	#~ @auth_token_required
	def get(self):
		
			
		#count stuff from on virtuoso
		try:
			result = get_data(virtuoso_server,'select * where { {select (COUNT(?seq) as ?sequences) where {?seq a typon:Sequence }} { select (COUNT(?spec) as ?species) where {?spec a <http://purl.uniprot.org/core/Taxon>}} { select (COUNT(?loc) as ?loci) where {?loc a typon:Locus }} { select (COUNT(?user) as ?users) where {?user a <http://xmlns.com/foaf/0.1/Agent>. }} { select (COUNT(?schema) as ?schemas) where {?schema a typon:Schema. }} { select (COUNT(?isol) as ?isolates) where {?isol a typon:Isolate. }} { select (COUNT(?all) as ?alleles) where {?all a typon:Allele. }}}')

			return (result["results"]["bindings"]),200
		except:
			return "Sum thing wong",result.status_code

class NS(Resource):
	#~ @auth_token_required
	def get(self):
		helloStr=""
		with open("about.nfo","r") as myfile:
			helloStr=myfile.read()
		
		#count number of sequences on virtuoso
		result = get_data(virtuoso_server,'select (COUNT(?seq) as ?count) where {?seq a typon:Sequence }')
		number_sequences_vir=int(result["results"]["bindings"][0]['count']['value'])
		

		#count number of species on virtuoso
		result = get_data(virtuoso_server,'select (COUNT(?spec) as ?count) where {?spec a <http://purl.uniprot.org/core/Taxon> }')
		number_species_vir=int(result["results"]["bindings"][0]['count']['value'])
		
		#count number of loci on virtuoso
		result = get_data(virtuoso_server,'select (COUNT(?spec) as ?count) where {?spec a typon:Locus }')
		number_loci_vir=int(result["results"]["bindings"][0]['count']['value'])
		
		#count number of users on virtuoso
		result = get_data(virtuoso_server,'select (COUNT(?user) as ?count) where {?user a <http://xmlns.com/foaf/0.1/Agent>. }')
		number_users_vir=int(result["results"]["bindings"][0]['count']['value'])
		
		helloStr+=" AUTHORS: Mickael Silva, António Paulo \n\n EMAIL: mickaelsilva@medicina.ulisboa.pt"
		
		helloStr+="\n\n DATE: "+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')) +"\n\n NUMBER OF SEQUENCES: "+ str(number_sequences_vir)+"\n\n NUMBER OF LOCI: "+ str(number_loci_vir)+"\n\n NUMBER OF SPECIES: "+ str(number_species_vir)+"\n\n NUMBER OF USERS: "+ str(number_users_vir)


		return Response(helloStr, mimetype='text/plain')



# curl -i  http://localhost:5000/NS/species/<int:spec_id>/profiles
class profile(Resource):
	
	@auth_token_required
	def post(self, spec_id):

		
		content = request.json
		
		if not content:
			return "Provide json"
		
		profileDict=content['profile']
		headers=content['headers']
		
		#get user id based on the token
		userid=g.identity.user.id
		new_user_url=baseURL+"users/"+str(userid)
		#~ new_user_url=baseURL+"users/"+str(1)
    
		new_spec_url=baseURL+"species/"+str(spec_id)
		
		dictgenes={}
		
		#get all locus from the species and their respective name, to compare to the name of the locus from the profile the user sent
		result = get_data(virtuoso_server,'select (str(?name) as ?name) ?locus where {?locus a typon:Locus; typon:isOfTaxon <'+new_spec_url+'>; typon:name ?name. }')
		for gene in result["results"]["bindings"]:
			dictgenes[str(gene['name']['value'])]=str(gene['locus']['value'])

		#result = get_data(virtuoso_server,'select (COUNT(?isol) as ?count) where {?isol a typon:Isolate }')
		#num_isolates=int(result["results"]["bindings"][0]['count']['value'])
            		
		
		for genomeName in profileDict.keys():
		
			#~ print (genomeName)
			#~ isolateUri=False
			#~ #check if genome is already present
			#~ result=[]
			#~ result = get_data(virtuoso_server,'ASK where { ?isolate a typon:Isolate; typon:name "'+genomeName+'"^^xsd:string.}')
			#~ genesAlreadyAttr=[]
			#~ 
			#~ try:
				#~ result['boolean']
			#~ except:
				#~ return "Profile not uploaded,try again " , 400
			#~ 
			#~ if result['boolean']:
				#~ 
				#~ #genome is present check if belongs to submitter
				#~ result=[]
				#~ result = get_data(virtuoso_server,'ASK where { ?isolate a typon:Isolate; typon:name "'+genomeName+'"^^xsd:string; typon:sentBy <'+new_user_url+'>.}')
				#~ 
				#~ 
				#~ try:
					#~ result['boolean']
				#~ except:
					#~ return "Profile not uploaded,try again " , 400
				#~ 
				#~ #genome is present and belongs to user, get alleles already attributed
				#~ if result['boolean']:
					#~ result=[]
					#~ result = get_data(virtuoso_server,'select ?locus ?isolate where { ?isolate a typon:Isolate; typon:name "'+genomeName+'"^^xsd:string; typon:hasAllele ?allele. ?allele typon:isOfLocus ?locus}')
					#~ 
					#~ for gene in result["results"]["bindings"]:
						#~ genesAlreadyAttr.append(str(gene['locus']['value']))
						#~ isolateUri=str(gene['isolate']['value'])
				#~ 
				#~ #genome is present and belongs to different user
				#~ else:
					#~ return "Genome "+genomeName+" already exists and belong to a different user", 403
		
			
			#create the new isolate id for the uri
			nameWdata2hash=genomeName+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))
			new_isolate_id=hashlib.sha256(nameWdata2hash.encode('utf-8')).hexdigest()
			
			rdf_2_ins='PREFIX typon: <http://purl.phyloviz.net/ontology/typon#> \nINSERT DATA IN GRAPH '+defaultgraph+' {\n'
			
			#~ if not isolateUri==False:
				#~ rdf_2_ins+='<'+isolateUri+'>'
			#~ else:
			isolateUri=new_spec_url+'/isolates/'+str(new_isolate_id)
			rdf_2_ins+='<'+isolateUri+'> a typon:Isolate;\ntypon:name "'+genomeName+'"^^xsd:string; typon:sentBy <'+new_user_url+'>; typon:dateEntered "'+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+'"^^xsd:dateTime; typon:isFromTaxon <'+new_spec_url+'>;'
			i=0
			hasAlleles=0
			
			#build the rdf with all alleles
			while i<len(profileDict[genomeName]):
				gene= headers[i+1]
				
				#get the allele id
				try:
					allele= int(profileDict[genomeName][i])
					
				except:
					i+=1
					continue
					#~ try:
						#~ allele= int(profileDict[genomeName][i].replace('*',''))
						#~ hasAlleles+=1
					#~ except:
						
					#~ print row[i]

				#get the locus uri
				try:
					loci_uri= dictgenes[headers[i+1]]
				except:
					#~ print ("locus is not on db")
					return str(headers[i+1])+" locus was not found, profile not uploaded",404
									
				#check if allele exists
				allele_uri=loci_uri+"/alleles/"+str(allele)
				result = get_data(virtuoso_server,'ASK where { <'+loci_uri+'> a typon:Locus; typon:hasDefinedAllele <'+allele_uri+'> }')
				if result['boolean']:
					
					rdf_2_ins+= '\ntypon:hasAllele <'+allele_uri+'>;'
					hasAlleles+=1
					
				i+=1
			
			#if the genome has alleles, send the rdf
			if hasAlleles > 0:

				#remove last semicolon from rdf and close the brackets
				rdf_2_ins=rdf_2_ins[:-1]
				
				rdf_2_ins+=".}"
				
				
				#add to the queue to send the profile
				task = add_profile.apply(args=[rdf_2_ins])
					
				process_result=task.result
				
				process_ran=task.ready()
				process_sucess=task.status
				
				if process_ran and process_sucess == "SUCCESS":
					pass
				else:
					return "status: "+process_sucess+" run:"+process_ran, 400
				
				process_result=task.result
				print(process_result)
				#new_allele_url=process_result[0]
				process_result_status_code=int(process_result[-1])
								
				print (genomeName, str(process_result_status_code))
				
				if process_result_status_code >201:
					return "Profile not uploaded,try again " , process_result_status_code
				else:
					return "Profile successfully uploaded at "+isolateUri , process_result_status_code
				
			else:
				#num_isolates-=1    
				return "Profile not uploaded, no alleles to send at "+isolateUri, 200
		
		
		return



#@app.route('/NS/species') 
class SpeciesListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()
		self.reqparse.add_argument('name', dest= 'name',
								   required=True,
								   type=str,
								   help='No valid name provided for species')

	# curl -i  http://localhost:5000/NS/species
	def get(self):

		#get all species
		print("alala")
		result = get_data(virtuoso_server,'select ?species ?name where { ?species owl:sameAs ?species2; a <http://purl.uniprot.org/core/Taxon>; typon:name ?name. }')
		print(result)
		return (result["results"]["bindings"])

	# curl -i  http://localhost:5000/NS/species -d 'name=bacteria'
	@auth_token_required
	def post(self):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['name'])
		
		#only admin can do this
		#~ userid=1
		#get user id, if >1 means is not the first user and cant continue the request
		userid=g.identity.user.id
		try:
			new_user_url=baseURL+"users/"+str(userid)
			result = get_data(virtuoso_server,'ASK where { <'+new_user_url+'> a <http://xmlns.com/foaf/0.1/Agent>; typon:Role "Admin"^^xsd:string}')
			if not result['boolean']:
				return "not authorized, admin only", 405
		except:
			return "not authorized, admin only", 405

		
		#get number of taxon already on the graph
		result = get_data(virtuoso_server,'select (COUNT(?taxon) as ?count) where { ?taxon a <http://purl.uniprot.org/core/Taxon> }')
		number_taxon=int(result["results"]["bindings"][0]['count']['value'])
		
		#get the taxon id from uniprot, if not found return 404
		query='PREFIX up:<http://purl.uniprot.org/core/> PREFIX taxon:<http://purl.uniprot.org/taxonomy/> PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> SELECT ?taxon FROM  <http://sparql.uniprot.org/taxonomy> WHERE{	?taxon a up:Taxon; rdfs:subClassOf taxon:2; up:scientificName "'+args['name']+'" .}'
		print ("searching on uniprot..")
		
		result2 = get_data(uniprot_server,query)
		try:
			url=result2["results"]["bindings"][0]['taxon']['value']
		except:
			return "species name not found on uniprot, search on http://www.uniprot.org/taxonomy/", 404 
		
		# check if species already exists locally
		result = get_data(virtuoso_server,'ASK where { ?species owl:sameAs <'+url+'>}')
		if result['boolean']:
			return "Species already exists", 409
		
		#species exists on uniprot, everything ok to create new species
		new_spec_url=baseURL+"species/"+str(number_taxon+1)
		data2send='INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_spec_url+'> owl:sameAs <'+url+'>; typon:name "'+args['name']+'"^^xsd:string ; a <http://purl.uniprot.org/core/Taxon>.}'
		
		result = send_data(data2send)

		#print (result)
		if result.status_code == 201 :
			return "Species created", 201		
		else:
			return "Sum Thing Wong", result.status_code

#@app.route('/NS/species/<int:spec_id>') 
class SpeciesAPItypon(Resource):

	def get(self, spec_id):
		url=baseURL+"species/"+str(spec_id)
		#result = get_data(virtuoso_server,'select ?species ?name where { <'+url+'> owl:sameAs ?species; typon:name ?name. } ')
		
		#get species name and its schemas
		result = get_data(virtuoso_server,'select ?species ?name ?schemas ?schemaName where { {<'+url+'> owl:sameAs ?species; typon:name ?name.} UNION { ?schemas typon:isFromTaxon <'+url+'>; a typon:Schema; typon:schemaName ?schemaName. FILTER NOT EXISTS { ?schemas typon:deprecated  "true"^^xsd:boolean }}}')
		return (result["results"]["bindings"])


#@app.route('/NS/species/<int:spec_id>/schemas') 
class SchemaListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('name', dest= 'name',
								   required=True,
								   type=str,
								   help='No valid name provided for schema')
        

	# curl -i  http://localhost:5000/NS/species/bacteria/schemas
	def get(self, spec_id):
		
		species_url=baseURL+"species/"+str(spec_id)	
		result = get_data(virtuoso_server,'select ?schemas ?name where { ?schemas a typon:Schema; typon:isFromTaxon <'+species_url+'>; typon:schemaName ?name. FILTER NOT EXISTS { ?schemas typon:deprecated  "true"^^xsd:boolean }}')
		try:
			return (result["results"]["bindings"])
		except:
			return []

	# curl -i http://localhost:5000/NS/species/1/schemas -d 'description=interesting'
	@auth_token_required
	def post(self, spec_id):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['name'])
		
		try:
			args['name']
		except:
			return "No valid name provided", 404
		
		# check if species exists
		species_url=baseURL+"species/"+str(spec_id)
		result = get_data(virtuoso_server,'ASK where { <'+species_url+'> a <http://purl.uniprot.org/core/Taxon>}')
		if not result['boolean']:
			return "Species doesnt exist", 404
		
		# check if a schema already exists with this description for this species
		species_url=baseURL+"species/"+str(spec_id)
		result = get_data(virtuoso_server,'ASK where { ?schema a typon:Schema; typon:isFromTaxon <'+species_url+'>; typon:schemaName "'+args['name']+'"^^xsd:string .}')
		if result['boolean']:
			
			result = get_data(virtuoso_server,'select ?schema where {?schema a typon:Schema; typon:isFromTaxon <'+species_url+'>; typon:schemaName "'+args['name']+'"^^xsd:string .}')
			schema_url = result["results"]["bindings"][0]['schema']['value']
			
			return "schema with that description already exists "+schema_url, 409
		
		#only users with role admin can do this
		userid=g.identity.user.id
		try:
			new_user_url=baseURL+"users/"+str(userid)
			result = get_data(virtuoso_server,'ASK where { <'+new_user_url+'> a <http://xmlns.com/foaf/0.1/Agent>; typon:Role "Admin"^^xsd:string}')
			if not result['boolean']:
				return "not authorized, admin only", 405
		except:
			return "not authorized, admin only", 405
		
		#only user 1 can add schemas, change at your discretion
		#~ userid=g.identity.user.id
		#~ if userid>1:
			#~ return "not authorized, admin only", 405
			
		new_user_url=baseURL+"users/"+str(userid)
		
		# count number of schemas on the server for the uri build and send data to server
		result = get_data(virtuoso_server,'select (COUNT(?schemas) as ?count) where { ?schemas a typon:Schema;typon:isFromTaxon <'+species_url+'>. }')
		number_schemas=int(result["results"]["bindings"][0]['count']['value'])
		
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(number_schemas+1)
		
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_schema_url+'> a typon:Schema; typon:isFromTaxon <'+species_url+'>; typon:administratedBy <'+new_user_url+'>; typon:schemaName "'+args['name']+'"^^xsd:string .}')
		if result.status_code == 201 :
			return new_schema_url, 201		
		else:
			return "Sum Thing Wong", result.status_code

#@app.route('/NS/species/<int:spec_id>/schema/<int:id>') 
class SchemaAPItypon(Resource):

	
	def get(self, spec_id,id ):
		
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		
		result = get_data(virtuoso_server,'ASK where {<'+new_schema_url+'>typon:deprecated "true"^^xsd:boolean.}')
		if result['boolean']:
			return "Schema is now deprecated",200
		
		result = get_data(virtuoso_server,'select ?description (COUNT(?part) as ?number_loci) where { <'+new_schema_url+'> typon:schemaName ?description; typon:hasSchemaPart ?part. }')
		try:
			finalresult=result["results"]["bindings"]
			finalresult[0]['list_loci']={'value':new_schema_url+'/loci'}
			return (finalresult)
		except:
			return []
	
	#it doesnt delete, it just adds an attribute typon:deprecated  "true"^^xsd:boolean to that part of the schema, the locus is just "removed" for the specific schema!!!11
	@auth_token_required
	def delete(self, spec_id, id):

		
		#only admin can do this
		
		userid=g.identity.user.id
		try:
			new_user_url=baseURL+"users/"+str(userid)
			result = get_data(virtuoso_server,'ASK where { <'+new_user_url+'> a <http://xmlns.com/foaf/0.1/Agent>; typon:Role "Admin"^^xsd:string}')
			if not result['boolean']:
				return "not authorized, admin only", 405
		except:
			return "not authorized, admin only", 405
		
		#~ try:
			#~ userid=g.identity.user.id
		#~ except:
			#~ return "not authorized, admin only", 405
		#~ if userid>1:
			#~ return "not authorized, admin only", 405
		#~ 
		#~ userid=1
		
		new_user_url=baseURL+"users/"+str(userid)
		
		#check if schema exists
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'ASK where { <'+new_schema_url+'> a typon:Schema; typon:administratedBy <'+new_user_url+'>.}')
		if not result['boolean']:
			return "Schema not found or schema is not yours", 404
		
		
		#add a tripple to the link between the schema and the locus implying that the locus is deprecated for that schema
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_schema_url+'> typon:deprecated "true"^^xsd:boolean.}')
		
		if result.status_code == 201 :
			return "Locus sucessfully removed from schema", 201	
		else:
			return "Sum Thing Wong", result.status_code

#@app.route('/NS/species/<int:spec_id>/schema/<int:id>/compressed') 
class SchemaZipAPItypon(Resource):

	
	def get(self, spec_id,id ):
		
		#check if schema exists
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'select ?description (COUNT(?part) as ?number_loci) where { <'+new_schema_url+'> typon:schemaName ?description; typon:hasSchemaPart ?part. FILTER NOT EXISTS { <'+new_schema_url+'> typon:deprecated  "true"^^xsd:boolean }}')
		
		try:
			schema_name=result["results"]["bindings"][0]["description"]["value"]
		except:
			return "schema not found",404
		
		
		#build the dowload path
		down_folder=os.path.join(app.config['DOWNLOAD_FOLDER'],str(spec_id),str(id))
		
		zippath=os.path.join(down_folder,"schema_"+schema_name+".zip")
		
		if os.path.isfile(zippath):
			return send_from_directory(down_folder, "schema_"+schema_name+".zip", as_attachment=True)
		else:
			return "File doesn't exist", 404


#@app.route('/NS/species/<int:spec_id>/schema/<int:id>/loci')
class SchemaLociAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()
		
		self.reqparse.add_argument('loci_id', dest= 'loci_id',
								   required=False,
								   type=int,
								   help='No valid id provided for loci')
		#~ super(SchemaLociAPI, self).__init__()
		self.reqparse.add_argument('date', dest= 'date',
								   required=False,
								   type=str,
								   help='provide a date in the format YYYY-MM-DDTHH:MM:SS to get the alleles that were uploaded after that defined date')

	def get(self, spec_id,id ):
		
		# check if date was provided as parameter
		args = self.reqparse.parse_args(strict=True)
		dateAux=False
		try:
			dateAux=args['date']
		except:
			pass
		

		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		
		#check if schema exists or deprecated
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'ASK where { <'+new_schema_url+'> a typon:Schema; typon:deprecated  "true"^^xsd:boolean }')
		
		if result['boolean']:
			return "Schema not found or deprecated", 404
		
		# if date is provided the request returns the alleles that were added after that specific date for all loci
		# else the request returns the list of loci
		# a correct request returns also the server date at which the request was done
		if dateAux:
			#print('select ?locus_name ?allele_id ?sequence where { { select ?locus_name ?allele_id ?sequence where {<'+new_schema_url+'> typon:hasSchemaPart ?part. ?part typon:hasLocus ?locus . ?alleles typon:isOfLocus ?locus ; typon:dateEntered ?date; typon:hasSequence ?sequence; typon:id ?allele_id. ?locus typon:name ?locus_name. FILTER ( ?date >= "'+dateAux+'"^^xsd:dateTime ). FILTER NOT EXISTS { ?part typon:deprecated  "true"^^xsd:boolean }.}order by ASC(?date)}} LIMIT 25000')
			
			#query all alleles for the loci of the schema since a specific date, sorted from oldest to newest (limit of max 50k records)
			result = get_data(virtuoso_server,'select ?locus_name ?allele_id ?sequence where { { select ?locus_name ?allele_id ?sequence where {<'+new_schema_url+'> typon:hasSchemaPart ?part. ?part typon:hasLocus ?locus . ?alleles typon:isOfLocus ?locus ; typon:dateEntered ?date; typon:hasSequence ?sequence; typon:id ?allele_id. ?locus typon:name ?locus_name. FILTER ( ?date > "'+dateAux+'"^^xsd:dateTime ). FILTER NOT EXISTS { ?part typon:deprecated  "true"^^xsd:boolean }.}order by ASC(?date)}} LIMIT 50000')
			if len(result["results"]["bindings"])<1:
				#~ return {"newAlleles":[{'date':str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))}],}
				def generate():
					yield '{"newAlleles": []}'
				r = Response(stream_with_context(generate()), content_type='application/json')
				r.headers.set('Server-Date',str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')))
				return r
			
			#get the latest allele date (the newest)
			latestAllele=(result["results"]["bindings"])[-1]
			geneFasta=latestAllele['locus_name']['value']
			alleleid=latestAllele['allele_id']['value']
			result2 = get_data(virtuoso_server,' select ?date where { ?locus typon:name "'+geneFasta+'"^^<http://www.w3.org/2001/XMLSchema#string>. ?alleles typon:isOfLocus ?locus ; typon:dateEntered ?date; typon:id '+alleleid+'. }')
			
			latestDatetime=(result2["results"]["bindings"])[0]['date']['value']
			
			number_of_alleles=len(result["results"]["bindings"])
			try:
				
				def generate():
					yield '{"newAlleles": ['
					#~ for item in result["results"]["bindings"]:
						#~ yield json.dumps(item)+','
					#~ yield json.dumps({'date':latestDatetime})+']}'
				
					try:
						prev_item=result["results"]["bindings"].pop(0)
					except:
						yield ']}'
					for item in result["results"]["bindings"]:
						yield json.dumps(prev_item)+','
						prev_item = item
					yield json.dumps(prev_item)+']}'
				
				r = Response(stream_with_context(generate()), content_type='application/json')
				r.headers.set('Last-Allele',latestDatetime)
				if number_of_alleles>49999:
					r.headers.set('All-Alleles-Returned',True)
				else:
					r.headers.set('All-Alleles-Returned',False)
				return r
									
			except :
				def generate():
					yield '{"newAlleles": []}'
				r = Response(stream_with_context(generate()), content_type='application/json')
				r.headers.set('Server-Date',str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')))
				return r
		
		#if no date provided, query for all loci for the schema
		else:
			result = get_data(virtuoso_server,'select ?locus (str(?name) as ?name) where { <'+new_schema_url+'> typon:hasSchemaPart ?part. ?part typon:hasLocus ?locus.?locus typon:name ?name. FILTER NOT EXISTS { ?part typon:deprecated  "true"^^xsd:boolean } }order by (?name) ')
			
			#return all loci in stream mode
			try:
				
				latestDatetime=str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))
				def generate():
					yield '{"Loci": ['
					
					try:
						prev_item=result["results"]["bindings"].pop(0)
					except:
						yield ']}'
					for item in result["results"]["bindings"]:
						yield json.dumps(prev_item)+','
						prev_item = item
					yield json.dumps(prev_item)+']}'
				
				r = Response(stream_with_context(generate()), content_type='application/json')
				r.headers.set('Server-Date',latestDatetime)
				return r
									
			except :
				return [],400
		
	
	@auth_token_required
	def post(self, spec_id, id):
		
		args = self.reqparse.parse_args(strict=True)
		
		try:
			args['loci_id']
		except:
			return "No valid id provided for loci: loci_id=<int>", 404
		
		userid=g.identity.user.id
		new_user_url=baseURL+"users/"+str(userid)
		
		#check if schema exists
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'ASK where { <'+new_schema_url+'> a typon:Schema; typon:administratedBy <'+new_user_url+'>; typon:deprecated  "true"^^xsd:boolean }')
		if result['boolean']:
			return "Schema not found or schema is not yours", 404
		
		#check if locus exists
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(args['loci_id'])
		result = get_data(virtuoso_server,'ASK where { <'+new_locus_url+'> a typon:Locus}')
		if not result['boolean']:
			return "Locus not found", 404
		
		#check if locus already exists on schema
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(args['loci_id'])
		result = get_data(virtuoso_server,'ASK where { <'+new_schema_url+'> typon:hasSchemaPart ?part. ?part typon:hasLocus <'+new_locus_url+'>.}')
		if result['boolean']:
			return "Locus already on schema", 409
				
		#get number of loci on schema and build the uri based on that number+1 , using a celery queue
		
		task = add_locus_schema.apply(args=[new_schema_url,new_locus_url])
					
		process_result=task.result
		
		process_ran=task.ready()
		process_sucess=task.status
		
		if process_ran and process_sucess == "SUCCESS":
			pass
		else:
			return "status: "+process_sucess+" run:"+process_ran, 400
		
		process_result=task.result
		print(process_result)
		new_allele_url=process_result[0]
		process_result_status_code=int(process_result[-1])
		
		if process_result_status_code > 201 :
			
			#check if process was sucessfull
			return "Sum Thing Wong creating sequence 2", process_result_status_code
		else:
			return new_allele_url, process_result_status_code
		
		
	#it doesnt delete, it just adds an attribute typon:deprecated  "true"^^xsd:boolean to that part of the schema, the locus is just "removed" for the specific schema!!!11
	@auth_token_required
	def delete(self, spec_id, id):
		args = self.reqparse.parse_args(strict=True)
		
		try:
			args['loci_id']
		except:
			return "No valid id provided for loci: loci_id=<int>", 404
		
		#only admin can do this
		
		userid=g.identity.user.id
		try:
			new_user_url=baseURL+"users/"+str(userid)
			result = get_data(virtuoso_server,'ASK where { <'+new_user_url+'> a <http://xmlns.com/foaf/0.1/Agent>; typon:Role "Admin"^^xsd:string}')
			if not result['boolean']:
				return "not authorized, admin only", 405
		except:
			return "not authorized, admin only", 405
		#~ try:
			#~ userid=g.identity.user.id
		#~ except:
			#~ return "not authorized, admin only", 405
		#~ if userid>1:
			#~ return "not authorized, admin only", 405
		#~ 
		#~ userid=1
		
		new_user_url=baseURL+"users/"+str(userid)
		
		#check if schema exists
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'ASK where { <'+new_schema_url+'> a typon:Schema; typon:administratedBy <'+new_user_url+'>; typon:deprecated  "true"^^xsd:boolean }')
		if not result['boolean']:
			return "Schema not found or schema is not yours", 404
		
		#check if locus exists
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(args['loci_id'])
		result = get_data(virtuoso_server,'ASK where { <'+new_locus_url+'> a typon:Locus}')
		if not result['boolean']:
			return "Locus not found", 404
		
		#check if locus exists on schema
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(args['loci_id'])
		result = get_data(virtuoso_server,'ASK where { <'+new_schema_url+'> typon:hasSchemaPart ?part. ?part typon:hasLocus <'+new_locus_url+'>. FILTER NOT EXISTS { ?part typon:deprecated  "true"^^xsd:boolean }.}')
		if not result['boolean']:
			return "Locus already not on schema", 409
				
		result = get_data(virtuoso_server,'select ?parts where { <'+new_schema_url+'> typon:hasSchemaPart ?parts. ?parts typon:hasLocus <'+new_locus_url+'>.}')
		
		schema_link=result["results"]["bindings"][0]['parts']['value']
						
		
		#add a tripple to the link between the schema and the locus implying that the locus is deprecated for that schema
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+schema_link+'> typon:deprecated "true"^^xsd:boolean.}')
		
		if result.status_code == 201 :
			return "Locus sucessfully removed from schema", 201		
		else:
			return "Sum Thing Wong", result.status_code
		


#@app.route('/NS/species/<int:spec_id>/loci') 
class LociListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('prefix', dest= 'prefix',
								   required=False,
								   type=str,
								   help='No valid aliases provided for loci')
		self.reqparse.add_argument('sequence', dest= 'sequence',
								   required=False,
								   type=str,
								   default=False,
								   help='No valid sequence provided')
		self.reqparse.add_argument('locus_ori_name', dest= 'locus_ori_name',
								   required=False,
								   type=str,
								   default=False,
								   help='provide original locus name')

		#~ super(LociListAPI, self).__init__()

	# curl -i http://localhost:5000/NS/species/1/loci
	def get(self, spec_id):
		
		args = self.reqparse.parse_args(strict=False)
		sequence=args['sequence']
		if sequence:
			sequence=str(sequence).upper()
		
		spec_url=baseURL+"species/"+str(spec_id)
		
		#sequence was provided, return the locus uri found that has the sequence, else give all locus from that species
		if sequence:
			
			new_id=hashlib.sha256(sequence.encode('utf-8')).hexdigest()
			new_seq_url=baseURL+"sequences/"+str(new_id)
			result = get_data(virtuoso_server,'select ?locus where {?alleles typon:hasSequence <'+new_seq_url+'>; typon:isOfLocus ?locus.?locus typon:isOfTaxon <'+spec_url+'>.}')
			try:
				return (result["results"]["bindings"])
			except:
				return []
		
		else:
			result = get_data(virtuoso_server,'select (str(?name) as ?name) ?locus (str(?original_name) as ?original_name) where { ?locus a typon:Locus; typon:isOfTaxon <'+spec_url+'>; typon:name ?name. OPTIONAL{?locus typon:originalName ?original_name.} }')
			
			
			
			try:
				def generate():
					yield '{"Loci": ['
					try:
						prev_item=result["results"]["bindings"].pop(0)
					except:
						yield ']}'
					for item in result["results"]["bindings"]:
						yield json.dumps(prev_item)+','
						prev_item = item
					yield json.dumps(prev_item)+']}'
				
				return Response(stream_with_context(generate()), content_type='application/json')
				
				
			except:
				return [],400
		
		

	# curl -i http://localhost:5000/NS/species/1/loci -d 'aliases=macarena'
	@auth_token_required
	def post(self, spec_id):
		args = self.reqparse.parse_args(strict=True)
		
		locus_ori_name=args['locus_ori_name']
		print(locus_ori_name)
		
		try:
			check_len(args['prefix'])
		except:
			return "provide prefix", 400
		
		
		#only admin can do this
		
		userid=g.identity.user.id
		try:
			new_user_url=baseURL+"users/"+str(userid)
			result = get_data(virtuoso_server,'ASK where { <'+new_user_url+'> a <http://xmlns.com/foaf/0.1/Agent>; typon:Role "Admin"^^xsd:string}')
			if not result['boolean']:
				return "not authorized, admin only", 405
		except:
			return "not authorized, admin only", 405
		
		#~ userid=g.identity.user.id
		#~ if userid>1:
			#~ return "not authorized, admin only", 405
		
		spec_url=baseURL+"species/"+str(spec_id)
		result = get_data(virtuoso_server,'ASK where { <'+spec_url+'> a <http://purl.uniprot.org/core/Taxon>}')
		
		
		if not result['boolean'] :
			return "Species not found", 404
		
		#check if already exists locus with that aliases
		#~ result = get_data(virtuoso_server,'ASK where { ?locus a typon:Locus; typon:name "'+args['aliases']+'"^^xsd:string.}')
		#~ 
		#~ if result['boolean'] :
			#~ return "Locus already exists", 409
		
		#count number of loci already created for that species, build the new locus uri and send to server
		result = get_data(virtuoso_server,'select (COUNT(?locus) as ?count) where { ?locus a typon:Locus; typon:isOfTaxon <'+spec_url+'>. }')
		number_loci_spec=int(result["results"]["bindings"][0]['count']['value'])
		
		newLocusId=number_loci_spec+1
		
		#name will be something like prefix000001.fasta
		#no more .fasta now
		#aliases=args['prefix']+"%06d" % (newLocusId,)+".fasta"
		aliases=args['prefix']+"%06d" % (newLocusId,)+""
		
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(newLocusId)
		
		#if locus_ori_name then also save the original fasta name
		if locus_ori_name:
			result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_locus_url+'> a typon:Locus; typon:name "'+aliases+'"^^xsd:string; typon:isOfTaxon <'+spec_url+'> ; typon:originalName "'+locus_ori_name+'"^^xsd:string.}')

		else:
			result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_locus_url+'> a typon:Locus; typon:name "'+aliases+'"^^xsd:string; typon:isOfTaxon <'+spec_url+'> .}')

		if result.status_code == 201 :
			return new_locus_url, 201		
		else:
			return "Sum Thing Wong", result.status_code

#@app.route('/NS/species/<int:spec_id>/loci/<int:id>/fasta')
class LociFastaAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1/loci/7/fasta
	def get(self, spec_id, id):
		
		spec_url=baseURL+"species/"+str(spec_id)
		result = get_data(virtuoso_server,'ASK where { <'+spec_url+'> a <http://purl.uniprot.org/core/Taxon>}')
		
		if not result['boolean'] :
			return "Species not found", 404
		
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(id)
		
		# find all alleles from the locus and return the sequence and id sorted by id
		result = get_data(virtuoso_server,'select ?allele_id (str(?nucSeq) as ?nucSeq) where { <'+new_locus_url+'> a typon:Locus; typon:name ?name. ?alleles typon:isOfLocus <'+new_locus_url+'> .?alleles typon:hasSequence ?sequence; typon:id ?allele_id .?sequence typon:nucleotideSequence ?nucSeq. } order by ASC(?allele_id)')
		
		#sometimes virtuoso returns an error "Max row length is exceeded when trying to store a string of" due to the sequences being too
		#large, if it happens there is a way around
		try:
			result["results"]["bindings"]
		except:
			#virtuoso returned an error, if it excedeed length request each allele one at a time
			if "Max row length is exceeded when trying to store a string of" in str(result):
				
				print ("sequence too long")
				result = get_data(virtuoso_server,'select ?allele_id ?sequence where { <'+new_locus_url+'> a typon:Locus; typon:name ?name. ?alleles typon:isOfLocus <'+new_locus_url+'> .?alleles typon:hasSequence ?sequence; typon:id ?allele_id .} order by ASC(?allele_id)')
				
				i=0
				for seq in result["results"]["bindings"]:
					
					#~ print(seq)
					
					result2 = get_data(virtuoso_server,'select (str(?nucSeq) as ?nucSeq) where {<'+seq['sequence']['value']+'> typon:nucleotideSequence ?nucSeq. }')
					
					#print(result2)
					
					realsequence=result2["results"]["bindings"][0]['nucSeq']['value']
					
					seq['nucSeq']={'value':str(realsequence)}
					#seq['nucSeq']['value']=str(realsequence)
					result["results"]["bindings"][i]['nucSeq']=result2["results"]["bindings"][0]['nucSeq']
					i+=1
				

				## stream way to send data
				try:
					def generate():
						yield '{"Fasta": ['
						try:
							prev_item=result["results"]["bindings"].pop(0)
						except:
							yield ']}'
						for item in result["results"]["bindings"]:
							yield json.dumps(prev_item)+','
							prev_item = item
						yield json.dumps(prev_item)+']}'
					
					return Response(stream_with_context(generate()), content_type='application/json')
				
				
				except:
					return []
				return result["results"]["bindings"]
			
			#the query returned some error, retry it one last time
			time.sleep(1)
			result = get_data(virtuoso_server,'select ?allele_id (str(?nucSeq) as ?nucSeq) where { <'+new_locus_url+'> a typon:Locus; typon:name ?name. ?alleles typon:isOfLocus <'+new_locus_url+'> .?alleles typon:hasSequence ?sequence; typon:id ?allele_id .?sequence typon:nucleotideSequence ?nucSeq. } order by ASC(?allele_id)')
			#TODO add response on stream mode
			
			
		#~ return result["results"]["bindings"]
		
		try:
			def generate():
				yield '{"Fasta": ['
				try:
					prev_item=result["results"]["bindings"].pop(0)
				except:
					yield ']}'
				for item in result["results"]["bindings"]:
					yield json.dumps(prev_item)+','
					prev_item = item
				yield json.dumps(prev_item)+']}'
			
			return Response(stream_with_context(generate()), content_type='application/json')
		
		
		except:
			return [],400

#@app.route('/NS/species/<int:spec_id>/loci/<int:id>/uniprot')
class LociUniprotAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1/loci/7/uniprot
	def get(self, spec_id, id):
		
		spec_url=baseURL+"species/"+str(spec_id)
		result = get_data(virtuoso_server,'ASK where { <'+spec_url+'> a <http://purl.uniprot.org/core/Taxon>}')
		
		if not result['boolean'] :
			return "Species not found", 404
		
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(id)
		
		#get all uniprot labels and URI from all alleles of the selected locus
		result = get_data(virtuoso_server,'select distinct (str(?UniprotLabel) as ?UniprotLabel) (str(?UniprotURI) as ?UniprotURI) where { <'+new_locus_url+'> a typon:Locus; typon:name ?name. ?alleles typon:isOfLocus <'+new_locus_url+'> .?alleles typon:hasSequence ?sequence. OPTIONAL{?sequence typon:hasUniprotLabel ?UniprotLabel.} OPTIONAL{?sequence typon:hasUniprotSequence ?UniprotURI }}')
		
		try:
			def generate():
				yield '{"UniprotInfo": ['
				try:
					prev_item=result["results"]["bindings"].pop(0)
				except:
					yield ']}'
				for item in result["results"]["bindings"]:
					if len(prev_item.keys())>0:
						yield json.dumps(prev_item)+','
					prev_item = item
				yield json.dumps(prev_item)+']}'

			
			return Response(stream_with_context(generate()), content_type='application/json')
		
		
		except:
			return [],400

#@app.route('/NS/species/<int:spec_id>/loci/<int:id>')
class LociAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1/loci/7
	def get(self, spec_id, id):
		
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(id)
		result = get_data(virtuoso_server,'select (str(?name) as ?name) (str(?original_name) as ?original_name) (COUNT(?alleles) as ?number_alleles) (AVG(strlen(str(?nucSeq)))as ?average_length) (MIN(strlen(str(?nucSeq)))as ?min_length) (MAX(strlen(str(?nucSeq)))as ?max_length) where { <'+new_locus_url+'> a typon:Locus; typon:name ?name; typon:hasDefinedAllele ?alleles.?alleles typon:hasSequence ?sequence.?sequence typon:nucleotideSequence ?nucSeq. OPTIONAL{<'+new_locus_url+'> typon:originalName ?original_name.} }')

		response=result["results"]["bindings"]
		response[0]['alleles']={'value':new_locus_url+'/alleles'}
		response[0]['uniprotInfo']={'value':new_locus_url+'/uniprot'}
		try:
			
			return (response)
		except:
			return []

#@app.route('/NS/species/<int:spec_id>/loci/<int:id>/alleles')
class AlleleListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('sequence', dest= 'sequence',
								   required=True,
								   type=str,
								   help='No valid sequence provided for allele')
		self.reqparse.add_argument('enforceCDS', dest= 'enforceCDS',
								   required=False,
								   type=str,
								   #~ default=True,
								   help='False to not Enforce CDS')

	# curl -i http://localhost:5000/NS/species/1/loci/7/alleles
	def get(self, spec_id, loci_id):

		#get list of alleles from that locus
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(loci_id)
		result = get_data(virtuoso_server,'select ?alleles where { <'+new_locus_url+'> a typon:Locus; typon:hasDefinedAllele ?alleles. ?alleles typon:id ?id }ORDER BY ASC(?id)')
		try:
			return (result["results"]["bindings"])
		except:
			return []
		


	# curl -i http://localhost:5000/NS/species/1/loci/7/alleles -d 'sequence=ACTCTGT'
	@auth_token_required
	def post(self, spec_id, loci_id):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['sequence'])

		enforceCDS=True
		try:
			if "False" in args['enforceCDS']:
				enforceCDS=False
		except:
			pass
		
		print("Enforce a cds: "+str(enforceCDS))
		
		#check if it's a validated user
		#~ userid=1
		try:
			userid=g.identity.user.id
		except:
			return "not authorized, authorized only", 405
		
		#this is the user uri
		new_user_url=baseURL+"users/"+str(userid)
		
		#check if species exists
		new_spec_url=baseURL+"species/"+str(spec_id)
		result = get_data(virtuoso_server,'ASK where { <'+new_spec_url+'> a <http://purl.uniprot.org/core/Taxon>}')
		
		if not result['boolean'] :
			return "Species not found", 404
		
		#check if locus exist
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(loci_id)
		result = get_data(virtuoso_server,'ASK where { <'+new_locus_url+'> a <http://purl.phyloviz.net/ontology/typon#Locus>.}')
		if not result['boolean'] :

			return "Locus not found", 404
		
		
		#sequences need to translate, that's the chewie way
		sequence=(str(args['sequence'])).upper()
		
		#sequence may no longer be translatable on user request, sad chewie :(
		sequenceIstranslatable=False
		proteinSequence=''
		#~ if enforceCDS:
		
		#will attempt to translate even if not enforced CDS
		#if translatable and enforce, ok
		#if translatable and not enforce, ok
		#if not translatable and enforce, error
		print("trying to translate")
		try:
			proteinSequence=translateSeq(sequence,False,enforceCDS)
			sequenceIstranslatable=True
			print(sequenceIstranslatable)
		except Exception as e:
			if enforceCDS:
				return "sequence failed to translate, not a CDS", 418
			else:
				sequenceIstranslatable=False
				

		#check if sequence is already present on locus query
		query='select ?alleles where { ?alleles typon:isOfLocus <'+new_locus_url+'>; typon:hasSequence ?seq. ?seq a typon:Sequence; typon:nucleotideSequence "'+sequence+'"^^xsd:string.}'
		

		if len(sequence) > 9000:
			result=send_big_query(virtuoso_server,query)
		else:
			result = get_data(virtuoso_server,query)
		
		#if sequence already exists on locus return the allele uri, if not create new sequence
		try :
			new_allele_url = result["results"]["bindings"][0]['alleles']['value']
			return new_allele_url, 200
	
		
		#sequence doesnt exist, create new and link to new allele uri. return the new allele uri
		except IndexError:
			
			
			#check if sequence exists in uniprot only if the sequence was translatable
			if sequenceIstranslatable:
				add2send2graph=''
				print("check if in uniprot")
				try:
					
					# query the uniprot sparql endpoint and build the RDF with the info on uniprot
					
					proteinSequence=proteinSequence.replace("*","")
					query='PREFIX rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>  PREFIX up: <http://purl.uniprot.org/core/> PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> select ?seq ?label ?sname where { ?b a up:Simple_Sequence; rdf:value "'+proteinSequence+'". ?seq up:sequence ?b. OPTIONAL {?seq rdfs:label ?label.} OPTIONAL {?seq up:submittedName ?rname2. ?rname2 up:fullName ?sname.}}LIMIT 20'
					#~ print (query)
					result2 = get_data(uniprot_server,query)
					
					url=result2["results"]["bindings"][0]['seq']['value']
					add2send2graph+='; typon:hasUniprotSequence <'+url+'>'
					try:
						url2=result2["results"]["bindings"][0]['label']['value']
						url2=sanitize_input(url2)
						add2send2graph+='; typon:hasUniprotLabel "'+url2+'"^^xsd:string'
					except:
						print ("no label associated")
						pass
					try:
						url2=result["results"]["bindings"][0]['sname']['value']
						url=sanitize_input(url2)
						rdf_2_ins+='; typon:hasUniprotSName "'+url2+'"^^xsd:string'
					except:
						#~ print ("no submitted name associated")
						pass

				#the sequence is not on uniprot or there was an error querying uniprot, just continue
				except Exception as e:
					add2send2graph=''
					#print (e)
					pass
			else:
				add2send2graph=''
						
			
			#build the id of the sequence hashing it
			new_id=hashlib.sha256(sequence.encode('utf-8')).hexdigest()
			
			# build the remaining new seq uri
			new_seq_url=baseURL+"sequences/"+str(new_id)

			
			#check if the uri with the hash is already attributed
			result = get_data(virtuoso_server,'ASK where { <'+new_seq_url+'> typon:nucleotideSequence ?seq.}')
			if result['boolean']:
				
				#check if the same sequence is attributed or there is a hash collision
				result = get_data(virtuoso_server,'ASK where { <'+new_seq_url+'> a typon:Sequence; typon:nucleotideSequence "'+sequence+'"^^xsd:string.}')
				
				#sequence was already attributed to the exact same sequence, reusing it
				if result['boolean']:
					
	
					task = add_allele.apply(args=[new_locus_url,spec_id,loci_id,new_user_url,new_seq_url,False,add2send2graph,sequence])
					
					process_result=task.result
					
					process_ran=task.ready()
					process_sucess=task.status
					
					if process_ran and process_sucess == "SUCCESS":
						pass
					else:
						return "status: "+process_sucess+" run:"+process_ran, 400
					
					process_result=task.result
					print(process_result)
					new_allele_url=process_result[0]
					process_result_status_code=int(process_result[-1])
					
					if process_result_status_code > 201 :
						
						#check if process was sucessfull
						return "Sum Thing Wong creating sequence 3", process_result_status_code
					else:
						return new_allele_url, process_result_status_code
					
				# attention, there was a hash collision!!!!1111111 a different sequence was attributed to the same hash
				else:
					return "URI "+new_seq_url+" already has sequence "+sequence+" with that hash, contact the admin!", 409
			
			#the hash is not yet attributed
			else:
				
				task = add_allele.apply(args=[new_locus_url,spec_id,loci_id,new_user_url,new_seq_url,True,add2send2graph,sequence])
				
				#result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_seq_url+'> a typon:Sequence '+add2send2graph+' ; typon:nucleotideSequence "'+args['sequence']+'"^^xsd:string.<'+new_allele_url+'> a typon:Allele; typon:sentBy  <'+new_user_url+'> ;typon:isOfLocus <'+new_locus_url+'>; typon:dateEntered "'+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+'"^^xsd:dateTime; typon:id "'+str(number_alleles_loci+1)+'"^^xsd:integer ; typon:hasSequence <'+new_seq_url+'>. <'+new_locus_url+'> typon:hasDefinedAllele <'+new_allele_url+'>.}')
				
				
				process_ran=task.ready()
				process_sucess=task.status
				
				if process_ran and process_sucess == "SUCCESS":
					pass
				else:
					return "status: "+process_sucess+" run:"+process_ran, 400
				
				process_result=task.result
				print(process_result)
				new_allele_url=process_result[0]
				process_result_status_code=int(process_result[-1])
				
				if process_result_status_code > 201 :
					
					#check if process was sucessfull
					return "Sum Thing Wong creating sequence 4", process_result_status_code
				else:
					return new_allele_url, process_result_status_code
				
				
		except Exception as e:
			print ('Error on line {}'.format(sys.exc_info()[-1].tb_lineno))
			print (e)
			return "Sum Thing Wong creating sequence", 400
		
		
#@app.route('/NS/species/<int:spec_id>/loci/<int:loci_id>/alleles/<int:allele_id>')
class AlleleAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria/loci/7/alleles/7
	def get(self, spec_id, loci_id, allele_id):
		
		new_allele_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(loci_id)+"/alleles/"+str(allele_id)
		
		#get information on allele, sequence, submission date, id and number of isolates with this allele
		result = get_data(virtuoso_server,'select ?sequence ?date ?id (COUNT(?isolate) as ?isolate_count) where { <'+new_allele_url+'> a typon:Allele; typon:dateEntered ?date; typon:hasSequence ?sequence; typon:id ?id. OPTIONAL{?isolate a typon:Isolate; typon:hasAllele <'+new_allele_url+'>}}')
		try:
			return (result["results"]["bindings"])
		except:
			return []	

#@app.route('/NS/sequences/<string:seq_id>')
class SequencesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/sequences/5
	def get(self, seq_id):
		
		new_seq_url=baseURL+"sequences/"+str(seq_id)

		#get information on sequence, DNA string, uniprot URI and uniprot label
		result = get_data(virtuoso_server,'select ?sequence ?uniprot ?label where { <'+new_seq_url+'> a typon:Sequence; typon:nucleotideSequence ?sequence. OPTIONAL { <'+new_seq_url+'> typon:hasUniprotSequence ?uniprot.}. OPTIONAL{ <'+new_seq_url+'> typon:hasUniprotLabel ?label.}}')
		try:
			return (result["results"]["bindings"])
		except:
			return []

#@app.route('/NS/sequences/')
class SequencesListAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/sequences
	def get(self):
		
		#query number of sequences on database
		result = get_data(virtuoso_server,'select (COUNT(?seq) as ?count) where {?seq a typon:Sequence }')
		number_sequences_vir=int(result["results"]["bindings"][0]['count']['value'])
		
		try:
			return (number_sequences_vir)
		except:
			return []

#this one does the same job as doing a post of an allele on a loci, it returns the allele id if present
#@app.route('/NS/species/<int:spec_id>/loci/sequences')
class LociSequencesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1/loci/5/sequences
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('sequence', dest= 'sequence',
								   required=True,
								   type=str,
								   help='No valid sequence provided for allele')
	
	def get(self, spec_id, loci_id):

		args = self.reqparse.parse_args(strict=True)
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(loci_id)
		result = get_data(virtuoso_server,'select ?id where { <'+new_locus_url+'> a <http://purl.phyloviz.net/ontology/typon#Locus>; typon:hasDefinedAllele ?allele. ?allele typon:hasSequence ?seq; typon:id ?id. ?seq typon:nucleotideSequence "'+args['sequence']+'"^^xsd:string.}')		
		
		#print(result)
		try:
			return (result["results"]["bindings"])
		except:
			return [],400

#@app.route('/NS/species/<int:spec_id>/isolates')
class IsolatesListAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1/isolates
	
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('isolName', dest= 'isolName',
								   required=False,
								   type=str,
								   help='isolate name')
		
		self.reqparse.add_argument('start', dest= 'start',
								   required=False,
								   type=str,
								   help='provide a date in the format YYYY-MM-DDTHH:MM:SS to get the isolates that were uploaded after that defined date')
		
		self.reqparse.add_argument('end', dest= 'end',
								   required=False,
								   type=str,
								   help='provide a date in the format YYYY-MM-DDTHH:MM:SS to get the isolates that were uploaded before that defined date')
	def get(self, spec_id):
		
		args = self.reqparse.parse_args(strict=True)
		isolName=False
		try:
			isolName=args['isolName']
		except:
			pass
		
		startDate=False
		try:
			startDate=args['start']
		except:
			pass
		
		endDate=False
		try:
			endDate=args['end']
		except:
			pass
		
		#if isolate name is provided return that isolate, else return all isolates
		#if number of isolates >100000 either increase the number of rows the virtuoso return or use the dateEntered property 
		#and make multiple queries to virtuoso based on the date until all have been fetched
		#you can create your own time intervals to better suite your query
		if isolName:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate ?date where { ?isolate a typon:Isolate; typon:isFromTaxon <'+new_spec_url+'>; typon:dateEntered ?date; typon:name "'+isolName+'"^^xsd:string.}')
		elif startDate and endDate:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate ?name where {{ select ?isolate ?name where { ?isolate a typon:Isolate; typon:isFromTaxon <'+new_spec_url+'>; typon:name ?name;typon:dateEntered ?date. FILTER ( ?date > "'+startDate+'"^^xsd:dateTime ).FILTER ( ?date < "'+endDate+'"^^xsd:dateTime ) } order by ASC(?date)}} LIMIT 50000')
		
		elif endDate:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate ?name where {{ select ?isolate ?name where { ?isolate a typon:Isolate; typon:isFromTaxon <'+new_spec_url+'>; typon:name ?name;typon:dateEntered ?date. FILTER ( ?date < "'+endDate+'"^^xsd:dateTime ). } order by DESC(?date)}} LIMIT 50000')
		
		elif startDate:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate ?name where {{ select ?isolate ?name where { ?isolate a typon:Isolate; typon:isFromTaxon <'+new_spec_url+'>; typon:name ?name;typon:dateEntered ?date. FILTER ( ?date > "'+startDate+'"^^xsd:dateTime ). } order by ASC(?date)}} LIMIT 50000')
		else:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate ?name where {{select ?isolate ?name where { ?isolate a typon:Isolate; typon:isFromTaxon <'+new_spec_url+'>;typon:dateEntered ?date ; typon:name ?name. }order by ASC(?date)}}LIMIT 50000')
		
		if len(result["results"]["bindings"])<1:
			
			def generate():
				yield '{"Isolates": []}'
			
			r = Response(stream_with_context(generate()), content_type='application/json')
			r.headers.set('Server-Date',str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')))
			return r
		
		latestIsolate=(result["results"]["bindings"])[-1]
		isolate_id=latestIsolate['isolate']['value']
		
		#get latest isolate submission date
		result2 = get_data(virtuoso_server,' select ?date where { <'+isolate_id+'> a typon:Isolate; typon:dateEntered ?date }')
		
		latestDatetime=(result2["results"]["bindings"])[0]['date']['value']
		number_of_isolates=len(result["results"]["bindings"])
		try:
			
			def generate():
				yield '{"Isolates": ['
				#~ for item in result["results"]["bindings"]:
					#~ yield json.dumps(item)+','
				#~ yield json.dumps({'date':latestDatetime})+']}'
			
				try:
					prev_item=result["results"]["bindings"].pop(0)
				except:
					yield ']}'
				for item in result["results"]["bindings"]:
					yield json.dumps(prev_item)+','
					prev_item = item
				yield json.dumps(prev_item)+']}'
				
			r = Response(stream_with_context(generate()), content_type='application/json')
			r.headers.set('Last-Isolate',latestDatetime)
			if number_of_isolates>49999:
				r.headers.set('All-Isolates-Returned',False)
			else:
				r.headers.set('All-Isolates-Returned',True)
			return r
		
		except:
			return []

#@app.route('/NS/species/<int:spec_id>/isolates/user')
class IsolatesUserListAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1/isolates/user
	
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('isolName', dest= 'isolName',
								   required=False,
								   type=str,
								   help='isolate name')
		
		self.reqparse.add_argument('start', dest= 'start',
								   required=False,
								   type=str,
								   help='provide a date in the format YYYY-MM-DDTHH:MM:SS to get the isolates that were uploaded after that defined date')
		
		self.reqparse.add_argument('end', dest= 'end',
								   required=False,
								   type=str,
								   help='provide a date in the format YYYY-MM-DDTHH:MM:SS to get the isolates that were uploaded before that defined date')
	@auth_token_required
	def get(self, spec_id):
		
		args = self.reqparse.parse_args(strict=True)
		isolName=False
		try:
			isolName=args['isolName']
		except:
			pass
		
		startDate=False
		try:
			startDate=args['start']
		except:
			pass
		
		endDate=False
		try:
			endDate=args['end']
		except:
			pass
		
		userid=g.identity.user.id
		user_url=baseURL+"users/"+str(userid)
		
		#if isolate name is provided return that isolate, else return all isolates
		#if number of isolates >100000 either increase the number of rows the virtuoso return or use the dateEntered property 
		#and make multiple queries to virtuoso based on the date until all have been fetched
		#you can create your own time intervals to better suite your query
		if isolName:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate ?date where { ?isolate a typon:Isolate; typon:sentBy <'+user_url+'>; typon:isFromTaxon <'+new_spec_url+'>; typon:dateEntered ?date; typon:name "'+isolName+'"^^xsd:string.}')
		elif startDate and endDate:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate ?name where {{ select ?isolate ?name where { ?isolate a typon:Isolate; typon:sentBy <'+user_url+'>; typon:isFromTaxon <'+new_spec_url+'>; typon:name ?name;typon:dateEntered ?date. FILTER ( ?date > "'+startDate+'"^^xsd:dateTime ).FILTER ( ?date < "'+endDate+'"^^xsd:dateTime ) } order by ASC(?date)}} LIMIT 50000')
		
		elif endDate:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate ?name where {{ select ?isolate ?name where { ?isolate a typon:Isolate; typon:sentBy <'+user_url+'>; typon:isFromTaxon <'+new_spec_url+'>; typon:name ?name;typon:dateEntered ?date. FILTER ( ?date < "'+endDate+'"^^xsd:dateTime ). } order by DESC(?date)}} LIMIT 50000')
		
		elif startDate:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate ?name where {{ select ?isolate ?name where { ?isolate a typon:Isolate; typon:sentBy <'+user_url+'>; typon:isFromTaxon <'+new_spec_url+'>; typon:name ?name;typon:dateEntered ?date. FILTER ( ?date > "'+startDate+'"^^xsd:dateTime ). } order by ASC(?date)}} LIMIT 50000')
		else:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate ?name where {{select ?isolate ?name where { ?isolate a typon:Isolate; typon:sentBy <'+user_url+'>; typon:isFromTaxon <'+new_spec_url+'>;typon:dateEntered ?date ; typon:name ?name. }order by ASC(?date)}}LIMIT 50000')
		
		if len(result["results"]["bindings"])<1:
			
			def generate():
				yield '{"Isolates": []}'
			
			r = Response(stream_with_context(generate()), content_type='application/json')
			r.headers.set('Server-Date',str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')))
			return r
		
		latestIsolate=(result["results"]["bindings"])[-1]
		isolate_id=latestIsolate['isolate']['value']
		
		#get latest isolate submission date
		result2 = get_data(virtuoso_server,' select ?date where { <'+isolate_id+'> a typon:Isolate; typon:dateEntered ?date }')
		
		latestDatetime=(result2["results"]["bindings"])[0]['date']['value']
		number_of_isolates=len(result["results"]["bindings"])
		try:
			
			def generate():
				yield '{"Isolates": ['
				#~ for item in result["results"]["bindings"]:
					#~ yield json.dumps(item)+','
				#~ yield json.dumps({'date':latestDatetime})+']}'
			
				try:
					prev_item=result["results"]["bindings"].pop(0)
				except:
					yield ']}'
				for item in result["results"]["bindings"]:
					yield json.dumps(prev_item)+','
					prev_item = item
				yield json.dumps(prev_item)+']}'
				
			r = Response(stream_with_context(generate()), content_type='application/json')
			r.headers.set('Last-Isolate',latestDatetime)
			if number_of_isolates>49999:
				r.headers.set('All-Isolates-Returned',False)
			else:
				r.headers.set('All-Isolates-Returned',True)
			return r
		
		except:
			return []

#@app.route('/NS/species/<int:spec_id>/isolates/<string:isol_id>')
class IsolatesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/isolates/<string:isol_id>
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('accession', dest= 'accession',
								   required=False,
								   type=str,
								   help='acession URL to reads')
		self.reqparse.add_argument('ST', dest= 'st',
								   required=False,
								   type=str,
								   help='ST for traditional 7 genes MLST')
		self.reqparse.add_argument('strainId', dest= 'strainID',
								   required=False,
								   type=str,
								   help='strain identifier')
		self.reqparse.add_argument('collection_date', dest= 'coldate',
								   required=False,
								   type=str,
								   help='the date on which the sample was collected')
		self.reqparse.add_argument('host', dest= 'host',
								   required=False,
								   type=str,
								   help='The natural (as opposed to laboratory) host to the organism from which the sample was obtained. Use the full taxonomic name, eg, "Homo sapiens".')
		self.reqparse.add_argument('host_disease', dest= 'host_disease',
								   required=False,
								   type=str,
								   help='DOID ID , e.g. salmonellosis has ID 0060859. Controlled vocabulary, http://www.disease-ontology.org/')
		self.reqparse.add_argument('lat', dest= 'lat',
								   required=False,
								   type=float,
								   help='latitude information in the WGS84 geodetic reference datum, e.g 30.0000')
		self.reqparse.add_argument('long', dest= 'long',
								   required=False,
								   type=float,
								   help='longitude information in the WGS84 geodetic reference datum, e.g. 30.0000')
		self.reqparse.add_argument('isol_source', dest= 'isol_source',
								   required=False,
								   type=str,
								   help='Describes the physical, environmental and/or local geographical source of the biological sample from which the sample was derived.')
		self.reqparse.add_argument('country', dest= 'country',
								   required=False,
								   type=str,
								   help='Country from isolate')							  
	
	def get(self, spec_id, isol_id):
		
		#new_isol_url=baseURL+"isolates/"+str(isol_id)
		new_isol_url=baseURL+"species/"+str(spec_id)+"/isolates/"+str(isol_id)
		
		#get information on the isolate, metadata are optional
		query='select ?name ?country ?country_name ?accession ?st ?date_entered  ?strainID ?col_date ?host ?host_disease ?lat ?long ?isol_source\n where { <'+new_isol_url+'''> a typon:Isolate; typon:name ?name; typon:dateEntered ?date_entered.
		OPTIONAL{<'''+new_isol_url+'''> typon:isolatedAt ?country. ?country rdfs:label ?country_name}
		OPTIONAL{<'''+new_isol_url+'''> typon:accession ?accession.}
		OPTIONAL{<'''+new_isol_url+'''> typon:ST ?st.} 
		OPTIONAL{<'''+new_isol_url+'''> typon:sampleCollectionDate ?col_date.}
		OPTIONAL{<'''+new_isol_url+'''> typon:host ?host.}
		OPTIONAL{<'''+new_isol_url+'''> typon:hostDisease ?host_disease.}
		OPTIONAL{<'''+new_isol_url+'''> <http://www.w3.org/2003/01/geo/wgs84_pos#lat> ?lat.}
		OPTIONAL{<'''+new_isol_url+'''> <http://www.w3.org/2003/01/geo/wgs84_pos#long> ?long.} 
		OPTIONAL{<'''+new_isol_url+'> typon:isolationSource ?isol_source.} }'
		result = get_data(virtuoso_server,query)
		#result = get_data(virtuoso_server,'select ?name ?country ?country_name ?accession ?st ?date_entered  ?strainID where { <'+new_isol_url+'> a typon:Isolate; typon:name ?name; typon:dateEntered ?date_entered. OPTIONAL{<'+new_isol_url+'> typon:isolatedAt ?country. ?country rdfs:label ?country_name}OPTIONAL{<'+new_isol_url+'> typon:accession ?accession.}OPTIONAL{<'+new_isol_url+'> typon:st ?st.} OPTIONAL{<'+new_isol_url+'> typon:userStrainId ?strainID.} }')
		try:
			return (result["results"]["bindings"])
		except:
			return []
	
	@auth_token_required
	def post(self, spec_id, isol_id):
		args = self.reqparse.parse_args(strict=True)
		
		#remove nones from args
		args2remove=[]
		for k,v in args.items():
			if v is None:
				args2remove.append(k)
		for k in args2remove:	
			args.pop(k, None)
		

		#check if isolate exist
		#new_isol_url=baseURL+"isolates/"+str(isol_id)
		new_isol_url=baseURL+"species/"+str(spec_id)+"/isolates/"+str(isol_id)
		result = get_data(virtuoso_server,'ASK where { <'+new_isol_url+'> a typon:Isolate.}')
		if not result['boolean'] :
			return "Isolate not found", 404
		
		#check if isolate belongs to the user that is submitting the post
		#~ userid=1
		userid=g.identity.user.id
		new_user_url=baseURL+"users/"+str(userid)
		result = get_data(virtuoso_server,'ASK where { <'+new_isol_url+'> typon:sentBy <'+new_user_url+'>.}')
		if not result['boolean'] :
			return "Isolate not yours", 403
		
		
		#get metadata already existing
		query='select ?name ?country ?country_name ?accession ?st ?date_entered  ?strainID ?col_date ?host ?host_disease ?lat ?long ?isol_source\n where { <'+new_isol_url+'''> a typon:Isolate; typon:name ?name; typon:dateEntered ?date_entered.
		OPTIONAL{<'''+new_isol_url+'''> typon:isolatedAt ?country. ?country rdfs:label ?country_name}
		OPTIONAL{<'''+new_isol_url+'''> typon:accession ?accession.}
		OPTIONAL{<'''+new_isol_url+'''> typon:ST ?st.} 
		OPTIONAL{<'''+new_isol_url+'''> typon:sampleCollectionDate ?col_date.}
		OPTIONAL{<'''+new_isol_url+'''> typon:host ?host.}
		OPTIONAL{<'''+new_isol_url+'''> typon:hostDisease ?host_disease.}
		OPTIONAL{<'''+new_isol_url+'''> <http://www.w3.org/2003/01/geo/wgs84_pos#lat> ?lat.}
		OPTIONAL{<'''+new_isol_url+'''> <http://www.w3.org/2003/01/geo/wgs84_pos#long> ?long.} 
		OPTIONAL{<'''+new_isol_url+'> typon:isolationSource ?isol_source.} }'
		result_meta = get_data(virtuoso_server,query)
		
		result_meta=result_meta["results"]["bindings"][0]
		
		metadataNotUploadable={}
		metadataUploadable=0
		
		country_name=False
		try:
			#if already this value country already exists for isolate
			aux=result_meta['country']['value']
		except:
			try:
				country_name=(args['country']).lower()
			except:
				pass
		
		
		data2sendlist=[]
		
		#########
		#if metadata already on database, skip the new one
		#if metadata provided, insert in RDF
		
		#accession check
		try:
			aux=result_meta['accession']['value']
		except:
			try:
				#TODO check if accession exists
				
				#check if accession exists in ENA
				print("checking accession...")
				accession=args['accession']
				#accessionTooSmall
				if len(accession)<5:
					metadataNotUploadable['accession']=accession
					
				else:
					existsInENA=get_read_run_info_ena(accession)
					print("Found in ena: "+str(existsInENA))
					
					if existsInENA:
						data2sendlist.append(' typon:accession <https://www.ebi.ac.uk/ena/data/view/'+accession+'>')
						metadataUploadable+=1
					else:
						existsInSRA=get_read_run_info_sra(accession)
						print("Found in sra: "+str(existsInSRA))
						if existsInSRA:
							data2sendlist.append(' typon:accession <https://www.ncbi.nlm.nih.gov/sra/'+accession+'>')
							metadataUploadable+=1
						else:
							metadataNotUploadable['accession']=accession
			except :
				pass
		
		#st check
		try:
			aux=result_meta['st']['value']
		except:
			try:
				data2sendlist.append(' typon:ST "'+args['st']+'"^^xsd:integer')
				metadataUploadable+=1
			except:
				pass
		
		#collection date check
		try:
			aux=result_meta['col_date']['value']
		except:
			try:
				col_date=args['coldate']
				try:
					col_date=str(datetime.datetime.strptime(col_date, '%Y-%m-%d'))
					data2sendlist.append(' typon:sampleCollectionDate "'+col_date+'"^^xsd:dateTime')
					metadataUploadable+=1
				except:
					metadataNotUploadable['coldate']=col_date
			except:
				pass
		
		#host check
		try:
			aux=result_meta['host']['value']
		except:
			try:
				
				#get the taxon id from uniprot, if not found metadata not added
				#capitalize the first letter as per scientific name notation
				hostname=(args['host']).capitalize()
				print("host name: "+hostname)
				
				#query is made to the scientific name first, then common name and then other name
				query='PREFIX up:<http://purl.uniprot.org/core/> PREFIX taxon:<http://purl.uniprot.org/taxonomy/> PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> SELECT ?taxon FROM  <http://sparql.uniprot.org/taxonomy> WHERE{	OPTIONAL{?taxon a up:Taxon; up:scientificName "'+hostname+'" } OPTIONAL{?taxon a up:Taxon; up:commonName "'+hostname+'" } OPTIONAL{?taxon a up:Taxon; up:otherName "'+hostname+'" } .}'
				
				print ("searching on host..")
				
				result2 = get_data(uniprot_server,query)
				try:
					url=result2["results"]["bindings"][0]['taxon']['value']
					data2sendlist.append(' typon:host <'+url+'>')
					metadataUploadable+=1
					print("host taxon found")
					
				except:
					#not found, lets try the query without capitalized first letter
					print("host name not found: "+hostname)
					hostname=args['host']
					print("Trying host name without first capitalized letter: "+hostname)
					
					query='PREFIX up:<http://purl.uniprot.org/core/> PREFIX taxon:<http://purl.uniprot.org/taxonomy/> PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> SELECT ?taxon FROM  <http://sparql.uniprot.org/taxonomy> WHERE{	OPTIONAL{?taxon a up:Taxon; up:scientificName "'+hostname+'" } OPTIONAL{?taxon a up:Taxon; up:commonName "'+hostname+'" } OPTIONAL{?taxon a up:Taxon; up:otherName "'+hostname+'" } .}'
				
					print ("searching on uniprot..")
					
					result2 = get_data(uniprot_server,query)
					try:
						url=result2["results"]["bindings"][0]['taxon']['value']
						data2sendlist.append(' typon:host <'+url+'>')
						metadataUploadable+=1
						print("host taxon found")
					
					except:
						print("no host names found for: "+hostname)
						metadataNotUploadable['host']=hostname
						print("species name not found on uniprot, search on http://www.uniprot.org/taxonomy/")
						pass

			except:
				pass
		
		#host disease check
		try:
			aux=result_meta['host_disease']['value']
		except:
			try:
				host_disease_ID=args['host_disease']
				#TODO check if exists
				
				host_disease_URI='http://purl.obolibrary.org/obo/DOID_'+host_disease_ID
				
				print("checking disease...")
				disease_found=check_disease_resource(host_disease_URI)
				
				print("disease found: "+str(disease_found))
				
				if disease_found:
					
					data2sendlist.append(' typon:hostDisease <'+host_disease_URI+'>')
					metadataUploadable+=1
				else:
					print(host_disease_URI+ " is not existant")
					metadataNotUploadable['host_disease']=host_disease_ID
			except Exception as e:
				print(e)
				pass
		
		#isolation source check
		try:
			aux=result_meta['isol_source']['value']
		except:
			try:
				isol_source=args['isol_source']
				data2sendlist.append(' typon:isolationSource "'+isol_source+'"^^xsd:string')
				metadataUploadable+=1
			except:
				pass
		
		#longitude check
		try:
			aux=result_meta['long']['value']
		except:
			try:
				longitude=args['long']
				try:
					latitude=float(longitude)
					data2sendlist.append(' <http://www.w3.org/2003/01/geo/wgs84_pos#long> "'+str(longitude)+'"^^xsd:long')
					metadataUploadable+=1
				except:
					metadataNotUploadable['long']=longitude
			except:
				pass
		
		#latitude check
		try:
			aux=result_meta['lat']['value']
		except:
			try:
				latitude=args['lat']
				try:
					latitude=float(latitude)
					data2sendlist.append(' <http://www.w3.org/2003/01/geo/wgs84_pos#lat> "'+str(latitude)+'"^^xsd:long')
					metadataUploadable+=1
				except:
					metadataNotUploadable['lat']=latitude
			except Exception as e:
				print(e)
				pass
		
				
		#country check
		if country_name:
			#search for country on dbpedia, first query may work for some and not for others, try with netherlands for instance
			query='select  ?country ?label where {?country a <http://dbpedia.org/class/yago/WikicatMemberStatesOfTheUnitedNations>; a dbo:Country; <http://www.w3.org/2000/01/rdf-schema#label> ?label. FILTER (lang(?label) = "en") FILTER (STRLANG("'+country_name+'", "en") = LCASE(?label) ) }'
			print ("searching country on dbpedia..")
			
			result = get_data(dbpedia_server,query)
			try:
				country_url=result["results"]["bindings"][0]['country']['value']
				label=result["results"]["bindings"][0]['label']['value']
				data2sendlist.append('typon:isolatedAt <'+country_url+'>.<'+country_url+'> rdfs:label "'+label+'"@en')
				metadataUploadable+=1
			except:
				try:
					query='select  ?country ?label where {?country a <http://dbpedia.org/class/yago/WikicatMemberStatesOfTheUnitedNations>; <http://www.w3.org/2000/01/rdf-schema#label> ?label; a dbo:Country; dbo:longName ?longName. FILTER (lang(?longName) = "en") FILTER (STRLANG("'+country_name+'", "en") = LCASE(?longName) ) }'
			
					print ("searching on dbpedia for the long name..")
					result = get_data(dbpedia_server,query)
					country_url=result["results"]["bindings"][0]['country']['value']
					label=result["results"]["bindings"][0]['label']['value']
					data2sendlist.append('typon:isolatedAt <'+country_url+'>.<'+country_url+'> rdfs:label "'+label+'"@en')
					metadataUploadable+=1
				except:
					print("Metadata not added, "+str(country_name)+" not found on dbpedia search on http://dbpedia.org/page/Category:Member_states_of_the_United_Nations")
					metadataNotUploadable['country']=country_name
					pass
			
		
		
		print(metadataNotUploadable)
		
		#if there is metadata to add or metadata to add and not passing the checks
		if len(data2sendlist)>0 or len(list(metadataNotUploadable.keys()))>0:
			
			#if there is metadata to add, build the rdf and send to virtuoso	
			if len(data2sendlist)>0:
				rdf2send=";".join(data2sendlist)

				result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_isol_url+'>'+rdf2send+'.}')

				if result.status_code > 201 :
					return "Sum Thing Wong uploading metadata to isolate", result.status_code
				
			def generate():
				yield '{"Uploaded_total": ['+str(metadataUploadable)+'],'

				
				yield '"Not_uploaded": ['
				
				auxkeys=list(metadataNotUploadable.keys())
				if len(auxkeys)<1:
					yield ']}'
				else:
					
					prev_item={}
					try:
						aux=auxkeys.pop(0)
						prev_item[aux]=metadataNotUploadable[aux]
					except Exception as e:
						print(e)
						yield ']}'
						
					for k in auxkeys:
						yield json.dumps(prev_item)+','
						prev_item={k:metadataNotUploadable[k]}
					yield json.dumps(prev_item)+']}'
			r = Response(stream_with_context(generate()), content_type='application/json')
			
			if metadataUploadable>0:
				r.headers.set('Metadata-Uploaded',True)
			else:
				r.headers.set('Metadata-Uploaded',False)
			return r
				
		else:
			return "No metadata to upload", 409
	
#@app.route('/NS/species/<int:spec_id>/isolates/<string:isol_id>/alleles')
class IsolatesAllelesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/isolates/<string:isol_id>/alleles
	def get(self, spec_id, isol_id):
		
		#return all alleles from the isolate
		new_isol_url=baseURL+"species/"+str(spec_id)+"/isolates/"+str(isol_id)
		
		#get all alleles from the isolate, independent of schema
		result = get_data(virtuoso_server,'select ?alleles  where { <'+new_isol_url+'> a typon:Isolate; typon:hasAllele ?alleles.  }')
		try:
			return (result["results"]["bindings"])
		except:
			return []

#@app.route('/NS/species/<int:spec_id>/isolates/<string:isol_id>/schemas/<int:id>')
class IsolatesProfileAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/isolates/<int:isol_id>/schemas/<int:id>
	def get(self, spec_id, isol_id,id):
		
		spec_uri=baseURL+"species/"+str(spec_id)
		isol_url=spec_uri+"/isolates/"+str(isol_id)
		
		#get species to build schema uri
		#~ result = get_data(virtuoso_server,'select ?taxon  where {<'+isol_url+'> typon:isFromTaxon <'+spec_uri+'>.}')
		#~ try:
			#~ species_uri = result["results"]["bindings"][0]['taxon']['value']
		#~ except:
			#~ return "Species not found for that isolate", 404
		
		#check if schema exists for that species
		schema_uri=spec_uri+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'ASK where { <'+schema_uri+'> a typon:Schema. FILTER NOT EXISTS { <'+schema_uri+'> typon:deprecated  "true"^^xsd:boolean }}')
		
		if not result['boolean'] :
			return "Schema "+schema_uri+" not found or deprecated" , 404
		
		#~ query='select ?id (str(?name) as ?name)  where { ?locus a typon:Locus; typon:name ?name. OPTIONAL{<'+isol_url+'> typon:hasAllele ?alleles. ?alleles typon:id ?id; typon:isOfLocus ?locus.}} order by (?name)'
		#get the alleles specific to that schema, deprecated alleles are removed
		#query='select ?id (str(?name) as ?name)  where {<'+schema_uri+'> typon:hasSchemaPart ?part.?part typon:hasLocus ?locus. ?locus typon:name ?name. OPTIONAL{<'+isol_url+'> typon:hasAllele ?alleles. ?alleles typon:id ?id; typon:isOfLocus ?locus.} FILTER NOT EXISTS { ?part typon:deprecated  "true"^^xsd:boolean }.}'
		query='select ?id (str(?name) as ?name) where { <'+isol_url+'> typon:hasAllele ?alleles. ?alleles typon:id ?id; typon:isOfLocus ?locus. {select ?locus ?name  where {<'+schema_uri+'> typon:hasSchemaPart ?part.?part typon:hasLocus ?locus. ?locus typon:name ?name. FILTER NOT EXISTS { ?part typon:deprecated  "true"^^xsd:boolean }.}}}'
		result = get_data(virtuoso_server,query) 
		
		try:
			return (result["results"]["bindings"])
		except:
			return []

#@app.route('/NS/species/<int:spec_id>/isolates/<string:isol_id>/loci/<int:id>')
class IsolatesLociAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/isolates/<int:isol_id>/loci/<int:id>
	
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('allele_id', dest= 'allele_id',
								   required=True,
								   type=int,
								   help='Id of the allele to add')
	
	@auth_token_required
	def post(self, spec_id, isol_id,locus_id):
		
		args = self.reqparse.parse_args(strict=True)
		
		alleleId=args['allele_id']
		
		spec_uri=baseURL+"species/"+str(spec_id)
		isol_url=spec_uri+"/isolates/"+str(isol_id)
		
		#check if isolate belongs to the user that is submitting the post
		#~ userid=1
		userid=g.identity.user.id
		new_user_url=baseURL+"users/"+str(userid)
		result = get_data(virtuoso_server,'ASK where { <'+isol_url+'> typon:sentBy <'+new_user_url+'>.}')
		if not result['boolean'] :
			return "Isolate not yours", 403
		
		#check if locus exists
		locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(locus_id)
		result = get_data(virtuoso_server,'ASK where { <'+locus_url+'> a typon:Locus}')
		if not result['boolean']:
			return "Locus not found", 404
		
		#check if locus already exists on isolate
		result = get_data(virtuoso_server,'ASK where { <'+isol_url+'> typon:hasAllele ?alleles.?alleles typon:isOfLocus <'+locus_url+'>.}')
		if result['boolean']:
			return "An allele was already attributed to that locus to that isolate", 409
		
		#check if allele exists
		allele_uri=locus_url+'/alleles/'+str(alleleId)
		result = get_data(virtuoso_server,'ASK where { <'+locus_url+'> a typon:Locus; typon:hasDefinedAllele <'+allele_uri+'> }')
		if not result['boolean']:
			return "Allele does not exist for that locus", 404
		
		rdf_2_ins='PREFIX typon: <http://purl.phyloviz.net/ontology/typon#> \nINSERT DATA IN GRAPH '+defaultgraph+' {<'+isol_url+'> typon:hasAllele <'+allele_uri+'>.}'
		
		print(rdf_2_ins)
				
		result = send_data(rdf_2_ins)

		if result.status_code == 201 :
			return "Locus and respective allele sucessfully added to isolate", 201	
		else:
			return "Sum Thing Wong", result.status_code


#### ---- AUXILIARY METHODS ---- ###
def check_len(arg):
	if len(arg) == 0:
		abort(400)
	elif len(arg) > 30000:
		abort(400)

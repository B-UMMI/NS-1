import datetime
from app import db, app, virtuoso_server,uniprot_server, celery
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

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

baseURL=app.config['BASE_URL']
defaultgraph=app.config['DEFAULTHGRAPH']
virtuoso_user=app.config['VIRTUOSO_USER']
virtuoso_pass=app.config['VIRTUOSO_PASS']
url_send_local_virtuoso=app.config['URL_SEND_LOCAL_VIRTUOSO']

#### ---- AUX FUNCTIONS ---- ###


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
		server.setTimeout(40)
		result = server.query().convert()
	except Exception as e:
		time.sleep(5)
		try:
			server.setQuery(sparql_query)
			server.setReturnFormat(JSON)
			result = server.query().convert()
		except Exception as e:
			result=e
		
	return result

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

	else:
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_allele_url+'> a typon:Allele; typon:sentBy  <'+new_user_url+'> ;typon:isOfLocus <'+new_locus_url+'>; typon:dateEntered "'+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+'"^^xsd:dateTime; typon:id "'+str(number_alleles_loci+1)+'"^^xsd:integer ; typon:hasSequence <'+new_seq_url+'>. <'+new_locus_url+'> typon:hasDefinedAllele <'+new_allele_url+'>.}')
	
	if result.status_code > 201 :
		return "Sum Thing Wong creating sequence", result.status_code
	else:
		return new_allele_url, result.status_code

	
#queue to add locus do schema
@celery.task(time_limit=20)
def add_locus_schema(new_schema_url,new_locus_url):	
	#get number of loci on schema and build the uri based on that number+1
	result = get_data(virtuoso_server,'select (COUNT(?parts) as ?count) where { <'+new_schema_url+'> typon:hasSchemaPart ?parts. }')
	number_schema_parts=int(result["results"]["bindings"][0]['count']['value'])
	
	new_schema_part_url=new_schema_url+"/loci/"+str(number_schema_parts+1)
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

#@app.route('/NS', methods=['GET'])
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
		
		#count number of users on virtuoso
		result = get_data(virtuoso_server,'select (COUNT(?user) as ?count) where {?user a <http://xmlns.com/foaf/0.1/Agent>. }')
		number_users_vir=int(result["results"]["bindings"][0]['count']['value'])
		
		helloStr+=" AUTHORS: Mickael Silva, António Paulo \n\n EMAIL: mickaelsilva@medicina.ulisboa.pt"
		
		helloStr+="\n\n DATE: "+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')) +"\n\n NUMBER OF SEQUENCES: "+ str(number_sequences_vir)+"\n\n NUMBER OF SPECIES: "+ str(number_species_vir)+"\n\n NUMBER OF USERS: "+ str(number_users_vir)
		
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
		
			print (genomeName)
			isolateUri=False
			#check if genome is already present
			result=[]
			result = get_data(virtuoso_server,'ASK where { ?isolate a typon:Isolate; typon:name "'+genomeName+'"^^xsd:string.}')
			genesAlreadyAttr=[]
			
			try:
				result['boolean']
			except:
				return "Profile not uploaded,try again " , 400
			
			if result['boolean']:
				
				#genome is present check if belongs to submitter
				result=[]
				result = get_data(virtuoso_server,'ASK where { ?isolate a typon:Isolate; typon:name "'+genomeName+'"^^xsd:string; typon:sentBy <'+new_user_url+'>.}')
				
				
				try:
					result['boolean']
				except:
					return "Profile not uploaded,try again " , 400
				
				#genome is present and belongs to user, get alleles already attributed
				if result['boolean']:
					result=[]
					result = get_data(virtuoso_server,'select ?locus ?isolate where { ?isolate a typon:Isolate; typon:name "'+genomeName+'"^^xsd:string; typon:hasAllele ?allele. ?allele typon:isOfLocus ?locus}')
					
					for gene in result["results"]["bindings"]:
						genesAlreadyAttr.append(str(gene['locus']['value']))
						isolateUri=str(gene['isolate']['value'])
				
				#genome is present and belongs to different user
				else:
					return "Genome "+genomeName+" already exists and belong to a different user", 403
		
			#check if genome is already on the database and which locus were already attributed
			
				#print("lala")
			
			#~ if result['boolean'] :
				#~ return genomeName+" already exists", 409
			
			#num_isolates+=1
			
			#create the new isolate id for the uri
			new_isolate_id=int(hashlib.sha256(genomeName.encode('utf-8')).hexdigest(), 16)
			
			rdf_2_ins='PREFIX typon: <http://purl.phyloviz.net/ontology/typon#> \nINSERT DATA IN GRAPH '+defaultgraph+' {\n'
			
			if not isolateUri==False:
				rdf_2_ins+='<'+isolateUri+'>'
			else:
				isolateUri=baseURL+'isolates/'+str(new_isolate_id)
				rdf_2_ins+='<'+isolateUri+'> a typon:Isolate;\ntypon:name "'+genomeName+'"^^xsd:string; typon:sentBy <'+new_user_url+'>; typon:dateEntered "'+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+'"^^xsd:dateTime; typon:isFromTaxon <'+new_spec_url+'>;'
			i=0
			hasAlleles=0
			
			#build the rdf with all alleles
			while i<len(profileDict[genomeName]):
				gene= headers[i+1]
				
				#get the allele id
				try:
					allele= int(profileDict[genomeName][i])
					hasAlleles+=1
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
				
				#if the genome has previously been sent, some alleles may already been attributed
				if loci_uri in genesAlreadyAttr:
					#~ return str(headers[i+1])+" locus already has an allele attributed for "+genomeName+", all profiles uploaded canceled",409
					hasAlleles-=1
					#~ print( str(headers[i+1])+" locus already has an allele attributed, locus not uploaded")
				
				else:
					
					#TODO check if allele actaully exists?
					
					allele_uri=loci_uri+"/alleles/"+str(allele)
					rdf_2_ins+= '\ntypon:hasAllele <'+allele_uri+'>;'
				i+=1
			
			#if the genome has alleles, send the rdf
			if hasAlleles > 0:

				#remove last semicolon from rdf
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
				return "Profile not uploaded, not enough alleles", 200
		
		
		return report

#~ class createUser(Resource):
	#~ @auth_token_required
	#~ def get(self):
		#~ 
		#~ new_mail='admin@ns.com'
		#~ new_pass='dfgvxc234gefg34qweqwesdfsqweqwe'
		#~ if not user_datastore.get_user(new_mail):
			#~ user_datastore.create_user(email=new_mail, password=new_pass)
			#~ db.session.commit()
			#~ userid=user_datastore.get_user(new_mail).id
			#~ new_user_url=baseURL+"users/"+str(userid)
			#~ result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_user_url+'> a <http://xmlns.com/foaf/0.1/Agent>.}')
			#~ r = requests.post('http://127.0.0.1:5000/login', data=json.dumps({'email':new_mail, 'password':new_pass}), headers={'content-type': 'application/json'})
			#~ print (r.json())
			#~ if result.status_code == 201 :
				#~ return "User created", 201		
			#~ else:
				#~ return "Sum Thing Wong", result.status_code
		#~ 
		#~ r = requests.post('http://127.0.0.1:5000/login', data=json.dumps({'email':new_mail, 'password':new_pass}), headers={'content-type': 'application/json'})
		#~ print (r.json())
		#~ return 'user already created'
	
	#~ @auth_token_required
	#~ def post(self):
		#~ lala=g.identity.user.id
		#~ 
		#~ return lala


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

		result = get_data(virtuoso_server,'select ?species ?name where { ?species owl:sameAs ?species2; a <http://purl.uniprot.org/core/Taxon>; typon:name ?name. } LIMIT 20')
		return (result["results"]["bindings"])

	# curl -i  http://localhost:5000/NS/species -d 'name=bacteria'
	@auth_token_required
	def post(self):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['name'])
		
		#only admin can do this
		#~ userid=1
		try:
			userid=g.identity.user.id
		except:
			return "not authorized, admin only", 405
		if userid>1:
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

#@app.route('/NS/species/<int:spec_id>/schema/<int:id>') 
class SpeciesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1
	def get(self, spec_id):
		url=baseURL+"species/"+str(spec_id)
		#result = get_data(virtuoso_server,'select ?species ?name where { <'+url+'> owl:sameAs ?species; typon:name ?name. } ')
		
		result = get_data(virtuoso_server,'select ?species ?name ?schemas ?schemaName where { {<'+url+'> owl:sameAs ?species; typon:name ?name.} UNION { ?schemas typon:isFromTaxon <'+url+'>; a typon:Schema; typon:schemaName ?schemaName.}}')
		return (result["results"]["bindings"])

#@app.route('/NS/species/<int:spec_id>/schema/<int:id>') 
class SchemaAPItypon(Resource):

	
	def get(self, spec_id,id ):
		
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'select ?description (COUNT(?part) as ?number_loci) where { <'+new_schema_url+'> typon:schemaName ?description; typon:hasSchemaPart ?part. }')
		
		try:
			finalresult=result["results"]["bindings"]
			finalresult.append({'list_loci':new_schema_url+'/loci'})
			return (finalresult)
		except:
			return []

#@app.route('/NS/species/<int:spec_id>/schema/<int:id>/compressed') 
class SchemaZipAPItypon(Resource):

	
	def get(self, spec_id,id ):
		
		#check if schema exists
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'select ?description (COUNT(?part) as ?number_loci) where { <'+new_schema_url+'> typon:schemaName ?description; typon:hasSchemaPart ?part. }')
		
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
		
		# if date is provided the request returns the alleles that were added after that specific date for all loci
		# else the request returns the list of loci
		# a correct request returns also the server date at which the request was done
		if dateAux:
			#print('select ?locus_name ?allele_id ?sequence where { { select ?locus_name ?allele_id ?sequence where {<'+new_schema_url+'> typon:hasSchemaPart ?part. ?part typon:hasLocus ?locus . ?alleles typon:isOfLocus ?locus ; typon:dateEntered ?date; typon:hasSequence ?sequence; typon:id ?allele_id. ?locus typon:name ?locus_name. FILTER ( ?date >= "'+dateAux+'"^^xsd:dateTime ). FILTER NOT EXISTS { ?part typon:deprecated  "true"^^xsd:boolean }.}order by ASC(?date)}} LIMIT 25000')
			result = get_data(virtuoso_server,'select ?locus_name ?allele_id ?sequence where { { select ?locus_name ?allele_id ?sequence where {<'+new_schema_url+'> typon:hasSchemaPart ?part. ?part typon:hasLocus ?locus . ?alleles typon:isOfLocus ?locus ; typon:dateEntered ?date; typon:hasSequence ?sequence; typon:id ?allele_id. ?locus typon:name ?locus_name. FILTER ( ?date > "'+dateAux+'"^^xsd:dateTime ). FILTER NOT EXISTS { ?part typon:deprecated  "true"^^xsd:boolean }.}order by ASC(?date)}} LIMIT 100000')
		
			#get the latest allele date
			latestAllele=(result["results"]["bindings"])[-1]
			geneFasta=latestAllele['locus_name']['value']
			alleleid=latestAllele['allele_id']['value']
			result2 = get_data(virtuoso_server,' select ?date where { ?locus typon:name "'+geneFasta+'"^^<http://www.w3.org/2001/XMLSchema#string>. ?alleles typon:isOfLocus ?locus ; typon:dateEntered ?date; typon:id '+alleleid+'. }')
			
			latestDatetime=(result2["results"]["bindings"])[0]['date']['value']
			try:
				
				def generate():
					yield '{"newAlleles": ['
					for item in result["results"]["bindings"]:
						yield json.dumps(item)+','
					yield json.dumps({'date':latestDatetime})+']}'
				
				
				
				return Response(stream_with_context(generate()), content_type='application/json')
					
				#~ #final_result=result["results"]["bindings"]
				#~ 
				#~ 
				#~ final_result=json.dumps(result["results"]["bindings"]+[latestDatetime])
				#~ print(type(final_result))
				#~ return Response(final_result,mimetype='application/json')
			except :
				return []
		else:
			result = get_data(virtuoso_server,'select ?locus (str(?name) as ?name) where { <'+new_schema_url+'> typon:hasSchemaPart ?part. ?part typon:hasLocus ?locus.?locus typon:name ?name. FILTER NOT EXISTS { ?part typon:deprecated  "true"^^xsd:boolean } }order by (?name) ')
		try:
			final_result=result["results"]["bindings"]+[str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))]
			return result["results"]["bindings"]+[str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))]
		except:
			return []
		
	
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
		result = get_data(virtuoso_server,'ASK where { <'+new_schema_url+'> a typon:Schema; typon:administratedBy <'+new_user_url+'>.}')
		if not result['boolean']:
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
			return "Sum Thing Wong creating sequence", process_result_status_code
		else:
			return new_allele_url, process_result_status_code
		
		
		#~ result = get_data(virtuoso_server,'select (COUNT(?parts) as ?count) where { <'+new_schema_url+'> typon:hasSchemaPart ?parts. }')
		#~ number_schema_parts=int(result["results"]["bindings"][0]['count']['value'])
		#~ 
		#~ new_schema_part_url=new_schema_url+"/loci/"+str(number_schema_parts+1)
		#~ result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_schema_part_url+'> a typon:SchemaPart ; typon:index "'+str(number_schema_parts+1)+'"^^xsd:int ; typon:hasLocus <'+new_locus_url+'>.<'+new_schema_url+'> typon:hasSchemaPart <'+new_schema_part_url+'>.}')
#~ 
		#~ if result.status_code == 201 :
			#~ return "Locus sucessfully added to schema", 201		
		#~ else:
			#~ return "Sum Thing Wong", result.status_code
	
	@auth_token_required
	def delete(self, spec_id, id):
		args = self.reqparse.parse_args(strict=True)
		
		try:
			args['loci_id']
		except:
			return "No valid id provided for loci: loci_id=<int>", 404
		
		#only admin can do this
		try:
			userid=g.identity.user.id
		except:
			return "not authorized, admin only", 405
		if userid>1:
			return "not authorized, admin only", 405
		#~ 
		#~ userid=1
		
		new_user_url=baseURL+"users/"+str(userid)
		
		#check if schema exists
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'ASK where { <'+new_schema_url+'> a typon:Schema; typon:administratedBy <'+new_user_url+'>.}')
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
		

#@app.route('/NS/species/<int:spec_id>/schemas') 
class SchemaListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('description', dest= 'description',
								   required=True,
								   type=str,
								   help='No valid description provided for schema')
        

	# curl -i  http://localhost:5000/NS/species/bacteria/schemas
	def get(self, spec_id):
		
		species_url=baseURL+"species/"+str(spec_id)	
		result = get_data(virtuoso_server,'select ?schemas ?name where { ?schemas a typon:Schema; typon:isFromTaxon <'+species_url+'>; typon:schemaName ?name. }')
		try:
			return (result["results"]["bindings"])
		except:
			return []

	# curl -i http://localhost:5000/NS/species/1/schemas -d 'description=interesting'
	@auth_token_required
	def post(self, spec_id):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['description'])
		
		try:
			args['description']
		except:
			return "No valid description provided", 404
		
		# check if a schema already exists with this description for this species
		species_url=baseURL+"species/"+str(spec_id)
		result = get_data(virtuoso_server,'ASK where { ?schema a typon:Schema; typon:isFromTaxon <'+species_url+'>; typon:schemaName "'+args['description']+'"^^xsd:string .}')
		if result['boolean']:
			
			result = get_data(virtuoso_server,'select ?schema where {?schema a typon:Schema; typon:isFromTaxon <'+species_url+'>; typon:schemaName "'+args['description']+'"^^xsd:string .}')
			schema_url = result["results"]["bindings"][0]['schema']['value']
			
			return schema_url, 409
		
		userid=g.identity.user.id
		new_user_url=baseURL+"users/"+str(userid)
		
		# count number of schemas on the server for the uri build and send data to server
		result = get_data(virtuoso_server,'select (COUNT(?schemas) as ?count) where { ?schemas a typon:Schema;typon:isFromTaxon <'+species_url+'>. }')
		
		number_schemas=int(result["results"]["bindings"][0]['count']['value'])
		
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(number_schemas+1)
		
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_schema_url+'> a typon:Schema; typon:isFromTaxon <'+species_url+'>; typon:administratedBy <'+new_user_url+'>; typon:schemaName "'+args['description']+'"^^xsd:string .}')
		if result.status_code == 201 :
			return new_schema_url, 201		
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
			
			new_id=int(hashlib.sha256(sequence.encode('utf-8')).hexdigest(), 16)
			new_seq_url=baseURL+"sequences/"+str(new_id)
			result = get_data(virtuoso_server,'select ?locus where {?alleles typon:hasSequence <'+new_seq_url+'>; typon:isOfLocus ?locus.?locus typon:isOfTaxon <'+spec_url+'>.}')
			try:
				return (result["results"]["bindings"])
			except:
				return []
		
		else:
			result = get_data(virtuoso_server,'select (str(?name) as ?name) ?locus where { ?locus a typon:Locus; typon:isOfTaxon <'+spec_url+'>; typon:name ?name.  }')
			
			try:
				def generate():
					yield '{"Loci": ['
					prev_item=result["results"]["bindings"][0]
					for item in result["results"]["bindings"]:
						yield json.dumps(prev_item)+','
						prev_item = item
					yield json.dumps(prev_item)+']}'
				
				return Response(stream_with_context(generate()), content_type='application/json')
				
				
			except:
				return []
		
		

	# curl -i http://localhost:5000/NS/species/1/loci -d 'aliases=macarena'
	@auth_token_required
	def post(self, spec_id):
		args = self.reqparse.parse_args(strict=True)
		try:
			check_len(args['prefix'])
		except:
			return "provide prefix", 400
		#only admin can do this
		userid=g.identity.user.id
		if userid>1:
			return "not authorized, admin only", 405
		
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
		aliases=args['prefix']+"%05d" % (newLocusId,)+".fasta"
		
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(newLocusId)
		
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
		result = get_data(virtuoso_server,'select ?allele_id (str(?nucSeq) as ?nucSeq) where { <'+new_locus_url+'> a typon:Locus; typon:name ?name. ?alleles typon:isOfLocus <'+new_locus_url+'> .?alleles typon:hasSequence ?sequence; typon:id ?allele_id .?sequence typon:nucleotideSequence ?nucSeq. } order by ASC(?allele_id)')
		#~ response=result["results"]["bindings"]
		
		#~ for allele in response:
			#~ print (allele['allele_id']['value'])
			#~ print (allele['nucSeq']['value'])
		
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
						prev_item=result["results"]["bindings"][0]
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
				prev_item=result["results"]["bindings"][0]
				for item in result["results"]["bindings"]:
					yield json.dumps(prev_item)+','
					prev_item = item
				yield json.dumps(prev_item)+']}'
			
			return Response(stream_with_context(generate()), content_type='application/json')
		
		
		except:
			return []
		return result["results"]["bindings"]

#@app.route('/NS/species/<int:spec_id>/loci/<int:id>')
class LociAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1/loci/7
	def get(self, spec_id, id):
		
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(id)
		result = get_data(virtuoso_server,'select (str(?name) as ?name) (COUNT(?alleles) as ?number_alleles) (AVG(strlen(str(?nucSeq)))as ?average_length) (MIN(strlen(str(?nucSeq)))as ?min_length) (MAX(strlen(str(?nucSeq)))as ?max_length) where { <'+new_locus_url+'> a typon:Locus; typon:name ?name; typon:hasDefinedAllele ?alleles.?alleles typon:hasSequence ?sequence.?sequence typon:nucleotideSequence ?nucSeq.}')

		response=result["results"]["bindings"]
		response.append({'alleles':new_locus_url+'/alleles'})
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

	# curl -i http://localhost:5000/NS/species/1/loci/7/alleles
	def get(self, spec_id, loci_id):

		#get list of alleles from that locus
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(loci_id)
		result = get_data(virtuoso_server,'select ?alleles where { <'+new_locus_url+'> a typon:Locus; typon:hasDefinedAllele ?alleles. ?alleles typon:id ?id }ORDER BY ASC(?id)')
		try:
			return (result["results"]["bindings"])
		except:
			return []
		


	# curl -i http://localhost:5000/NS/species/1/loci/7/alleles -d 'time_stamp=2017-07-24T17:16:59.688836' -d 'sequence=ACTCTGT'
	@auth_token_required
	def post(self, spec_id, loci_id):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['sequence'])
		
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
		try:
			proteinSequence=translateSeq(sequence,False)
		except:
			return "sequence failed to translate, not a CDS", 400
		
		
		#check if sequence is already present on locus query
		query='select ?alleles where { ?alleles typon:isOfLocus <'+new_locus_url+'>; typon:hasSequence ?seq. ?seq a typon:Sequence; typon:nucleotideSequence "'+sequence+'"^^xsd:string.}'
		
		#check if sequence is already present on the full db - TO CONSIDER FOR FUTURE IF IS WORTH
		#query='select ?seq ?alleles ?locus where { ?alleles typon:isOfLocus ?locus; typon:hasSequence ?seq. ?seq a typon:Sequence; typon:nucleotideSequence "'+sequence+'"^^xsd:string.}'


		if len(sequence) > 9000:
			result=send_big_query(virtuoso_server,query)
		else:
			result = get_data(virtuoso_server,query)
		
		#if sequence exists return the allele uri, if not create new sequence
		try :
			new_allele_url = result["results"]["bindings"][0]['alleles']['value']
			return new_allele_url, 200
		
				
			
		#sequence doesnt exist, create new and link to new allele uri. return the new allele uri
		except IndexError:
			
			
			#check if sequence exists in uniprot
			add2send2graph=''
			try:
				
				# try to translate the sequence and check if is a CDS and build the RDF with the info on uniprot
				
				proteinSequence=proteinSequence.replace("*","")
				query='PREFIX rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>  PREFIX up: <http://purl.uniprot.org/core/> PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> select ?seq ?label ?sname where { ?b a up:Simple_Sequence; rdf:value "'+proteinSequence+'". ?seq up:sequence ?b. OPTIONAL {?seq rdfs:label ?label.} OPTIONAL {?seq up:submittedName ?rname2. ?rname2 up:fullName ?sname.}}LIMIT 20'
				#~ print (query)
				result2 = get_data(uniprot_server,query)
				
				url=result2["results"]["bindings"][0]['seq']['value']
				add2send2graph+='; typon:hasUniprotSequence <'+url+'>'
				try:
					url2=result2["results"]["bindings"][0]['label']['value']
					add2send2graph+='; typon:hasUniprotLabel "'+url2+'"^^xsd:string'
				except:
					print ("no label associated")
					pass
				try:
					url2=result["results"]["bindings"][0]['sname']['value']
					rdf_2_ins+='; typon:hasUniprotSName "'+url2+'"^^xsd:string'
				except:
					#~ print ("no submitted name associated")
					pass

			#the sequence is not on uniprot or there was an error querying uniprot, just continue
			except Exception as e:
				add2send2graph=''
				#print (e)
				pass
						
			
			#build the id of the sequence hashing it
			
			new_id=int(hashlib.sha256(sequence.encode('utf-8')).hexdigest(), 16)
			
						
			# build the remaining new seq uri
			new_seq_url=baseURL+"sequences/"+str(new_id)
			
			#check if the uri with the hash is already attributed
			result = get_data(virtuoso_server,'ASK where { <'+new_seq_url+'> typon:nucleotideSequence ?seq.}')
			if result['boolean']:
				
				#check if the same sequence is attributed or there is a hash collision
				result = get_data(virtuoso_server,'ASK where { <'+new_seq_url+'> a typon:Sequence; typon:nucleotideSequence "'+sequence+'"^^xsd:string.}')
				
				#sequence was already attributed to the exact same sequence, reusing it
				if result['boolean']:
					
					#get number of alleles for locus
					#~ result = get_data(virtuoso_server,'select (COUNT(?alleles) as ?count) where { ?alleles typon:isOfLocus <'+new_locus_url+'>.}')
					#~ number_alleles_loci=int(result["results"]["bindings"][0]['count']['value'])
					#~ new_allele_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(loci_id)+"/alleles/"+str(number_alleles_loci+1)

					#add allele to virtuoso
					#~ result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_allele_url+'> a typon:Allele; typon:sentBy  <'+new_user_url+'> ;typon:isOfLocus <'+new_locus_url+'>; typon:dateEntered "'+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+'"^^xsd:dateTime; typon:id "'+str(number_alleles_loci+1)+'"^^xsd:integer ; typon:hasSequence <'+new_seq_url+'>. <'+new_locus_url+'> typon:hasDefinedAllele <'+new_allele_url+'>.}')
										
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
						return "Sum Thing Wong creating sequence", process_result_status_code
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
					return "Sum Thing Wong creating sequence", process_result_status_code
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
		result = get_data(virtuoso_server,'select ?sequence ?date ?id where { <'+new_allele_url+'> a typon:Allele; typon:dateEntered ?date; typon:hasSequence ?sequence; typon:id ?id. }')
		try:
			return (result["results"]["bindings"])
		except:
			return []	

#@app.route('/NS/sequences/<int:seq_id>')
class SequencesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/sequences/5
	def get(self, seq_id):
		
		new_seq_url=baseURL+"sequences/"+str(seq_id)
		result = get_data(virtuoso_server,'select ?sequence ?uniprot ?label where { <'+new_seq_url+'> a typon:Sequence; typon:nucleotideSequence ?sequence. OPTIONAL { <'+new_seq_url+'> typon:hasUniprotSequence ?uniprot.}. OPTIONAL{ <'+new_seq_url+'> typon:hasUniprotLabel ?label.}}')
		try:
			return (result["results"]["bindings"])
		except:
			return []

#@app.route('/NS/sequences/')
class SequencesListAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/sequences
	def get(self):
		
				
		result = get_data(virtuoso_server,'select (COUNT(?seq) as ?count) where {?seq a typon:Sequence }')
		number_sequences_vir=int(result["results"]["bindings"][0]['count']['value'])
		
		try:
			return (number_sequences_vir)
		except:
			return []

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

		try:
			return (result["results"]["bindings"])
		except:
			return []

#@app.route('/NS/species/<int:spec_id>/isolates')
class IsolatesListAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1/isolates
	
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('isolName', dest= 'isolName',
								   required=False,
								   type=str,
								   help='isolate name')
	
	def get(self, spec_id):
		
		args = self.reqparse.parse_args(strict=True)
		isolName=False
		try:
			isolName=args['isolName']
		except:
			pass
		
		#if isolate name is provided return that isolate, else return all isolates
		if isolName:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate where { ?isolate a typon:Isolate; typon:isFromTaxon <'+new_spec_url+'>; typon:name "'+isolName+'"^^xsd:string.}')
		else:
			new_spec_url=baseURL+"species/"+str(spec_id)
			result = get_data(virtuoso_server,'select ?isolate ?name where { ?isolate a typon:Isolate; typon:isFromTaxon <'+new_spec_url+'>; typon:name ?name. }')
		
		#isolates number can grow quickly, stream response is default
		try:
			def generate():
				yield '{"Isolates": ['
				prev_item=result["results"]["bindings"][0]
				for item in result["results"]["bindings"]:
					yield json.dumps(prev_item)+','
					prev_item = item
				yield json.dumps(prev_item)+']}'
			
			return Response(stream_with_context(generate()), content_type='application/json')
		
		#~ try:
			#~ return (result["results"]["bindings"])
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
		self.reqparse.add_argument('ST', dest= 'mlstst',
								   required=False,
								   type=str,
								   help='ST for traditional 7 genes MLST')
		self.reqparse.add_argument('country', dest= 'country',
								   required=True,
								   type=str,
								   help='Country from isolate')								  
	
	def get(self, isol_id):
		
		new_isol_url=baseURL+"isolates/"+str(isol_id)
		result = get_data(virtuoso_server,'select ?name ?country ?accession ?ST  where { <'+new_isol_url+'> a typon:Isolate; typon:name ?name. OPTIONAL{<'+new_isol_url+'> typon:country ?country.}OPTIONAL{<'+new_isol_url+'> typon:accession ?accession.}OPTIONAL{<'+new_isol_url+'> typon:ST ?ST.}  }')
		try:
			return (result["results"]["bindings"])
		except:
			return []
	
	@auth_token_required
	def post(self, isol_id):
		args = self.reqparse.parse_args(strict=True)
		
		#check if isolate exist
		new_isol_url=baseURL+"isolates/"+str(isol_id)
		result = get_data(virtuoso_server,'ASK where { <'+new_isol_url+'> a typon:Isolate.}')
		if not result['boolean'] :
			return "Isolate not found", 404
		
		#check if isolate exist
		result = get_data(virtuoso_server,'ASK where { <'+new_isol_url+'> typon:country ?country.}')
		if result['boolean'] :
			return "Isolate already has metada", 409
		
		#check if isolate belongs to the user that is submitting the post
		userid=g.identity.user.id
		#~ userid=1
		new_user_url=baseURL+"users/"+str(userid)
		result = get_data(virtuoso_server,'ASK where { <'+new_isol_url+'> typon:sentBy <'+new_user_url+'>.}')
		if not result['boolean'] :
			return "Isolate not yours", 403
		
		#if metadata provided, insert in RDF
		data2send=''
		try:
			data2send+=' typon:accession <'+args['accession']+'>;'
		except:
			pass
		try:
			data2send+=' typon:ST "'+args['mlstst']+'"^^xsd:integer;'
		except:
			pass
		try:
			data2send+=' typon:country "'+args['country']+'"^^xsd:string.'
		except:
			pass

			
		if not data2send=='':
			
			result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_isol_url+'>'+data2send+'}')
			
			if result.status_code > 201 :
				return "Sum Thing Wong uploading metadata to isolate", result.status_code
			else:
				return "Metadata added", result.status_code
		else:
			return "No metadata to upload", 400
	
#@app.route('/NS/species/<int:spec_id>/isolates/<string:isol_id>/alleles')
class IsolatesAllelesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/isolates/<string:isol_id>/alleles
	def get(self, isol_id):
		
		#return all alleles from the isolate
		new_isol_url=baseURL+"isolates/"+str(isol_id)
		result = get_data(virtuoso_server,'select ?alleles  where { <'+new_isol_url+'> a typon:Isolate; typon:hasAllele ?alleles.  }')
		try:
			return (result["results"]["bindings"])
		except:
			return []

#@app.route('/NS/species/<int:spec_id>/isolates/<string:isol_id>/schemas/<int:id>')
class IsolatesProfileAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/isolates/<int:isol_id>/schemas/<int:id>
	def get(self, isol_id,id):
		
		isol_url=baseURL+"isolates/"+str(isol_id)
		
		#get species to build schema uri
		result = get_data(virtuoso_server,'select ?taxon  where {<'+isol_url+'> typon:isFromTaxon ?taxon.}')
		try:
			species_uri = result["results"]["bindings"][0]['taxon']['value']
		except:
			return "Species not found for that isolate", 404
		
		#check if schema exists for that species
		schema_uri=species_uri+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'ASK where { <'+schema_uri+'> a typon:Schema.}')
		
		if not result['boolean'] :

			return "Schema "+schema_uri+" not found", 404
		
		#~ query='select ?id (str(?name) as ?name)  where { ?locus a typon:Locus; typon:name ?name. OPTIONAL{<'+isol_url+'> typon:hasAllele ?alleles. ?alleles typon:id ?id; typon:isOfLocus ?locus.}} order by (?name)'
		query='select ?id (str(?name) as ?name)  where {<'+schema_uri+'> typon:hasSchemaPart ?part.?part typon:hasLocus ?locus. ?locus typon:name ?name. OPTIONAL{<'+isol_url+'> typon:hasAllele ?alleles. ?alleles typon:id ?id; typon:isOfLocus ?locus.} FILTER NOT EXISTS { ?part typon:deprecated  "true"^^xsd:boolean }.}'
		result = get_data(virtuoso_server,query) 
		
		try:
			return (result["results"]["bindings"])
		except:
			return []

#### ---- AUXILIARY METHODS ---- ###
def check_len(arg):
	if len(arg) == 0:
		abort(400)
	elif len(arg) > 30000:
		abort(400)

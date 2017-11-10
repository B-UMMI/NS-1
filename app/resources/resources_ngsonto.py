import datetime
from app import db, app, virtuoso_server,uniprot_server
from flask import abort,g,request
from flask_restful import Resource, reqparse, marshal, fields
from app.models.models import User, Role
from flask_security import Security, SQLAlchemyUserDatastore, auth_token_required
from SPARQLWrapper import JSON
from app.scripts.AuxFunctions import translateSeq
import requests,json

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

baseURL=app.config['BASE_URL']
defaultgraph=app.config['DEFAULTHGRAPH']
virtuoso_user=app.config['VIRTUOSO_USER']
virtuoso_pass=app.config['VIRTUOSO_PASS']

#### ---- RESOURCES ---- ###
# TODO: Error handling for duplicate DB PK data on POST
#       (atm client gets splattered with ugly error messages)

def send_data(sparql_query):
    url = 'http://localhost:8890/DAV/test_folder/data'
    headers = {'content-type': 'application/sparql-query'}
    r = requests.post(url, data=sparql_query, headers=headers, auth=requests.auth.HTTPBasicAuth(virtuoso_user, virtuoso_pass))
    return r


def get_data(server,sparql_query):
	try:
		server.setQuery(sparql_query)
		server.setReturnFormat(JSON)
		result = server.query().convert()
	except Exception as e:
		result=e
		
	return result


#@app.route('/NS', methods=['GET'])

class NS(Resource):
	#~ @auth_token_required
	def get(self):
		
		return 'Hello darkness my old friend'

# curl -i  http://localhost:5000/NS/species/<int:spec_id>/profiles
class profile(Resource):
	
	
	#TODO CREATE A GET FROM PROFILES
	#~ @auth_token_required
	def post(self, spec_id):

		
		content = request.json
		
		if not content:
			return "Provide json"
		
		profileDict=content['profile']
		headers=content['headers']
		
		#~ userid=g.identity.user.id
		#~ new_user_url=baseURL+"users/"+str(userid)
		new_user_url=baseURL+"users/"+str(1)
    
		new_spec_url=baseURL+"species/"+str(spec_id)
		
		dictgenes={}
		result = get_data(virtuoso_server,'select (str(?name) as ?name) ?locus where {?locus a typon:Locus; typon:isOfTaxon <'+new_spec_url+'>; typon:name ?name. }')
		for gene in result["results"]["bindings"]:
			dictgenes[str(gene['name']['value'])]=str(gene['locus']['value'])

		result = get_data(virtuoso_server,'select (COUNT(?isol) as ?count) where {?isol a typon:Isolate }')
		num_isolates=int(result["results"]["bindings"][0]['count']['value'])
            		
		
		for genomeName in profileDict.keys():
		
			print (genomeName)
			result = get_data(virtuoso_server,'ASK where { ?isolate a typon:Isolate; typon:name "'+genomeName+'"^^xsd:string.}')
		
			if result['boolean'] :
				return genomeName+" already exists", 400
			
			num_isolates+=1
			
			rdf_2_ins='PREFIX typon: <http://purl.phyloviz.net/ontology/typon#> \nINSERT DATA IN GRAPH '+defaultgraph+' {\n'
			
			isolateUri=baseURL+'isolates/'+str(num_isolates)
			rdf_2_ins+='<'+isolateUri+'> a typon:Isolate;\ntypon:name "'+genomeName+'"^^xsd:string; typon:sentBy <'+new_user_url+'>; typon:isFromTaxon <'+new_spec_url+'>'
			i=0
			hasAlleles=0
			while i<len(profileDict[genomeName]):
				gene= headers[i+1]
				try:
					allele= int(profileDict[genomeName][i])
					hasAlleles+=1
				except:
					try:
						allele= int(profileDict[genomeName][i].replace('INF-',''))
						hasAlleles+=1
					except:
						i+=1
						continue
					#~ print row[i]

				try:
					loci_uri= dictgenes[headers[i+1]]
				except:
					#~ print ("locus is not on db")
					return str(headers[i+1])+" locus was not found, profile not uploaded",400
				
				
				allele_uri=loci_uri+"/alleles/"+str(allele)
				rdf_2_ins+= ';\ntypon:hasAllele <'+allele_uri+'>'
				i+=1
			
			if hasAlleles > 0:
				#~ print (rdf_2_ins)
				#~ asd
				result=send_data(rdf_2_ins+".}")
				print (genomeName, str(result.status_code))
				return "Profile successfully uploaded", 200
				
			else:
				num_isolates-=1    
				return "Profile not uploaded, not enough alleles", 200
		
		
		return report

class createUser(Resource):
	#~ @auth_token_required
	def get(self):
		
		new_mail='test@example.com'
		new_pass='adasdasd'
		if not user_datastore.get_user(new_mail):
			user_datastore.create_user(email=new_mail, password='adasdasd')
			db.session.commit()
			userid=user_datastore.get_user(new_mail).id
			new_user_url=baseURL+"users/"+str(userid)
			result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_user_url+'> a <http://xmlns.com/foaf/0.1/Agent>.}')
			
			if result.status_code == 201 :
				return "User created", 201		
			else:
				return "Sum Thing Wong", result.status_code
		
		return 'user already created'
	
	@auth_token_required
	def post(self):
		lala=g.identity.user.id
		
		return lala


class SpeciesListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()
		self.reqparse.add_argument('name', dest= 'name',
								   required=True,
								   type=str,
								   help='No valid name provided for species')

	# curl -i  http://localhost:5000/NS/species
	#~ @auth_token_required
	def get(self):

		result = get_data(virtuoso_server,'select ?species where { ?species owl:sameAs ?species2. ?species2 a <http://purl.uniprot.org/core/Taxon> } LIMIT 20')
		return (result["results"]["bindings"])

	# curl -i  http://localhost:5000/NS/species -d 'name=bacteria'
	#~ @auth_token_required
	def post(self):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['name'])
		
		#get number of taxon already on the graph
		result = get_data(virtuoso_server,'select (COUNT(?taxon) as ?count) where { ?taxon a <http://purl.uniprot.org/core/Taxon> }')
		number_taxon=int(result["results"]["bindings"][0]['count']['value'])
		
		#get the taxon id from uniprot
		query='PREFIX up:<http://purl.uniprot.org/core/> PREFIX taxon:<http://purl.uniprot.org/taxonomy/> PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> SELECT ?taxon FROM  <http://sparql.uniprot.org/taxonomy> WHERE{	?taxon a up:Taxon; rdfs:subClassOf taxon:2; up:scientificName "'+args['name']+'" .}'
		print ("searching on uniprot..")
		
		result2 = get_data(uniprot_server,query)
		#~ print (result2)
		try:
			url=result2["results"]["bindings"][0]['taxon']['value']
		except:
			return "species name not found on uniprot, search on http://www.uniprot.org/taxonomy/"
		
		result = get_data(virtuoso_server,'ASK where { ?species owl:sameAs <'+url+'>}')
		if result['boolean']:
			return "Species already exists", 409
		
		
		new_spec_url=baseURL+"species/"+str(number_taxon+1)
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_spec_url+'> owl:sameAs <'+url+'>; typon:name "'+args['name']+'"^^xsd:string ; a <http://purl.uniprot.org/core/Taxon>.}')

		if result.status_code == 201 :
			return "Done", 201		
		else:
			return "Sum Thing Wong", result.status_code


class SpeciesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria
	def get(self, spec_id):
		url=baseURL+"species/"+str(spec_id)
		result = get_data(virtuoso_server,'select ?species ?name where { <'+url+'> owl:sameAs ?species; typon:name ?name. } ')
		return (result["results"]["bindings"])

#@app.route('/NS/species/<int:spec_id>/schema/<int:id>') 
class SchemaAPItypon(Resource):

	def get(self, spec_id,id ):
		
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'select ?description where { <'+new_schema_url+'> typon:schemaName ?description. }')
		try:
			return (result["results"]["bindings"])
		except:
			return []


#@app.route('/NS/species/<int:spec_id>/schema/<int:id>/loci') 
class SchemaLociAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()
		
		self.reqparse.add_argument('loci_id', dest= 'loci_id',
								   required=True,
								   type=int,
								   help='No valid id provided for loci')
		#~ super(SchemaLociAPI, self).__init__()

	def get(self, spec_id,id ):
		
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'select ?locus where { <'+new_schema_url+'> typon:hasSchemaPart ?part. ?part typon:hasLocus ?locus. }')
		try:
			return (result["results"]["bindings"])
		except:
			return []
		
	
	#~ @auth_token_required
	def post(self, spec_id, id):
		
		args = self.reqparse.parse_args(strict=True)
		
		#check if schema exists
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(id)
		result = get_data(virtuoso_server,'ASK where { <'+new_schema_url+'> a typon:Schema}')
		if not result['boolean']:
			return "Schema not found", 404
		
		#check if locus exists
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(args['loci_id'])
		result = get_data(virtuoso_server,'ASK where { <'+new_locus_url+'> a typon:Locus}')
		if not result['boolean']:
			return "Locus not found", 404
				
		result = get_data(virtuoso_server,'select (COUNT(?parts) as ?count) where { <'+new_schema_url+'> typon:hasSchemaPart ?parts. }')
		number_schema_parts=int(result["results"]["bindings"][0]['count']['value'])
		
		new_schema_part_url=new_schema_url+"/loci/"+str(number_schema_parts+1)
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_schema_part_url+'> a typon:SchemaPart ; typon:index "'+str(number_schema_parts+1)+'"^^xsd:int ; typon:hasLocus <'+new_locus_url+'>.<'+new_schema_url+'> typon:hasSchemaPart <'+new_schema_part_url+'>.}')

		if result.status_code == 201 :
			return "Done", 201		
		else:
			return "Sum Thing Wong", result.status_code
		

#@app.route('/NS/species/<int:spec_id>/schema') 
class SchemaListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('description', dest= 'description',
								   required=True,
								   type=str,
								   help='No valid description provided for schema')

	# curl -i  http://localhost:5000/NS/species/bacteria/schema
	def get(self, spec_id):
		result = get_data(virtuoso_server,'select ?schemas ?name where { ?schemas a typon:Schema; typon:schemaName ?name. }')
		try:
			return (result["results"]["bindings"])
		except:
			return []

	# curl -i http://localhost:5000/NS/species/1/schema -d 'description=interesting'
	#~ @auth_token_required
	def post(self, spec_id):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['description'])
		
		result = get_data(virtuoso_server,'select (COUNT(?schemas) as ?count) where { ?schemas a typon:Schema. }')
		
		number_schemas=int(result["results"]["bindings"][0]['count']['value'])
		
		#check if schema already exists with description
		new_schema_url=baseURL+"species/"+str(spec_id)+"/schemas/"+str(number_schemas+1)
		result = get_data(virtuoso_server,'ASK where { ?schema a typon:Schema; typon:schemaName "'+args['description']+'"^^xsd:string .}')
		if result['boolean']:
			return "Already exists", 409
		
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_schema_url+'> a typon:Schema; typon:schemaName "'+args['description']+'"^^xsd:string .}')
		if result.status_code == 201 :
			return "Done", 201		
		else:
			return "Sum Thing Wong", result.status_code

class LociListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('aliases', dest= 'aliases',
								   required=True,
								   type=str,
								   help='No valid aliases provided for loci')

		#~ super(LociListAPI, self).__init__()

	# curl -i http://localhost:5000/NS/species/1/loci
	def get(self, spec_id):
		spec_url=baseURL+"species/"+str(spec_id)
		result = get_data(virtuoso_server,'select (str(?name) as ?name) ?locus where { ?locus a typon:Locus; typon:isOfTaxon <'+spec_url+'>; typon:name ?name.  }')
		try:
			return (result["results"]["bindings"])
		except:
			return []

	# curl -i http://localhost:5000/NS/species/1/loci -d 'aliases=macarena'
	#~ @auth_token_required
	def post(self, spec_id):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['aliases'])
		
		spec_url=baseURL+"species/"+str(spec_id)
		result = get_data(virtuoso_server,'ASK where { <'+spec_url+'> a <http://purl.uniprot.org/core/Taxon>}')
		
		
		if not result['boolean'] :

			return "Species not found", 404
		
		#check if already exists locus with that aliases
		result = get_data(virtuoso_server,'ASK where { ?locus a typon:Locus; typon:name "'+args['aliases']+'"^^xsd:string.}')
		
		
		if result['boolean'] :

			return "Locus already exists", 409
		
		#count number of loci already present
		result = get_data(virtuoso_server,'select (COUNT(?locus) as ?count) where { ?locus a typon:Locus; typon:isOfTaxon <'+spec_url+'>. }')
		number_loci_spec=int(result["results"]["bindings"][0]['count']['value'])
		
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(number_loci_spec+1)
		
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_locus_url+'> a typon:Locus; typon:name "'+args['aliases']+'"^^xsd:string; typon:isOfTaxon <'+spec_url+'> .}')

		if result.status_code == 201 :
			return new_locus_url, 201		
		else:
			return "Sum Thing Wong", result.status_code


class LociFastaAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1/loci/7/fasta
	def get(self, spec_id, id):
		
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(id)
		result = get_data(virtuoso_server,'select (str(?name) as ?locus_name) ?allele_id (str(?nucSeq) as ?nucSeq) where { <'+new_locus_url+'> a typon:Locus; typon:name ?name. ?alleles typon:isOfLocus <'+new_locus_url+'> .?alleles typon:hasSequence ?sequence; typon:id ?allele_id .?sequence typon:nucleotideSequence ?nucSeq. }')
		
		response=result["results"]["bindings"]
		#~ print (response)
		#~ for allele in response:
			#~ print (allele['allele_id']['value'])
			#~ print (allele['nucSeq']['value'])
		
		return response

class LociAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1/loci/7
	def get(self, spec_id, id):
		
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(id)
		result = get_data(virtuoso_server,'select distinct (str(?name) as ?locus_name) where { <'+new_locus_url+'> a typon:Locus; typon:name ?name. ?alleles typon:isOfLocus <'+new_locus_url+'> . }')

		response=result["results"]["bindings"]
		
		try:
			return (response)
		except:
			return []

class AlleleListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('sequence', dest= 'sequence',
								   required=True,
								   type=str,
								   help='No valid sequence provided for allele')

	# curl -i http://localhost:5000/NS/species/1/loci/7/alleles
	def get(self, spec_id, loci_id):
		# Check if loci associated with species exists on the database 
				
		new_locus_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(loci_id)
		result = get_data(virtuoso_server,'select ?alleles where { <'+new_locus_url+'> a typon:Locus; typon:hasDefinedAllele ?alleles. }')
		try:
			return (result["results"]["bindings"])
		except:
			return []
		


	# curl -i http://localhost:5000/NS/species/1/loci/7/alleles -d 'time_stamp=2017-07-24T17:16:59.688836' -d 'sequence=ACTCTGT'
	#~ @auth_token_required
	def post(self, spec_id, loci_id):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['sequence'])
		
		#~ userid=g.identity.user.id
		#~ new_user_url=baseURL+"users/"+str(userid)
		new_user_url=baseURL+"users/"+str(1)
		
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
		
		#get number of alleles for locus
		result = get_data(virtuoso_server,'select (COUNT(?alleles) as ?count) where { ?alleles typon:isOfLocus <'+new_locus_url+'>.}')
		number_alleles_loci=int(result["results"]["bindings"][0]['count']['value'])
		new_allele_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(loci_id)+"/alleles/"+str(number_alleles_loci+1)

		#check if sequence is already present
		result = get_data(virtuoso_server,'select ?alleles where { ?alleles typon:isOfLocus <'+new_locus_url+'>; typon:hasSequence ?seq. ?seq a typon:Sequence; typon:nucleotideSequence "'+args['sequence']+'"^^xsd:string.}')
				
		
		#if sequence exists return the allele uri, if not create new sequence
		try :
			new_allele_url = result["results"]["bindings"][0]['alleles']['value']
			return new_allele_url, 201
		
				
			
		#sequence doesnt exist, create new and link to new allele uri. return the new allele uri
		except IndexError:
			
			#check if sequence exists in uniprot
			add2send2graph=''
			try:
				proteinSequence=translateSeq(args['sequence'],False)
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
					print ("no submitted name associated")
					pass

			except Exception as e:
				add2send2graph=''
			
			
			result = get_data(virtuoso_server,'select (COUNT(?seq) as ?count) where {?seq a typon:Sequence }')
			number_sequences=int(result["results"]["bindings"][0]['count']['value'])
			new_seq_url=baseURL+"sequences/"+str(number_sequences+1)
			result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_seq_url+'> a typon:Sequence '+add2send2graph+' ; typon:nucleotideSequence "'+args['sequence']+'"^^xsd:string.<'+new_allele_url+'> a typon:Allele; typon:sentBy  <'+new_user_url+'> ;typon:isOfLocus <'+new_locus_url+'>; typon:dateEntered "'+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+'"^^xsd:dateTime; typon:id "'+str(number_alleles_loci+1)+'"^^xsd:integer ; typon:hasSequence <'+new_seq_url+'>. <'+new_locus_url+'> typon:hasDefinedAllele <'+new_allele_url+'>.}')
		
			if result.status_code != 201 :
				return "Sum Thing Wong creating sequence", result.status_code
			else:
				return new_allele_url, result.status_code
		except Exception as e:
			return "Sum Thing Wong creating sequence", 400
		
		

class AlleleAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria/loci/7/alleles/7
	def get(self, spec_id, loci_id, allele_id):
		
		new_allele_url=baseURL+"species/"+str(spec_id)+"/loci/"+str(loci_id)+"/alleles/"+str(allele_id)
		result = get_data(virtuoso_server,'select ?sequence ?date ?id ?short where { <'+new_allele_url+'> a typon:Allele; typon:dateEntered ?date; typon:hasSequence ?sequence; typon:id ?id. }')
		try:
			return (result["results"]["bindings"])
		except:
			return []	

class SequencesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/sequences/5
	def get(self, seq_id):
		
		new_seq_url=baseURL+"sequences/"+str(seq_id)
		result = get_data(virtuoso_server,'select ?sequence ?uniprot ?label where { <'+new_seq_url+'> a typon:Sequence; typon:nucleotideSequence ?sequence. OPTIONAL { <'+new_seq_url+'> typon:hasUniprotSequence ?uniprot.}. OPTIONAL{ <'+new_seq_url+'> typon:hasUniprotLabel ?label.}}')
		try:
			return (result["results"]["bindings"])
		except:
			return []

class LociSequencesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/pneumo/loci/5/sequences
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

class IsolatesListAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/1/isolates
	def get(self, spec_id):
		new_spec_url=baseURL+"species/"+str(spec_id)
		result = get_data(virtuoso_server,'select ?isolates where { ?isolates a typon:Isolate; typon:isFromTaxon <'+new_spec_url+'>. }')
		try:
			return (result["results"]["bindings"])
		except:
			return []

class IsolatesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/isolates/<string:isol_id>
	def get(self, isol_id):
		
		new_isol_url=baseURL+"isolates/"+str(isol_id)
		result = get_data(virtuoso_server,'select ?name  where { <'+new_isol_url+'> a typon:Isolate; typon:name ?name.  }')
		try:
			return (result["results"]["bindings"])
		except:
			return []

class IsolatesAllelesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/isolates/<string:isol_id>/alleles
	def get(self, isol_id):
		
		new_isol_url=baseURL+"isolates/"+str(isol_id)
		result = get_data(virtuoso_server,'select ?alleles  where { <'+new_isol_url+'> a typon:Isolate; typon:hasAllele ?alleles.  }')
		try:
			return (result["results"]["bindings"])
		except:
			return []

class IsolatesProfileAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/isolates/<int:isol_id>/profiles
	def get(self, isol_id):
		
		isol_url=baseURL+"isolates/"+str(isol_id)
		query='select ?id (str(?name) as ?name)  where { ?locus a typon:Locus; typon:name ?name. OPTIONAL{<'+isol_url+'> typon:hasAllele ?alleles. ?alleles typon:id ?id; typon:isOfLocus ?locus.}} order by (?name)'
		result = get_data(virtuoso_server,query) 
		
		try:
			return (result["results"]["bindings"])
		except:
			return []

#### ---- AUXILIARY METHODS ---- ###
def check_len(arg):
	if len(arg) == 0:
		abort(400)
	elif len(arg) > 10000:
		abort(400)

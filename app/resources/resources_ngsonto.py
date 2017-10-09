import datetime
from app import db, app, virtuoso_server
from flask import abort
from flask_restful import Resource, reqparse, marshal, fields
from app.models.models import Species, Schema, Loci, Allele, User, Role
from flask_security import Security, SQLAlchemyUserDatastore, auth_token_required
from SPARQLWrapper import JSON
import requests,json

# Setup Flask-Security
#~ user_datastore = SQLAlchemyUserDatastore(db, User, Role)
#~ security = Security(app, user_datastore)

baseURL="http://localhost:5000/NS/"
defaultgraph="<http://localhost:8890/2del>"
virtuoso_user='demo'
virtuoso_pass='demo'

#### ---- RESOURCES ---- ###
# TODO: Error handling for duplicate DB PK data on POST
#       (atm client gets splattered with ugly error messages)

def send_data(sparql_query):
    url = 'http://localhost:8890/DAV/test_folder/data'
    headers = {'content-type': 'application/sparql-query'}
    r = requests.post(url, data=sparql_query, headers=headers, auth=requests.auth.HTTPBasicAuth(virtuoso_user, virtuoso_pass))
    return r

def get_data(sparql_query):
    virtuoso_server.setQuery(sparql_query)
    virtuoso_server.setReturnFormat(JSON)
    result = virtuoso_server.query().convert()
    return result


#@app.route('/NS', methods=['GET'])

class NS(Resource):
	#~ @auth_token_required
	def get(self):
		
		return 'Welcome to the Nomenclature Server'

class createUser(Resource):
	@auth_token_required
	def get(self):
		
		if not User.query.first():
			user_datastore.create_user(email='test@example.com', password='adasdasd')
			print ("commit")
			db.session.commit()
		
		return 'Created user'

class SpeciesListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()
		self.reqparse.add_argument('name', dest= 'name',
								   required=True,
								   type=str,
								   help='No valid name provided for species')

	# curl -i  http://localhost:5000/NS/species
	def get(self):

		result = get_data('select ?species where { ?species a <http://purl.uniprot.org/core/Taxon> } LIMIT 20')
		return (result["results"]["bindings"])

	# curl -i  http://localhost:5000/NS/species -d 'name=bacteria'
	#~ @auth_token_required
	def post(self):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['name'])
		new_spec_url="http://localhost:5000/NS/species/"+args['name']
		result = get_data('ASK where { <'+new_spec_url+'> a <http://purl.uniprot.org/core/Taxon>}')
		if result['boolean']:
			return "Already exists", 409
		
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_spec_url+'> a <http://purl.uniprot.org/core/Taxon>; typon:name "'+args['name']+'"^^xsd:string .}')

		if result.status_code == 201 :
			return "Done", 201		
		else:
			return "Sum Thing Wong", result.status_code


class SpeciesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria
	def get(self, name):
		result = get_data('select ?species where { ?species typon:name "'+name+'"^^xsd:string } LIMIT 20')
		return (result["results"]["bindings"])

#@app.route('/NS/species/<string:species_name>/schema/<int:id>/loci') 
class SchemaLociAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()
		
		self.reqparse.add_argument('loci_id', dest= 'loci_id',
								   required=True,
								   type=int,
								   help='No valid id provided for loci')
		#~ super(SchemaLociAPI, self).__init__()

	def get(self, species_name,id ):
		
		new_schema_url=baseURL+"species/"+species_name+"/schemas/"+str(id)
		result = get_data('select ?locus where { <'+new_schema_url+'> typon:hasSchemaPart ?part. ?part typon:hasLocus ?locus. }')
		try:
			return (result["results"]["bindings"])
		except:
			return []
		
	
	#~ @auth_token_required
	def post(self, species_name, id):
		print(species_name)
		args = self.reqparse.parse_args(strict=True)
		
		new_schema_url=baseURL+"species/"+species_name+"/schemas/"+str(id)
		result = get_data('ASK where { <'+new_schema_url+'> a typon:Schema}')
		if not result['boolean']:
			return "Schema not found", 404
		
		new_locus_url=baseURL+"species/"+species_name+"/loci/"+str(args['loci_id'])
		result = get_data('ASK where { <'+new_locus_url+'> a typon:Locus}')
		if not result['boolean']:
			return "Locus not found", 404
				
		result = get_data('select (COUNT(?parts) as ?count) where { <'+new_schema_url+'> typon:hasSchemaPart ?parts. }')
		number_schema_parts=int(result["results"]["bindings"][0]['count']['value'])
		
		new_schema_part_url=new_schema_url+"/loci/"+str(number_schema_parts+1)
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_schema_part_url+'> a typon:SchemaPart ; typon:index "'+str(number_schema_parts+1)+'"^^xsd:int ; typon:hasLocus <'+new_locus_url+'>.<'+new_schema_url+'> typon:hasSchemaPart <'+new_schema_part_url+'>.}')

		if result.status_code == 201 :
			return "Done", 201		
		else:
			return "Sum Thing Wong", result.status_code
		

#@app.route('/NS/species/<string:species_name>/schema') 
class SchemaListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('description', dest= 'description',
								   required=True,
								   type=str,
								   help='No valid description provided for schema')

	# curl -i  http://localhost:5000/NS/species/bacteria/schema
	def get(self, species_name):
		result = get_data('select ?schemas ?name where { ?schemas a typon:Schema; typon:schemaName ?name. }')
		try:
			return (result["results"]["bindings"])
		except:
			return []

	# curl -i http://localhost:5000/NS/species/bacteria/schema -d 'description=interesting'
	
	#~ @auth_token_required
	def post(self, species_name):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['description'])
		
		result = get_data('select (COUNT(?schemas) as ?count) where { ?schemas a typon:Schema. }')
		
		number_schemas=int(result["results"]["bindings"][0]['count']['value'])
		
		
		new_schema_url=baseURL+"species/"+species_name+"/schemas/"+str(number_schemas+1)
		result = get_data('ASK where { <'+new_schema_url+'> a typon:Schema}')
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

	# curl -i http://localhost:5000/NS/species/bacteria/loci
	def get(self, species_name):
		result = get_data('select ?locus where { ?locus a typon:Locus; typon:isOfTaxon ?taxon. ?taxon typon:name "'+species_name+'"^^xsd:string . }')
		try:
			return (result["results"]["bindings"])
		except:
			return []

	# curl -i http://localhost:5000/NS/species/bacteria/loci -d 'aliases=macarena'
	#~ @auth_token_required
	def post(self, species_name):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['aliases'])
		
		new_spec_url=baseURL+"species/"+species_name
		result = get_data('ASK where { <'+new_spec_url+'> a <http://purl.uniprot.org/core/Taxon>}')
		
		
		if not result['boolean'] :

			return "Species not found", 404
		
		#check if already exists locus with that aliases
		result = get_data('ASK where { ?locus a typon:Locus; typon:name "'+args['aliases']+'"^^xsd:string.}')
		
		
		if result['boolean'] :

			return "Locus already exists", 404
		
		
		result = get_data('select (COUNT(?locus) as ?count) where { ?locus a typon:Locus; typon:isOfTaxon ?taxon. ?taxon typon:name "'+species_name+'"^^xsd:string . }')
		
		number_loci_spec=int(result["results"]["bindings"][0]['count']['value'])
		
		new_locus_url=baseURL+"species/"+species_name+"/loci/"+str(number_loci_spec+1)
		
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_locus_url+'> a typon:Locus; typon:name "'+args['aliases']+'"^^xsd:string; typon:isOfTaxon <'+new_spec_url+'> .}')

		if result.status_code == 201 :
			return new_locus_url, 201		
		else:
			return "Sum Thing Wong", result.status_code

class LociAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria/loci/7
	def get(self, species_name, id):
		
		new_locus_url=baseURL+"species/"+species_name+"/loci/"+str(id)
		#~ return (new_locus_url)
		result = get_data('select ?name where { <'+new_locus_url+'> a typon:Locus; typon:name ?name. } LIMIT 20')
		try:
			return (result["results"]["bindings"])
		except:
			return []

class AlleleListAPItypon(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		#~ self.reqparse.add_argument('time_stamp', dest= 'time_stamp',
								   #~ required=True,
								   #~ type=lambda x: datetime.datetime.strptime(x,'%Y-%m-%dT%H:%M:%S.%f'),
								   #~ help='No valid time stamp provided for allele')
		self.reqparse.add_argument('sequence', dest= 'sequence',
								   required=True,
								   type=str,
								   help='No valid sequence provided for allele')

	# curl -i http://localhost:5000/NS/species/bacteria/loci/7/alleles
	def get(self, species_name, loci_id):
		# Check if loci associated with species exists on the database 
				
		new_locus_url=baseURL+"species/"+species_name+"/loci/"+str(loci_id)
		result = get_data('select ?alleles where { <'+new_locus_url+'> a typon:Locus; typon:hasDefinedAllele ?alleles. }')
		try:
			return (result["results"]["bindings"])
		except:
			return []
		


	# curl -i http://localhost:5000/NS/species/bacteria/loci/7/alleles -d 'time_stamp=2017-07-24T17:16:59.688836' -d 'sequence=ACTCTGT'
	#~ @auth_token_required
	def post(self, species_name, loci_id):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['sequence'])
		
		#check if species exists
		new_spec_url=baseURL+"species/"+species_name
		result = blaze_server.query('ASK where { <'+new_spec_url+'> a <http://purl.uniprot.org/core/Taxon>}')
		
		if not result['boolean'] :

			return "Species not found", 404
		
		#check if locus exist
		new_locus_url=baseURL+"species/"+species_name+"/loci/"+str(loci_id)
		result = blaze_server.query('ASK where { <'+new_locus_url+'> a <http://purl.phyloviz.net/ontology/typon#Locus>.}')
		if not result['boolean'] :

			return "Locus not found", 404
		
		#check if sequence already exists
		result = get_data('select (COUNT(?alleles) as ?count) where { ?alleles typon:isOfLocus> <'+new_locus_url+'>.}')
		number_alleles_loci=int(result["results"]["bindings"][0]['count']['value'])
		new_allele_url=baseURL+"species/"+species_name+"/loci/"+str(loci_id)+"/alleles/"+str(number_alleles_loci+1)

		result = get_data('select ?seq where { ?seq a typon:Sequence; typon:nucleotideSequence "'+args['sequence']+'"^^xsd:string.}')
				
		#if sequence exists link it to allele, if not create new sequence
		try :
			new_seq_url = result["results"]["bindings"][0]['seq']['value']
			
		except IndexError:
			result = get_data('select (COUNT(?seq) as ?count) where {?seq a typon:Sequence }')
			number_sequences=int(result["results"]["bindings"][0]['count']['value'])
			new_seq_url=baseURL+"sequences/"+str(number_sequences+1)
			result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_seq_url+'> a typon:Sequence; typon:nucleotideSequence "'+args['sequence']+'"^^xsd:string.}')
			if result.status_code != 201 :
				return "Sum Thing Wong creating sequence", result.status_code
		except:
			return "Sum Thing Wong creating sequence", 400
		
		
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' {<'+new_allele_url+'> a typon:Allele; typon:isOfLocus <'+new_locus_url+'>; typon:dateEntered "'+str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+'"^^xsd:dateTime; typon:id "'+str(number_alleles_loci+1)+'"^^xsd:long ; typon:hasSequence <'+new_seq_url+'>. <'+new_locus_url+'> typon:hasDefinedAllele <'+new_allele_url+'>.}')
		
		if result.status_code == 201 :
			return "Done", 201		
		else:
			return "Sum Thing Wong", result.status_code

class AlleleAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria/loci/7/alleles/7
	def get(self, species_name, loci_id, allele_id):
		
		new_allele_url=baseURL+"species/"+species_name+"/loci/"+str(loci_id)+"/alleles/"+str(allele_id)
		result = get_data('select ?sequence ?date ?id where { <'+new_allele_url+'> a typon:Allele; typon:dateEntered ?date; typon:hasSequence ?sequence; typon:id ?id . }')
		try:
			return (result["results"]["bindings"])
		except:
			return []	

class SequencesAPItypon(Resource):
	# curl -i  http://localhost:5000/NS/sequences/5
	def get(self, seq_id):
		
		new_seq_url=baseURL+"sequences/"+str(seq_id)
		result = get_data('select ?sequence where { <'+new_seq_url+'> a typon:Sequence; typon:nucleotideSequence ?sequence.  }')
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

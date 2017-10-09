import datetime
from app import db, app, blaze_server
from flask import abort
from flask_restful import Resource, reqparse, marshal, fields
from app.models.models import Species, Schema, Loci, Allele, User, Role
from flask_security import Security, SQLAlchemyUserDatastore, auth_token_required

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

#### ---- MARSHAL TEMPLATES ---- ###
species_fields = {
	'name': fields.String
}
schema_fields = {
	'id_per_species': fields.Integer,
	#~ 'loci': fields.String,
	'description': fields.String,
	'species_name': fields.String
}
loci_fields = {
	'aliases': fields.String,
	'allele_number': fields.Integer,
	'species_name': fields.String,
	'id_per_species': fields.Integer
}
allele_fields = {
	'id_per_locus': fields.Integer,
	'time_stamp': fields.DateTime(dt_format='iso8601'),
	'sequence': fields.String
}
schema_loci_fields = {
	'id_per_species': fields.Integer
}

#### ---- RESOURCES ---- ###
# TODO: Error handling for duplicate DB PK data on POST
#       (atm client gets splattered with ugly error messages)


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

class SpeciesListAPI(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()
		self.reqparse.add_argument('name', dest= 'name',
								   required=True,
								   type=str,
								   help='No valid name provided for species')
		super(SpeciesListAPI, self).__init__()

	# curl -i  http://localhost:5000/NS/species
	def get(self):
		return marshal(Species.query.all(), species_fields)

	# curl -i  http://localhost:5000/NS/species -d 'name=bacteria'
	#~ @auth_token_required
	def post(self):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['name'])
		species = Species(args['name'])
		db.session.add(species)
		db.session.commit()
		return marshal(species, species_fields), 201


class SpeciesAPI(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria
	def get(self, name):
		species=Species.query.get_or_404(name)
		schemas=species.schemas.all()
		spec_info=[marshal(species, species_fields),marshal(schemas, schema_fields)]
		return spec_info

#@app.route('/NS/species/<string:species_name>/schema') 
class SchemaListAPI(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('description', dest= 'description',
								   required=True,
								   type=str,
								   help='No valid description provided for schema')
		super(SchemaListAPI, self).__init__()

	# curl -i  http://localhost:5000/NS/species/bacteria/schema
	def get(self, species_name):
		return marshal(Species.query.get_or_404(species_name).schemas.all(), schema_fields)

	# curl -i http://localhost:5000/NS/species/bacteria/schema -d 'description=interesting'
	
	#~ @auth_token_required
	def post(self, species_name):
		args = self.reqparse.parse_args(strict=True)
		#~ check_len(args['loci'])
		check_len(args['description'])
		num_of_schemas= len(Species.query.get_or_404(species_name).schemas.all())
		schema = Schema(args['description'], Species.query.get_or_404(species_name),num_of_schemas+1)
		db.session.add(schema)
		db.session.commit()
		return marshal(schema, schema_fields), 201

#@app.route('/NS/species/<string:species_name>/schema/<int:id>/loci') 
class SchemaLociAPI(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()
		
		self.reqparse.add_argument('loci_id', dest= 'loci_id',
								   required=True,
								   type=int,
								   help='No valid id provided for loci')
		super(SchemaLociAPI, self).__init__()

	# curl -i  http://localhost:5000/NS/species/bacteria/schema
	def get(self, species_name,id ):
		schema=Species.query.get_or_404(species_name).schemas.filter_by(id_per_species=id).first()
		#~ return schema
		results =marshal(schema.schema_loci.all(),schema_loci_fields)
		for loci in results:
			for k,v in loci.items():
				#todo change hardcoded
				loci[k]= "http://localhost:5000/NS/species/"+species_name+"/loci/" + str(v)
		return results
		

	# curl -i http://localhost:5000/NS/species/bacteria/schema -d 'description=interesting'
	
	#~ @auth_token_required
	def post(self, species_name, id):
		print(species_name)
		args = self.reqparse.parse_args(strict=True)
		schema = Species.query.get_or_404(species_name).schemas.filter_by(id_per_species=id).first()
		someLoci = Species.query.get_or_404(species_name).loci.filter_by(id_per_species=args['loci_id']).first()
		someLoci.schema = [schema]
		db.session.add(someLoci)
		db.session.commit()
		return marshal(someLoci,loci_fields), 201

class SchemaAPI(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria/schema/7
	def get(self, species_name, id):
		if Schema.query.get_or_404(id).species_name != species_name:
			abort(404)
		return marshal(Schema.query.get_or_404(id), schema_fields)


class LociListAPI(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('aliases', dest= 'aliases',
								   required=True,
								   type=str,
								   help='No valid aliases provided for loci')

		super(LociListAPI, self).__init__()

	# curl -i http://localhost:5000/NS/species/bacteria/loci
	def get(self, species_name):
		return marshal(Species.query.get_or_404(species_name).loci.all(), loci_fields)

	# curl -i http://localhost:5000/NS/species/bacteria/loci -d 'aliases=macarena' -d 'allele_number=10'
	#~ @auth_token_required
	def post(self, species_name):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['aliases'])
		n_of_loci_in_species=len(Species.query.get_or_404(species_name).loci.all())

		loci = Loci( args['aliases'], 0, Species.query.get_or_404(species_name).name,n_of_loci_in_species+1)
		db.session.add(loci)
		db.session.commit()
		return marshal(loci, loci_fields), 201


class LociAPI(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria/loci/7
	def get(self, species_name, id):
		
		#~ if Loci.query.get_or_404(id).species_name != species_name:
			#~ abort(404)
		return marshal(Species.query.get_or_404(species_name).loci.filter_by(id_per_species=id).all(), loci_fields)


class AlleleListAPI(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()

		self.reqparse.add_argument('time_stamp', dest= 'time_stamp',
								   required=True,
								   type=lambda x: datetime.datetime.strptime(x,'%Y-%m-%dT%H:%M:%S.%f'),
								   help='No valid time stamp provided for allele')
		self.reqparse.add_argument('sequence', dest= 'sequence',
								   required=True,
								   type=str,
								   help='No valid sequence provided for allele')
		super(AlleleListAPI, self).__init__()

	# curl -i http://localhost:5000/NS/species/bacteria/loci/7/alleles
	def get(self, species_name, loci_id):
		# Check if loci associated with species exists on the database 
			
		someLoci = Species.query.get_or_404(species_name).loci.filter_by(id_per_species=loci_id).first()
		alleles=[]
		for asdas in someLoci.alleles:
			alleles.append (marshal(asdas, allele_fields))
		return alleles


	# curl -i http://localhost:5000/NS/species/bacteria/loci/7/alleles -d 'time_stamp=2017-07-24T17:16:59.688836' -d 'sequence=ACTCTGT'
	#~ @auth_token_required
	def post(self, species_name, loci_id):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['sequence'])
		sel_loci= Species.query.get_or_404(species_name).loci.filter_by(id_per_species=loci_id).first()
		try:
			n_of_alleles_in_loci=len(sel_loci.alleles.all())
		except:
			n_of_alleles_in_loci=0

		allele = Allele(n_of_alleles_in_loci+1, str(args['time_stamp']),sel_loci.identifier ,args['sequence'])

		sel_loci.allele_number=n_of_alleles_in_loci+1
		db.session.add(allele)
		db.session.add(sel_loci)
		db.session.commit()
		
		return marshal(allele, allele_fields), 201


class AlleleAPI(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria/loci/7/alleles/7
	def get(self, species_name, loci_id, id):
		if Allele.query.get_or_404(id).species_name != species_name:
			abort(404)
		if Allele.query.get_or_404(id).locus != loci_id:
			abort(404)
		return marshal(Allele.query.get_or_404(id), allele_fields)


#### ---- AUXILIARY METHODS ---- ###
def check_len(arg):
	if len(arg) == 0:
		abort(400)

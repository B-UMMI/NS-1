import datetime
from app import db
from flask import abort
from flask_restful import Resource, reqparse, marshal, fields
from app.models.models import Species, Schema, Loci, Allele

#### ---- MARSHAL TEMPLATES ---- ###
species_fields = {
	'name': fields.String
}
schema_fields = {
	'identifier': fields.Integer,
	'loci': fields.String,
	'description': fields.String,
	'species_name': fields.String
}
loci_fields = {
	'identifier': fields.Integer,
	'aliases': fields.String,
	'allele_number': fields.Integer,
	'species_name': fields.String
}
allele_fields = {
	'identifier': fields.Integer,
	'time_stamp': fields.DateTime(dt_format='iso8601'),
	'sequence': fields.String,	
	'species_name': fields.String
}

#### ---- RESOURCES ---- ###
# TODO: Error handling for duplicate DB PK data on POST
#       (atm client gets splattered with ugly error messages)

class NS(Resource):
	def get(self):
		return 'Welcome to the Nomenclature Server'


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
		return marshal(Species.query.get_or_404(name), species_fields)


class SchemaListAPI(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()
		self.reqparse.add_argument('id', dest= 'id',
								   required=True,
								   type=int,
								   help='No valid id provided for schema')
		self.reqparse.add_argument('loci', dest= 'loci',
								   required=True,
								   type=str,
								   help='No valid loci provided for schema')
		self.reqparse.add_argument('description', dest= 'description',
								   required=True,
								   type=str,
								   help='No valid description provided for schema')
		super(SchemaListAPI, self).__init__()

	# curl -i  http://localhost:5000/NS/species/bacteria/schema
	def get(self, species_name):
		return marshal(Species.query.get_or_404(species_name).schemas.all(), schema_fields)

	# curl -i http://localhost:5000/NS/species/bacteria/schema -d 'id=7' -d 'loci=ACG' -d 'description=interesting'
	def post(self, species_name):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['loci'])
		check_len(args['description'])
		schema = Schema(args['id'], args['loci'], args['description'], Species.query.get_or_404(species_name))
		db.session.add(schema)
		db.session.commit()
		return marshal(schema, schema_fields), 201


class SchemaAPI(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria/schema/7
	def get(self, species_name, id):
		if Schema.query.get_or_404(id).species_name != species_name:
			abort(404)
		return marshal(Schema.query.get_or_404(id), schema_fields)


class LociListAPI(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()
		self.reqparse.add_argument('id', dest= 'id',
								   required=True,
								   type=int,
								   help='No valid id provided for loci')
		self.reqparse.add_argument('aliases', dest= 'aliases',
								   required=True,
								   type=str,
								   help='No valid aliases provided for loci')
		self.reqparse.add_argument('allele_number', dest= 'allele_number',
								   required=True,
								   type=str,
								   help='No valid allele number provided for loci')
		super(LociListAPI, self).__init__()

	# curl -i http://localhost:5000/NS/species/bacteria/loci
	def get(self, species_name):
		return marshal(Species.query.get_or_404(species_name).loci.all(), loci_fields)

	# curl -i http://localhost:5000/NS/species/bacteria/loci -d 'id=7' -d 'aliases=macarena' -d 'allele_number=10'
	def post(self, species_name):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['aliases'])
		loci = Loci(args['id'], args['aliases'], args['allele_number'], Species.query.get_or_404(species_name))
		db.session.add(loci)
		db.session.commit()
		return marshal(loci, loci_fields), 201


class LociAPI(Resource):
	# curl -i  http://localhost:5000/NS/species/bacteria/loci/7
	def get(self, species_name, id):
		if Loci.query.get_or_404(id).species_name != species_name:
			abort(404)
		return marshal(Loci.query.get_or_404(id), loci_fields)


class AlleleListAPI(Resource):
	def __init__(self):
		self.reqparse = reqparse.RequestParser()
		self.reqparse.add_argument('id', dest= 'id',
								   required=True,
								   type=int,
								   help='No valid id provided for allele')
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
		loci_db_entry = Species.query.get_or_404(species_name).loci.filter_by(identifier=loci_id)
		if loci_db_entry.first() == None:
			abort(404)
		return marshal(loci_db_entry.first().alleles.all(), allele_fields)

	# curl -i http://localhost:5000/NS/species/bacteria/loci/7/alleles -d 'id=7' -d 'time_stamp=2017-07-24T17:16:59.688836' -d 'sequence=ACTCTGT'
	def post(self, species_name, loci_id):
		args = self.reqparse.parse_args(strict=True)
		check_len(args['sequence'])
		allele = Allele(args['id'], args['time_stamp'], args['sequence'], Species.query.get_or_404(species_name), Loci.query.get_or_404(loci_id))
		db.session.add(allele)
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

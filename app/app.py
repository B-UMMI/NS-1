# import datetime
# from flask import Flask, jsonify, abort
# from flask_restful import Api, Resource, reqparse, fields, marshal
# from flask_sqlalchemy import SQLAlchemy

# app = Flask(__name__)
# api = Api(app)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://chewie:newbie@localhost/testdb'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# db = SQLAlchemy(app)

# #### ---- MARSHAL TEMPLATES ---- ###
# species_fields = {
# 	'name': fields.String
# }

# schema_fields = {
# 	'identifier': fields.Integer,
# 	'loci': fields.String,
# 	'description': fields.String
# }

# loci_fields = {
# 	'identifier': fields.Integer,
# 	'aliases': fields.String,
# 	'alleles': fields.String
# }

# allele_fields = {
# 	'identifier': fields.Integer,
# 	'time_stamp': fields.DateTime(dt_format='iso8601'),
# 	'sequence': fields.String	
# }

# ###					  	 ###
# ### --- Resources.py --- ###
# ###					  	 ###

# class NS(Resource):
# 	def get(self):
# 		return 'Welcome to the Nomenclature Server'


# class SpeciesListAPI(Resource):
# 	def __init__(self):
# 		self.reqparse = reqparse.RequestParser()
# 		self.reqparse.add_argument('name',
# 								   required=True,
# 								   type=str,
# 								   help='No valid name provided for species') # location='json')
# 		super(SpeciesListAPI, self).__init__()

# 	# curl -i  http://localhost:5000/NS/species
# 	def get(self):
# 		# TODO: implement error handler for not found?
# 		return marshal(Species.query.all(), species_fields)

# 	# curl -i  http://localhost:5000/NS/species -d 'name=bacteria'
# 	def post(self):
# 		args = self.reqparse.parse_args(strict=True)
# 		check_len(args['name'])
# 		species = Species(args['name']) # TODO: hard coded :\
# 		db.session.add(species)
# 		db.session.commit()
# 		return marshal(species, species_fields), 201


# class SpeciesAPI(Resource):
# 	# curl -i  http://localhost:5000/NS/species/bacteria
# 	def get(self, name):
# 		return marshal(Species.query.get_or_404(name), species_fields)

# 	# curl -i  -d 'name=baDteria' http://localhost:5000/NS/species/bacteria -X PUT
# 	def put(self, name):
# 		pass # TODO: update necessary?


# class SchemaListAPI(Resource):
# 	def __init__(self):
# 		self.reqparse = reqparse.RequestParser()
# 		self.reqparse.add_argument('id',
# 								   required=True,
# 								   type=int,
# 								   help='No valid id provided for schema')
# 		self.reqparse.add_argument('loci',
# 								   required=True,
# 								   type=str,
# 								   help='No valid loci provided for schema')
# 		self.reqparse.add_argument('description',
# 								   required=True,
# 								   type=str,
# 								   help='No valid description provided for schema')
# 		super(SchemaListAPI, self).__init__()

# 	# TODO: needs to check URI: species name rly exists? Make relationship in model?
# 	# curl -i  http://localhost:5000/NS/species/bacteria/schema
# 	def get(self, name):
# 		return marshal(Schema.query.all(), schema_fields)

# 	# curl http://localhost:5000/NS/species/bacteria/schema -d 'id=7' -d 'loci=ACG' -d 'description=interesting'
# 	def post(self, name):
# 		args = self.reqparse.parse_args(strict=True)
# 		check_len(args['loci'])
# 		check_len(args['description'])
# 		schema = Schema(args['id'], args['loci'], args['description']) # TODO: hard coded :\
# 		db.session.add(schema)
# 		db.session.commit()
# 		return marshal(schema, schema_fields), 201


# class SchemaAPI(Resource):
# 	# curl -i  http://localhost:5000/NS/species/bacteria/schema/1
# 	def get(self, name, id):
# 		return marshal(Schema.query.get_or_404(id), schema_fields)

# 	# TODO: updates?
# 	def put(self, name, id):
# 		pass


# class LociListAPI(Resource):
# 	def __init__(self):
# 		self.reqparse = reqparse.RequestParser()
# 		self.reqparse.add_argument('id',
# 								   required=True,
# 								   type=int,
# 								   help='No valid id provided for loci')
# 		self.reqparse.add_argument('aliases',
# 								   required=True,
# 								   type=str,
# 								   help='No valid aliases provided for loci')
# 		self.reqparse.add_argument('alleles',
# 								   required=True,
# 								   type=str,
# 								   help='No valid alleles provided for loci')
# 		super(LociListAPI, self).__init__()

# 	# curl -i http://localhost:5000/NS/species/bacteria/loci
# 	def get(self, name):
# 		return marshal(Loci.query.all(), loci_fields)

# 	# curl -i http://localhost:5000/NS/species/bacteria/loci -d 'id=7' -d 'aliases=macarena' -d 'alleles=YHTHK'
# 	def post(self, name):
# 		args = self.reqparse.parse_args(strict=True)
# 		check_len(args['aliases'])
# 		check_len(args['alleles'])
# 		loci = Loci(args['id'], args['aliases'], args['alleles']) # TODO: hard coded :\
# 		db.session.add(loci)
# 		db.session.commit()
# 		return marshal(loci, loci_fields), 201


# class LociAPI(Resource):
# 	# curl -i  http://localhost:5000/NS/species/bacteria/loci/1
# 	def get(self, name, id):
# 		return marshal(Loci.query.get_or_404(id), loci_fields)
	
# 	# TODO: updates
# 	def put(self, name, id):
# 		pass


# class AlleleListAPI(Resource):
# 	def __init__(self):
# 		self.reqparse = reqparse.RequestParser()
# 		self.reqparse.add_argument('id',
# 								   required=True,
# 								   type=int,
# 								   help='No valid id provided for allele')
# 		self.reqparse.add_argument('time_stamp',
# 								   required=True,
# 								   type=lambda x: datetime.datetime.strptime(x,'%Y-%m-%dT%H:%M:%S.%f'),
# 								   help='No valid time stamp provided for allele')
# 		self.reqparse.add_argument('sequence',
# 								   required=True,
# 								   type=str,
# 								   help='No valid sequence provided for allele')
# 		super(AlleleListAPI, self).__init__()

# 	# curl -i http://localhost:5000/NS/species/bacteria/loci/1/allele
# 	def get(self, name, loci_id):
# 		return marshal(Allele.query.all(), allele_fields)

# 	# curl -i http://localhost:5000/NS/species/bacteria/loci/1/allele -d 'id=7' -d 'time_stamp=2017-07-24T17:16:59.688836' -d 'sequence=ACTCTGT'
# 	def post(self, name, loci_id):
# 		args = self.reqparse.parse_args(strict=True)
# 		check_len(args['sequence'])
# 		allele = Allele(args['id'], args['time_stamp'], args['sequence']) # TODO: hard coded :\
# 		db.session.add(allele)
# 		db.session.commit()
# 		return marshal(allele, allele_fields), 201


# class AlleleAPI(Resource):
# 	# curl -i  http://localhost:5000/NS/species/bacteria/loci/1/allele/7
# 	def get(self, name, loci_id, id):
# 		return marshal(Allele.query.get_or_404(id), allele_fields)
	
# 	# TODO: updates
# 	def put(self, name, loci_id, id):
# 		pass



# #### ---- AVAILABLE RESOURCES ---- ###
# api.add_resource(NS,
# 				'/NS',
# 				endpoint='NS')
# api.add_resource(SpeciesListAPI,
# 				'/NS/species',
# 				endpoint='speciesList') 
# api.add_resource(SpeciesAPI,
# 				'/NS/species/<string:name>',
# 				endpoint='species')
# api.add_resource(SchemaListAPI,
# 				'/NS/species/<string:name>/schema',
# 				endpoint='schemaList')
# api.add_resource(SchemaAPI,
# 				'/NS/species/<string:name>/schema/<int:id>',
# 				endpoint='schema')
# api.add_resource(LociListAPI,
# 				'/NS/species/<string:name>/loci',
# 				endpoint='lociList')
# api.add_resource(LociAPI,
# 				'/NS/species/<string:name>/loci/<int:id>',
# 				endpoint='loci')
# api.add_resource(AlleleListAPI,
# 				'/NS/species/<string:name>/loci/<int:loci_id>/allele',
# 				endpoint='alleleList')
# api.add_resource(AlleleAPI,
# 				'/NS/species/<string:name>/loci/<int:loci_id>/allele/<int:id>',
# 				endpoint='allele')



# ###					  ###
# ### --- Models.py --- ###
# ###					  ###

# class Species(db.Model):
# 	name = db.Column(db.String, primary_key=True)
# 	# TODO: One-to-Many relationship with Schema

# 	def __init__(self, name):
# 		self.name = name

# 	def __repr__(self):
# 		return '<Species %r>' % (self.name)


# class Schema(db.Model):
# 	identifier = db.Column(db.Integer, primary_key=True)
# 	loci = db.Column(db.String(2048)) # TODO: indexes
# 	description = db.Column(db.String(2048))
# 	# NOTE: relationship with Species?

# 	def __init__(self, identifier, loci, description=''): # NOTE: default value for desc.?
# 		self.identifier = identifier
# 		self.loci = loci
# 		self.description = description 

# 	def __repr__(self):
# 		return '<Schema %d: %r>' % (self.identifier, self.description) 


# class Loci(db.Model):
# 	identifier = db.Column(db.Integer, primary_key=True)
# 	aliases = db.Column(db.String(2048))
# 	alleles = db.Column(db.String(2048))

# 	def __init__(self, identifier, aliases, alleles):
# 		self.identifier = identifier
# 		self.aliases = aliases
# 		self.alleles = alleles

# 	def __repr__(self):
# 		return '<Loci %d: %r>' % (self.identifier, self.aliases)


# class Allele(db.Model):
# 	identifier = db.Column(db.Integer, primary_key=True)
# 	time_stamp = db.Column(db.DateTime)
# 	sequence = db.Column(db.String(8192))

# 	def __init__(self, identifier, time_stamp, sequence):
# 		self.identifier = identifier
# 		self.time_stamp = time_stamp
# 		self.sequence = sequence

# 	def __repr__(self):
# 		return '<Allele %d: %r>' % (self.identifier, self.time_stamp)



# #### ---- AUXILIARY METHODS ---- ###
# def check_len(arg):
# 	if len(arg) == 0:
# 		abort(400)



# if __name__ == '__main__':
# 	app.run(debug=True)
# 	
from app import app
from flask_restful import Api
from app.resources.resources import NS, createUser
from app.resources.resources import SpeciesListAPI, SpeciesAPI
from app.resources.resources import SchemaListAPI, SchemaAPI, SchemaLociAPI
from app.resources.resources import LociListAPI, LociAPI
from app.resources.resources import AlleleListAPI, AlleleAPI

## API Setup ##
api = Api(app)

# NOTE: maybe use 'url_for(...)' + concatenation instead of hard coding URIs

api.add_resource(createUser,
				'/createUser',
				endpoint='createUser')

api.add_resource(NS,
				'/NS',
				endpoint='NS')
api.add_resource(SpeciesListAPI,
				'/NS/species',
				endpoint='speciesList')
api.add_resource(SpeciesAPI,
				'/NS/species/<string:name>',
				endpoint='species')
api.add_resource(SchemaListAPI,
				'/NS/species/<string:species_name>/schema',
				endpoint='schemaList')
api.add_resource(SchemaAPI,
				'/NS/species/<string:species_name>/schema/<int:id>',
				endpoint='schema')
api.add_resource(SchemaLociAPI,
				'/NS/species/<string:species_name>/schema/<int:id>/loci',
				endpoint='schemaLoci')
api.add_resource(LociListAPI,
				'/NS/species/<string:species_name>/loci',
				endpoint='lociList')
api.add_resource(LociAPI,
				'/NS/species/<string:species_name>/loci/<int:id>',
				endpoint='loci')
api.add_resource(AlleleListAPI,
				'/NS/species/<string:species_name>/loci/<int:loci_id>/alleles',
				endpoint='alleleList')
api.add_resource(AlleleAPI,
				'/NS/species/<string:species_name>/loci/<int:loci_id>/alleles/<int:id>',
				endpoint='allele')

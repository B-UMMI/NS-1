from app import app
from flask_restful import Api
from app.resources.resources_ngsonto import NS, createUser
from app.resources.resources_ngsonto import SpeciesListAPItypon,SpeciesAPItypon, SchemaListAPItypon, LociListAPItypon, LociAPItypon, SchemaLociAPItypon, AlleleListAPItypon, AlleleAPItypon, SequencesAPItypon

## API Setup ##
api = Api(app)

# NOTE: maybe use 'url_for(...)' + concatenation instead of hard coding URIs

#~ api.add_resource(createUser,
				#~ '/createUser',
				#~ endpoint='createUser')

				
api.add_resource(NS,
				'/NS',
				endpoint='NS')			


api.add_resource(SpeciesListAPItypon,
				'/NS/species',
				endpoint='speciesList')

api.add_resource(SpeciesAPItypon,
				'/NS/species/<string:name>',
				endpoint='species')

api.add_resource(SchemaListAPItypon,
				'/NS/species/<string:species_name>/schemas',
				endpoint='schemaList')

api.add_resource(SchemaLociAPItypon,
				'/NS/species/<string:species_name>/schemas/<int:id>/loci',
				endpoint='schemaLoci')

api.add_resource(LociListAPItypon,
				'/NS/species/<string:species_name>/loci',
				endpoint='lociList')

api.add_resource(LociAPItypon,
				'/NS/species/<string:species_name>/loci/<int:id>',
				endpoint='loci')

api.add_resource(AlleleListAPItypon,
				'/NS/species/<string:species_name>/loci/<int:loci_id>/alleles',
				endpoint='alleleList')

api.add_resource(AlleleAPItypon,
				'/NS/species/<string:species_name>/loci/<int:loci_id>/alleles/<int:allele_id>',
				endpoint='allele')
				
api.add_resource(SequencesAPItypon,
				'/NS/sequences/<string:seq_id>',
				endpoint='sequences')

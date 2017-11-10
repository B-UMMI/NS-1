from app import app
from flask_restful import Api
from app.resources.resources_ngsonto import NS, createUser, profile
from app.resources.resources_ngsonto import SpeciesListAPItypon, SpeciesAPItypon
from app.resources.resources_ngsonto import SchemaListAPItypon, SchemaLociAPItypon, SchemaAPItypon
from app.resources.resources_ngsonto import LociListAPItypon, LociAPItypon, LociFastaAPItypon, LociSequencesAPItypon
from app.resources.resources_ngsonto import AlleleListAPItypon, AlleleAPItypon, SequencesAPItypon
from app.resources.resources_ngsonto import IsolatesAPItypon, IsolatesAllelesAPItypon, IsolatesListAPItypon, IsolatesProfileAPItypon

## API Setup ##
api = Api(app)

# NOTE: maybe use 'url_for(...)' + concatenation instead of hard coding URIs

api.add_resource(createUser,
				'/createUser',
				endpoint='createUser')

				
api.add_resource(NS,
				'/NS',
				endpoint='NS')			


api.add_resource(profile,
				'/NS/species/<int:spec_id>/profiles',
				endpoint='profile')

api.add_resource(SpeciesListAPItypon,
				'/NS/species',
				endpoint='speciesList')

api.add_resource(SpeciesAPItypon,
				'/NS/species/<int:spec_id>',
				endpoint='species')

api.add_resource(SchemaListAPItypon,
				'/NS/species/<int:spec_id>/schemas',
				endpoint='schemaList')

api.add_resource(SchemaAPItypon,
				'/NS/species/<int:spec_id>/schemas/<int:id>',
				endpoint='schema')

api.add_resource(SchemaLociAPItypon,
				'/NS/species/<int:spec_id>/schemas/<int:id>/loci',
				endpoint='schemaLoci')

api.add_resource(LociListAPItypon,
				'/NS/species/<int:spec_id>/loci',
				endpoint='lociList')

api.add_resource(LociAPItypon,
				'/NS/species/<int:spec_id>/loci/<int:id>',
				endpoint='loci')

api.add_resource(LociFastaAPItypon,
				'/NS/species/<int:spec_id>/loci/<int:id>/fasta',
				endpoint='lociFasta')

api.add_resource(AlleleListAPItypon,
				'/NS/species/<int:spec_id>/loci/<int:loci_id>/alleles',
				endpoint='alleleList')

api.add_resource(AlleleAPItypon,
				'/NS/species/<int:spec_id>/loci/<int:loci_id>/alleles/<int:allele_id>',
				endpoint='allele')
				
api.add_resource(SequencesAPItypon,
				'/NS/sequences/<string:seq_id>',
				endpoint='sequences')

api.add_resource(IsolatesListAPItypon,
				'/NS/species/<int:spec_id>/isolates',
				endpoint='isolatesList')

api.add_resource(IsolatesAPItypon,
				'/NS/isolates/<string:isol_id>',
				endpoint='isolates')

api.add_resource(IsolatesAllelesAPItypon,
				'/NS/isolates/<string:isol_id>/alleles',
				endpoint='isolatesAlleles')

api.add_resource(IsolatesProfileAPItypon,
				'/NS/isolates/<string:isol_id>/profiles',
				endpoint='isolatesProfiles')

api.add_resource(LociSequencesAPItypon,
				'/NS/species/<int:spec_id>/loci/<int:loci_id>/sequences',
				endpoint='lociSequences')

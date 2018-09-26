from app import app
from flask_restful import Api
from app.resources.resources_ngsonto import NS, profile
from app.resources.resources_ngsonto import SpeciesListAPItypon, SpeciesAPItypon
from app.resources.resources_ngsonto import SchemaListAPItypon, SchemaLociAPItypon, SchemaAPItypon, SchemaZipAPItypon
from app.resources.resources_ngsonto import LociListAPItypon, LociAPItypon, LociFastaAPItypon, LociSequencesAPItypon
from app.resources.resources_ngsonto import AlleleListAPItypon, AlleleAPItypon, SequencesAPItypon, SequencesListAPItypon
from app.resources.resources_ngsonto import IsolatesAPItypon, IsolatesAllelesAPItypon, IsolatesListAPItypon, IsolatesProfileAPItypon

version="/v1"

## API Setup ##
api = Api(app)

# NOTE: maybe use 'url_for(...)' + concatenation instead of hard coding URIs

				
api.add_resource(NS,
				version+'/NS',
				endpoint='NS')			


api.add_resource(profile,
				version+'/NS/species/<int:spec_id>/profiles',
				endpoint='profile')

api.add_resource(SpeciesListAPItypon,
				version+'/NS/species',
				endpoint='speciesList')

api.add_resource(SpeciesAPItypon,
				version+'/NS/species/<int:spec_id>',
				endpoint='species')

api.add_resource(SchemaListAPItypon,
				version+'/NS/species/<int:spec_id>/schemas',
				endpoint='schemaList')

api.add_resource(SchemaAPItypon,
				version+'/NS/species/<int:spec_id>/schemas/<int:id>',
				endpoint='schema')

api.add_resource(SchemaZipAPItypon,
				version+'/NS/species/<int:spec_id>/schemas/<int:id>/compressed',
				endpoint='schemaZip')				

api.add_resource(SchemaLociAPItypon,
				version+'/NS/species/<int:spec_id>/schemas/<int:id>/loci',
				endpoint='schemaLoci')

api.add_resource(LociListAPItypon,
				version+'/NS/species/<int:spec_id>/loci',
				endpoint='lociList')

api.add_resource(LociAPItypon,
				version+'/NS/species/<int:spec_id>/loci/<int:id>',
				endpoint='loci')

api.add_resource(LociFastaAPItypon,
				version+'/NS/species/<int:spec_id>/loci/<int:id>/fasta',
				endpoint='lociFasta')

api.add_resource(AlleleListAPItypon,
				version+'/NS/species/<int:spec_id>/loci/<int:loci_id>/alleles',
				endpoint='alleleList')

api.add_resource(AlleleAPItypon,
				version+'/NS/species/<int:spec_id>/loci/<int:loci_id>/alleles/<int:allele_id>',
				endpoint='allele')
				
api.add_resource(SequencesAPItypon,
				version+'/NS/sequences/<int:seq_id>',
				endpoint='sequences')

api.add_resource(SequencesListAPItypon,
				version+'/NS/sequences',
				endpoint='sequencesNumber')

api.add_resource(IsolatesListAPItypon,
				version+'/NS/species/<int:spec_id>/isolates',
				endpoint='isolatesList')

api.add_resource(IsolatesAPItypon,
				version+'/NS/isolates/<int:isol_id>',
				endpoint='isolates')

api.add_resource(IsolatesAllelesAPItypon,
				version+'/NS/isolates/<int:isol_id>/alleles',
				endpoint='isolatesAlleles')

api.add_resource(IsolatesProfileAPItypon,
				version+'/NS/isolates/<int:isol_id>/schemas/<int:id>',
				endpoint='isolatesProfiles')

api.add_resource(LociSequencesAPItypon,
				version+'/NS/species/<int:spec_id>/loci/<int:loci_id>/sequences',
				endpoint='lociSequences')

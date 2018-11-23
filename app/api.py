from app import app
from flask_restful import Api
from app.resources.resources_typon import NS, profile
from app.resources.resources_typon import SpeciesListAPItypon, SpeciesAPItypon
from app.resources.resources_typon import SchemaListAPItypon, SchemaLociAPItypon, SchemaAPItypon, SchemaZipAPItypon
from app.resources.resources_typon import LociListAPItypon, LociAPItypon, LociFastaAPItypon, LociSequencesAPItypon, LociUniprotAPItypon
from app.resources.resources_typon import AlleleListAPItypon, AlleleAPItypon, SequencesAPItypon, SequencesListAPItypon
from app.resources.resources_typon import IsolatesAPItypon, IsolatesAllelesAPItypon, IsolatesListAPItypon, IsolatesProfileAPItypon,IsolatesLociAPItypon,IsolatesUserListAPItypon

#version="/v1"
version="/"+app.config['API_VERSION']

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

api.add_resource(LociUniprotAPItypon,
				version+'/NS/species/<int:spec_id>/loci/<int:id>/uniprot',
				endpoint='lociUniprot')

api.add_resource(AlleleListAPItypon,
				version+'/NS/species/<int:spec_id>/loci/<int:loci_id>/alleles',
				endpoint='alleleList')

api.add_resource(AlleleAPItypon,
				version+'/NS/species/<int:spec_id>/loci/<int:loci_id>/alleles/<int:allele_id>',
				endpoint='allele')
				
api.add_resource(SequencesAPItypon,
				version+'/NS/sequences/<string:seq_id>',
				endpoint='sequences')

api.add_resource(SequencesListAPItypon,
				version+'/NS/sequences',
				endpoint='sequencesNumber')

api.add_resource(IsolatesListAPItypon,
				version+'/NS/species/<int:spec_id>/isolates',
				endpoint='isolatesList')

api.add_resource(IsolatesAPItypon,
				version+'/NS/species/<int:spec_id>/isolates/<string:isol_id>',
				endpoint='isolates')

api.add_resource(IsolatesAllelesAPItypon,
				version+'/NS/species/<int:spec_id>/isolates/<string:isol_id>/alleles',
				endpoint='isolatesAlleles')

api.add_resource(IsolatesUserListAPItypon,
				version+'/NS/species/<int:spec_id>/user/isolates',
				endpoint='isolatesUser')

api.add_resource(IsolatesLociAPItypon,
				version+'/NS/species/<int:spec_id>/isolates/<string:isol_id>/loci/<int:locus_id>',
				endpoint='isolatesLoci')

api.add_resource(IsolatesProfileAPItypon,
				version+'/NS/species/<int:spec_id>/isolates/<string:isol_id>/schemas/<int:id>',
				endpoint='isolatesProfiles')

api.add_resource(LociSequencesAPItypon,
				version+'/NS/species/<int:spec_id>/loci/<int:loci_id>/sequences',
				endpoint='lociSequences')

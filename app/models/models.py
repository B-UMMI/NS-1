from app import db

SPECIES_NAME_SIZE = 2048

class Species(db.Model):
	name = db.Column(db.String(SPECIES_NAME_SIZE), primary_key=True)
	schemas = db.relationship('Schema', backref='species_id', lazy='dynamic')
	loci = db.relationship('Loci', backref='species_id', lazy='dynamic')
	alleles = db.relationship('Allele', backref='species_id', lazy='dynamic')

	def __init__(self, name):
		self.name = name

	def __repr__(self):
		return '<Species %r>' % (self.name)


class Schema(db.Model):
	identifier = db.Column(db.Integer, primary_key=True)
	loci = db.Column(db.String(2048))
	description = db.Column(db.String(2048))
	species_name = db.Column(db.String(SPECIES_NAME_SIZE),
							 db.ForeignKey('species.name'))

	def __init__(self, identifier, loci, description, species_name):
		self.identifier = identifier
		self.loci = loci
		self.description = description 
		self.species_id = species_name # 'species_id' is the backref 
									   # declared on the Species Model 

	def __repr__(self):
		return '<Schema %d: %r> (from %r)' % \
				(self.identifier, self.description, self.species_id)


class Loci(db.Model):
	identifier = db.Column(db.Integer, primary_key=True)
	aliases = db.Column(db.String(2048))
	allele_number = db.Column(db.Integer)
	species_name = db.Column(db.String(SPECIES_NAME_SIZE),
							 db.ForeignKey('species.name'))
	alleles = db.relationship('Allele', backref='locus_id', lazy='dynamic')

	def __init__(self, identifier, aliases, allele_number, species_name):
		self.identifier = identifier
		self.aliases = aliases
		self.allele_number = allele_number
		self.species_id = species_name # 'species_id' is the backref 
									   # declared on the Species Model 

	def __repr__(self):
		return '<Loci %d: %r [%d]> (from %r)' % \
			   (self.identifier, self.aliases, self.allele_number, self.species_id)


class Allele(db.Model):
	identifier = db.Column(db.Integer, primary_key=True)
	time_stamp = db.Column(db.DateTime)
	sequence = db.Column(db.String(8192))
	species_name = db.Column(db.String(SPECIES_NAME_SIZE),
							 db.ForeignKey('species.name'))
	locus = db.Column(db.Integer,
					  db.ForeignKey('loci.identifier'))


	def __init__(self, identifier, time_stamp, sequence, species_name, locus_id):
		self.identifier = identifier
		self.time_stamp = time_stamp
		self.sequence = sequence
		self.species_id = species_name # 'species_id' is the backref 
									   # declared on the Species Model
		self.locus_id = locus_id # 'locus_id' is the backref 
							     # declared on the Loci Model

	def __repr__(self):
		return '<Allele %d> (from %r - %r @ %r)' % \
			   (self.identifier, self.species_id, self.locus_id, self.time_stamp)

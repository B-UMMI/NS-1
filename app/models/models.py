from app import db

SPECIES_NAME_SIZE = 2048

# NOTE: Decide String sizes for each case.
# TODO: Indexes?
# TODO: Relationships

class Species(db.Model):
	name = db.Column(db.String(SPECIES_NAME_SIZE), primary_key=True)
	schemas = db.relationship('Schema', backref='species_id', lazy='dynamic')

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
	alleles = db.Column(db.String(2048))

	def __init__(self, identifier, aliases, alleles):
		self.identifier = identifier
		self.aliases = aliases
		self.alleles = alleles

	def __repr__(self):
		return '<Loci %d: %r>' % (self.identifier, self.aliases)


class Allele(db.Model):
	identifier = db.Column(db.Integer, primary_key=True)
	time_stamp = db.Column(db.DateTime)
	sequence = db.Column(db.String(8192))

	def __init__(self, identifier, time_stamp, sequence):
		self.identifier = identifier
		self.time_stamp = time_stamp
		self.sequence = sequence

	def __repr__(self):
		return '<Allele %d: %r>' % (self.identifier, self.time_stamp)
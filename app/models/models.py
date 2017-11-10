#from app import db,bcrypt, app
from app import db
import datetime
from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin
SPECIES_NAME_SIZE = 2048



#~ class Species(db.Model):
	#~ name = db.Column(db.String(SPECIES_NAME_SIZE), primary_key=True)
	#~ schemas = db.relationship('Schema', backref='species_id', lazy='dynamic')
	#~ loci = db.relationship('Loci', backref='species_id', lazy='dynamic')
#~ 
	#~ def __init__(self, name):
		#~ self.name = name
#~ 
	#~ def __repr__(self):
		#~ return '<Species %r>' % (self.name)
#~ 
#~ 
#~ class Schema(db.Model):
	#~ identifier = db.Column(db.Integer, primary_key=True, autoincrement=True)
	#~ id_per_species = db.Column(db.Integer)
	#~ description = db.Column(db.String(2048))
	#~ species_name = db.Column(db.String(SPECIES_NAME_SIZE),
							 #~ db.ForeignKey('species.name'))
#~ 
	#~ def __init__(self, description, species_name,id_per_species):

		#~ self.id_per_species = id_per_species
		#~ self.description = description 
		#~ self.species_id = species_name # 'species_id' is the backref 
									   #~ # declared on the Species Model 
#~ 
	#~ def __repr__(self):
		#~ return '<Schema %d: %r> (from %r)' % \
				#~ (self.id_per_species, self.description, self.species_id)
#~ 
#~ schema_loci = db.Table('schema_loci',
    #~ db.Column('schema_id', db.Integer, db.ForeignKey('schema.identifier')),
    #~ db.Column('loci_id', db.Integer, db.ForeignKey('loci.identifier'))
#~ )
#~ 
#~ class Loci(db.Model):
	#~ identifier = db.Column(db.Integer, primary_key=True, autoincrement=True)
	#~ id_per_species = db.Column(db.Integer)
	#~ aliases = db.Column(db.String(2048))
	#~ allele_number = db.Column(db.Integer)
	#~ species_name = db.Column(db.String(SPECIES_NAME_SIZE),
							 #~ db.ForeignKey('species.name'))

	#~ 
	#~ alleles = db.relationship('Allele', backref='loci_id', lazy='dynamic')
	#~ schema = db.relationship('Schema', secondary=schema_loci,
                            #~ backref=db.backref('schema_loci', lazy='dynamic'))
	#~ 
#~ 
	#~ def __init__(self, aliases, allele_number, species_name, id_per_species):
		#~ self.aliases = aliases
		#~ self.allele_number = allele_number
		#~ self.id_per_species = id_per_species
		#~ self.species_name = species_name # 'species_id' is the backref 
									   #~ # declared on the Species Model 
#~ 
	#~ def __repr__(self):
		#~ return '<Loci %d: %r [%d] [%r]> (from %r)' % \
			   #~ (  self.id_per_species, self.aliases, self.allele_number,self.alleles, self.species_name )
#~ 
#~ 
#~ class Allele(db.Model):
	#~ identifier = db.Column(db.Integer, primary_key=True, autoincrement=True)
	#~ id_per_locus = db.Column(db.Integer)
	#~ time_stamp = db.Column(db.DateTime)
	#~ sequence = db.Column(db.String(8192))
	#~ locus = db.Column(db.Integer,
					  #~ db.ForeignKey('loci.identifier'))
#~ 
#~ 
	#~ def __init__(self,id_per_locus, time_stamp, loci_id, sequence):
		#~ self.time_stamp = time_stamp
		#~ self.sequence = sequence
		#~ self.id_per_locus = id_per_locus
									   #~ # declared on the Species Model
		#~ self.locus = loci_id # 'locus_id' is the backref 
							     #~ # declared on the Loci Model
#~ 
	#~ def __repr__(self):
		#~ return '<Allele %d> ( %r @ %r)' % \
			   #~ (self.id_per_locus, self.sequence, self.time_stamp)



class Base(db.Model):
	__abstract__ = True
	id = db.Column(db.Integer, primary_key=True)
	created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
	modified_at = db.Column(db.DateTime, default=db.func.current_timestamp(),
							onupdate=db.func.current_timestamp())


roles_users = db.Table('roles_users',
					db.Column('user_id', db.Integer(),
							db.ForeignKey('auth_user.id')),
					db.Column('role_id', db.Integer(),
							db.ForeignKey('auth_role.id')))


class Role(Base, RoleMixin):
	__tablename__ = 'auth_role'
	name = db.Column(db.String(80), nullable=False, unique=True)
	description = db.Column(db.String(255))

	def __init__(self, name):
		self.name = name

	def __repr__(self):
		return '<Role %r>' % self.name


class User(Base, UserMixin):
	__tablename__ = 'auth_user'
	email = db.Column(db.String(255), nullable=False, unique=True)
	password = db.Column(db.String(255), nullable=False)
	first_name = db.Column(db.String(255))
	last_name = db.Column(db.String(255))
	active = db.Column(db.Boolean())
	confirmed_at = db.Column(db.DateTime())
	last_login_at = db.Column(db.DateTime())
	current_login_at = db.Column(db.DateTime())
	# Why 45 characters for IP Address ?
	# See http://stackoverflow.com/questions/166132/maximum-length-of-the-textual-representation-of-an-ipv6-address/166157#166157
	last_login_ip = db.Column(db.String(45))
	current_login_ip = db.Column(db.String(45))
	login_count = db.Column(db.Integer)
	roles = db.relationship('Role', secondary=roles_users,
							backref=db.backref('users', lazy='dynamic'))

	def __repr__(self):
		return '<User %r>' % self.email
		


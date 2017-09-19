SQLALCHEMY_DATABASE_URI = 'postgresql://msilva:msilva@localhost/test'
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECURITY_PASSWORD_HASH = 'pbkdf2_sha512'
SECURITY_TRACKABLE = True
SECRET_KEY = 'super-secret'
SECURITY_PASSWORD_SALT = 'something_super_secret_change_in_production'
WTF_CSRF_ENABLED = False

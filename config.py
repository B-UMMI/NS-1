SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:mypostgres@localhost/test'
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECURITY_PASSWORD_HASH = 'pbkdf2_sha512'
SECURITY_TRACKABLE = True
SECRET_KEY = ''
SECURITY_PASSWORD_SALT = ''
WTF_CSRF_ENABLED = False
BASE_URL="http://137.205.69.51/app/v1/NS/"
API_VERSION="v1"
DEFAULTHGRAPH="<http://localhost:8890/test>"
VIRTUOSO_USER=''
VIRTUOSO_PASS=''
LOCAL_SPARQL='http://localhost:8890/sparql'
UNIPROT_SPARQL='http://sparql.uniprot.org/sparql'
DBPEDIA_SPARQL='http://dbpedia.org/sparql/'
DOWNLOAD_FOLDER='/home/ubuntu/schemas_zip'

URL_SEND_LOCAL_VIRTUOSO='http://localhost:8890/DAV/test_folder/data'

##
SECURITY_HASHING_SCHEMES= ['plaintext']
SECURITY_DEPRECATED_HASHING_SCHEMES= []

##
CELERY_BROKER_URL= 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND= 'redis://localhost:6379/0'

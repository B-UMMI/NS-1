import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    """ Configuration class for the application """

    SECRET_KEY = ''
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgres@localhost/test'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECURITY_PASSWORD_HASH = 'pbkdf2_sha512'
    SECURITY_TRACKABLE = True
    SECURITY_CONFIRMABLE = False
    SECURITY_REGISTERABLE = True
    SECURITY_PASSWORD_SALT = ''
    SECURITY_SEND_REGISTER_EMAIL = False
    SECURITY_MSG_INVALID_PASSWORD = ('Your username/password do not match our records', 'error')
    SECURITY_MSG_USER_DOES_NOT_EXIST = ('Your username/password do not match our records', 'error')
    #WTF_CSRF_ENABLED = False
    #LOGIN_DISABLED = True
    
    ##
    SECURITY_HASHING_SCHEMES= ['plaintext']
    SECURITY_DEPRECATED_HASHING_SCHEMES= []

    ## EMAIL CONFIGS
    MAIL_SERVER = ''
    MAIL_PORT = 8025
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['your-email@example.com']

    # VIRTUOSO CONFIGS
    #BASE_URL="http://localhost/app/v1/NS/"
    BASE_URL="http://127.0.0.1:5000/NS/api/"
    DEFAULTHGRAPH="http://localhost:8890/test2"
    VIRTUOSO_USER=''
    VIRTUOSO_PASS=''
    LOCAL_SPARQL='http://localhost:8890/sparql'
    UNIPROT_SPARQL='http://sparql.uniprot.org/sparql'
    DBPEDIA_SPARQL='http://dbpedia.org/sparql/'

    URL_SEND_LOCAL_VIRTUOSO='http://localhost:8890/DAV/test_folder/data'

    #DOWNLOAD_FOLDER=''

    # CELERY CONFIG
    CELERY_BROKER_URL= 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND= 'redis://localhost:6379/0'
    
    # FLASK-RESTPLUS CONFIG
    SWAGGER_UI_JSON_EDITOR = True
    RESTPLUS_MASK_SWAGGER = False

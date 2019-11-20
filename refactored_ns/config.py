import os
import datetime
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    """ Configuration class for the application """

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess' # only for debug
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgres@localhost/ref_ns_sec'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECURITY_PASSWORD_HASH = 'pbkdf2_sha512'
    SECURITY_TRACKABLE = True
    SECURITY_CONFIRMABLE = False
    SECURITY_REGISTERABLE = True
    SECURITY_RECOVERABLE = True
    SECURITY_EMAIL_SENDER = "ns_no-reply@localhost.com"
    SECURITY_PASSWORD_SALT = ''
    SECURITY_SEND_REGISTER_EMAIL = False
    SECURITY_MSG_INVALID_PASSWORD = ('Your username/password do not match our records', 'error')
    SECURITY_MSG_USER_DOES_NOT_EXIST = ('Your username/password do not match our records', 'error')
    #WTF_CSRF_ENABLED = False
    #LOGIN_DISABLED = True
    ##
    SECURITY_HASHING_SCHEMES= ['plaintext']
    SECURITY_DEPRECATED_HASHING_SCHEMES= []

    ## JWT Config
    JWT_SECRET_KEY = 'super-secret' # CHANGE THIS!!!
    JWT_TOKEN_LOCATION = ['headers']
    JWT_ACCESS_TOKEN_EXPIRES = datetime.timedelta(hours=3)
    #JWT_REFRESH_TOKEN_EXPIRES = datetime.timedelta(days=30) #default
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = ''
    
    # Only allow JWT cookies to be sent over https. Production -> True
    JWT_COOKIE_SECURE = False 
    
    # Enable csrf double submit protection
    JWT_COOKIE_CSRF_PROTECT = True 

    # Set the cookie paths, so that you are only sending your access token
    # cookie to the access endpoints, and only sending your refresh token
    # to the refresh endpoint. Technically this is optional, but it is in
    # your best interest to not send additional cookies in the request if
    # they aren't needed.
    
    # JWT_ACCESS_COOKIE_PATH = ""
    # JWT_REFRESH_COOKIE_PATH = ""
    
    # Send  CSRF double submit values back directly to the caller
    #JWT_CSRF_IN_COOKIES = False



    ## EMAIL CONFIGS
    MAIL_SERVER = 'localhost'
    MAIL_PORT = 8025
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['your-email@example.com']

    # VIRTUOSO CONFIGS
    #BASE_URL="http://localhost/app/v1/NS/"
    #BASE_URL="http://127.0.0.1:5000/NS/api/"
    BASE_URL="http://10.105.85.84/NS/api/"
    DEFAULTHGRAPH="http://localhost:8890/test2"
    VIRTUOSO_USER='demo'
    VIRTUOSO_PASS='chewiens'
    LOCAL_SPARQL='http://localhost:8890/sparql'
    UNIPROT_SPARQL='http://sparql.uniprot.org/sparql'
    DBPEDIA_SPARQL='http://dbpedia.org/sparql/'

    URL_SEND_LOCAL_VIRTUOSO='http://localhost:8890/DAV/test_folder/data'

    DOWNLOAD_FOLDER='/home/pcerqueira/Lab_Software/refactored_ns/ns_security/schema_zip'

    # CELERY CONFIG
    CELERY_BROKER_URL= 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND= 'redis://localhost:6379/0'
    
    # FLASK-RESTPLUS CONFIG
    SWAGGER_UI_JSON_EDITOR = True
    RESTPLUS_MASK_SWAGGER = False

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from SPARQLWrapper import SPARQLWrapper
from flask_cors import CORS, cross_origin


#~ from rq import Queue
#~ from rq.job import Job
#~ from worker import conn

from celery import Celery

app = Flask(__name__)
CORS(app)
app.config.from_object('config')

##remove when in production
#~ app.config['SECURITY_HASHING_SCHEMES'] = ['plaintext']
#~ app.config['SECURITY_DEPRECATED_HASHING_SCHEMES'] = []
##
db = SQLAlchemy(app)


virtuoso_server=SPARQLWrapper(app.config['LOCAL_SPARQL'])
uniprot_server=SPARQLWrapper(app.config['UNIPROT_SPARQL'])
dbpedia_server=SPARQLWrapper(app.config['DBPEDIA_SPARQL'])

#### test celery
#~ app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
#~ app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)


from app import api, models




if __name__ == '__main__':
	app.run(debug=True,threaded=True)

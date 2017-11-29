from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from SPARQLWrapper import SPARQLWrapper
from flask_cors import CORS, cross_origin

app = Flask(__name__)
CORS(app)
app.config.from_object('config')

##remove when in production
app.config['SECURITY_HASHING_SCHEMES'] = ['plaintext']
app.config['SECURITY_DEPRECATED_HASHING_SCHEMES'] = []
##
db = SQLAlchemy(app)

virtuoso_server=SPARQLWrapper(app.config['LOCAL_SPARQL'])
uniprot_server=SPARQLWrapper(app.config['UNIPROT_SPARQL'])

from app import api, models


if __name__ == '__main__':
	app.run(debug=True,threaded=True)

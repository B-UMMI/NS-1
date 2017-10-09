from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from SPARQLWrapper import SPARQLWrapper

app = Flask(__name__)
app.config.from_object('config')
db = SQLAlchemy(app)

virtuoso_server=sparql=SPARQLWrapper('http://localhost:8890/sparql')

from app import api, models


if __name__ == '__main__':
	app.run(debug=True)

from flask import Flask, Blueprint, g
from flask.sessions import SecureCookieSessionInterface
from flask_login import LoginManager, user_loaded_from_header
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
#from flask_mail import Mail
from flask_bootstrap import Bootstrap
#from flask_moment import Moment
from flask_security import Security, SQLAlchemyUserDatastore
from flask_restplus import Api, marshal_with
#from flask_marshmallow import Marshmallow
from flask_cors import CORS, cross_origin
# from flask_talisman import Talisman

from celery import Celery
from config import Config

app = Flask(__name__)
CORS(app)
app.config.from_object(Config)

# # Disable Session Cookie generation
# class CustomSessionInterface(SecureCookieSessionInterface):
#     """Disable default cookie generation."""
    
#     def should_set_cookie(self, *args, **kwargs):
#         return False

#     """Prevent creating session from API requests."""
#     def save_session(self, *args, **kwargs):
#         if g.get('login_via_header'):
#             #print("Custom session login via header")
#             return
#         return super(CustomSessionInterface, self).save_session(*args, **kwargs)

# app.session_interface = CustomSessionInterface()

# @user_loaded_from_header.connect
# def user_loaded_from_header(self, user=None):
#     g.login_via_header = True

login_manager = LoginManager(app)
#login_manager.init_app(app)


## HTTPS config

# Content Security Policy
# csp = {
#     'default-src': '\'self\''
# }
# talisman = Talisman(app, content_security_policy=csp)

# get db
db = SQLAlchemy(app)

# provide migration
migrate = Migrate(app, db)

# Pretty Things
bootstrap = Bootstrap(app)

# Pretty date and time
#moment = Moment(app)

# API

# Define a blueprint to change the endpoint for the documentation of the API (Swagger)
blueprint = Blueprint("api", __name__, url_prefix='/NS/api')


# Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)


# API authorizations
authorizations = {
    'apikey' : {
        'type' : 'apiKey',
        'in' : 'header',
        'name' : 'X-API-KEY'
    }
}

api = Api(blueprint,
          title="Nomenclature Server API",
          version="2.0",
          doc="/docs",
          authorizations=authorizations)
#name_space = api.namespace('/NS/api/docs', description='Nomenclature Server API')

app.register_blueprint(blueprint)



from app import models, routes

if __name__ == "__main__":
    app.run(Threaded=True, debug=True)

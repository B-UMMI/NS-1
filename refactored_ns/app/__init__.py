from flask import Flask, render_template
#from flask.sessions import SecureCookieSessionInterface
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_bootstrap import Bootstrap
#from flask_moment import Moment
from flask_security import Security, SQLAlchemyUserDatastore, user_registered
from flask_restplus import Api, marshal_with
#from flask_marshmallow import Marshmallow
from flask_cors import CORS
# from flask_talisman import Talisman
#from flask_seasurf import SeaSurf
from flask_jwt_extended import JWTManager
from celery import Celery
from config import Config



#get db
db = SQLAlchemy()
# provide migration
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
bootstrap = Bootstrap()
celery = Celery(__name__, broker=Config.CELERY_BROKER_URL)
security = Security()
#csrf = SeaSurf()


####### Config jwt ##############################################################
jwt = JWTManager()


# Create a function that will be called whenever create_access_token
# is used. It will take whatever object is passed into the
# create_access_token method, and lets us define what custom claims
# should be added to the access token.

user_roles_dict = {"<Role Admin>": "Admin",
                   "<Role Contributor>": "Contributor",
                   "<Role User>": "User"}

@jwt.user_claims_loader
def add_claims_to_access_token(user):
    return {'roles': user_roles_dict[str(user.roles[0])]}


# Create a function that will be called whenever create_access_token
# is used. It will take whatever object is passed into the
# create_access_token method, and lets us define what the identity
# of the access token should be.
@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.id

#################################################################################

def create_app(config_class=Config):
    app = Flask(__name__)
    CORS(app)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)
    celery.conf.update(app.config)
    datastore = SQLAlchemyUserDatastore(db, models.User, models.Role)
    security.init_app(app, datastore=datastore)
    #csrf.init_app(app)
    jwt.init_app(app)

    # Custom error templates
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404

    from app.api import blueprint as api_bp
    app.register_blueprint(api_bp)

    from app.front_end import front_end_blueprint
    app.register_blueprint(front_end_blueprint)

    @user_registered.connect_via(app)
    def user_registered_sighandler(app, user, confirm_token, **extra):
        print("User created successfully ")
        default_role = datastore.find_role("User")
        datastore.add_role_to_user(user, default_role)
        db.session.commit()

    # Send user to Virtuoso
    # userid = user_datastore.get_user(user.email).id
    # new_user_url = baseURL+"users/"+str(userid)
    # newUserRole = "User"
    # sparql_query = 'INSERT DATA IN GRAPH <' + defaultgraph + '> { <'+new_user_url+'> a <http://xmlns.com/foaf/0.1/Agent>; typon:Role "' + newUserRole + '"^^xsd:string}'
    # result = aux.send_data(sparql_query, url_send_local_virtuoso, virtuoso_user, virtuoso_pass)

    # print(user.id)
    # userid = user_datastore.get_user(user).id
    # print(str(userid))

    return app


from app import models
datastore_cheat = SQLAlchemyUserDatastore(db, models.User, models.Role)

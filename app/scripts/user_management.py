from app import db, app
#~ from flask import abort,g,request
#~ from flask_restful import Resource, reqparse, marshal, fields
from app.models.models import User, Role, Auxiliar
from flask_security import Security, SQLAlchemyUserDatastore
import requests,json
import time

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

baseURL=app.config['BASE_URL']
defaultgraph=app.config['DEFAULTHGRAPH']
virtuoso_user=app.config['VIRTUOSO_USER']
virtuoso_pass=app.config['VIRTUOSO_PASS']
url_send_local_virtuoso=app.config['URL_SEND_LOCAL_VIRTUOSO']

def send_data(sparql_query):
	url = url_send_local_virtuoso
	headers = {'content-type': 'application/sparql-query'}
	r = requests.post(url, data=sparql_query, headers=headers, auth=requests.auth.HTTPBasicAuth(virtuoso_user, virtuoso_pass))

	#sometimes virtuoso returns 405 God knows why ¯\_(ツ)_/¯ retry in 2 sec
	if r.status_code >201:
		time.sleep(2)
		r = requests.post(url, data=sparql_query, headers=headers, auth=requests.auth.HTTPBasicAuth(virtuoso_user, virtuoso_pass))
    
	return r

def main():
	parser = argparse.ArgumentParser(
        description="This program creates the user and returns the token")
	parser.add_argument('-u', nargs='?', type=str, help='user email', required=True)
	parser.add_argument('-p', nargs='?', type=str, help='password', required=True)

	args = parser.parse_args()
	new_mail = args.u
	new_pass = args.p
	
	#~ new_mail='admin@ns.com'
	#~ new_pass='dfgvxc234gefg34qweqwesdfsqweqwe'
	if not user_datastore.get_user(new_mail):
		user_datastore.create_user(email=new_mail, password=new_pass)
		db.session.commit()
		userid=user_datastore.get_user(new_mail).id
		new_user_url=baseURL+"users/"+str(userid)
		result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_user_url+'> a <http://xmlns.com/foaf/0.1/Agent>.}')
		r = requests.post('http://127.0.0.1:5000/login', data=json.dumps({'email':new_mail, 'password':new_pass}), headers={'content-type': 'application/json'})
		print (r.json())
		if result.status_code == 201 :
			return "User created", 201		
		else:
			return "Sum Thing Wong", result.status_code
	
	r = requests.post('http://127.0.0.1:5000/login', data=json.dumps({'email':new_mail, 'password':new_pass}), headers={'content-type': 'application/json'})
	print (r.json())
	return 'user already created'

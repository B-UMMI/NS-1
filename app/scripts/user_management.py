import sys
import os
path_2_app=os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(path_2_app)

from app import db, app
#~ from flask import abort,g,request
#~ from flask_restful import Resource, reqparse, marshal, fields
from app.models.models import User, Role, Auxiliar
from flask_security import Security, SQLAlchemyUserDatastore
import requests,json
import time
import argparse
#from flask.app import db


# Setup Flask-Security
with app.app_context():
	user_datastore = SQLAlchemyUserDatastore(db, User, Role)
#security2 = Security(app, user_datastore)

baseURL=app.config['BASE_URL']
defaultgraph=app.config['DEFAULTHGRAPH']
virtuoso_user=app.config['VIRTUOSO_USER']
virtuoso_pass=app.config['VIRTUOSO_PASS']
url_send_local_virtuoso=app.config['URL_SEND_LOCAL_VIRTUOSO']


#some helpful links, this needs to be changed somewhere in the future :)
#https://realpython.com/token-based-authentication-with-flask/
#
#the implementation was based on https://mandarvaze.github.io/2015/01/token-auth-with-flask-security.html

#check https://pythonhosted.org/Flask-Security/api.html#flask_security.datastore.UserDatastore.create_user 



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
        description="This program creates manages the users, create new and get token, get token or change password")
	parser.add_argument('-u', nargs='?', type=str, help='user email', required=True)
	parser.add_argument('-p', nargs='?', type=str, help='password', required=False)
	parser.add_argument('--role', nargs='?', type=str, help='Admin or User', required=True)
	parser.add_argument('--new', nargs='?', type=str, help='new password, ', required=False, default=False)

	args = parser.parse_args()
	new_mail = args.u
	new_pass = args.p
	new_password2change = args.new
	newUserRole = args.role
	
	
	roles=['Admin','User']
	if newUserRole not in roles:
		print("role needs to be one of: ")
		print(roles)
		return
	
	
	if not new_pass and not new_password2change:
		print("no user password provided or new password to reset the user")
		return
	
	#chewie@ns.com
	#sdfkjsdfhkqjwheqwkjasdjn
	
	
	with app.app_context():
		
		#very stupid way to change password but that's what I managed to do quickly
		#if reset just delete the user, recreate it and change the id to the previous one
		if isinstance(new_password2change, str):
			
			if not user_datastore.get_user(new_mail):
				print("User not known, give correct email, use -h on how to use")
				return
			else:
				olduser=user_datastore.get_user(new_mail)
				userid_old=olduser.id
				
				user_datastore.delete_user(olduser)
			
				#delete the user	
				userid=user_datastore.get_user(new_mail)
				
				#create the user with same email and new password
				user_datastore.create_user(email=new_mail, password=new_password2change)
				db.session.commit()
				
				#usercreated, get the user, change the id to the old one and commit
				newuser=user_datastore.get_user(new_mail)
				newuser_id=newuser.id
				newuser.id = userid_old
				
				#~ newuser.id = 1
				db.session.add(newuser)
				db.session.commit()
				
				print("user old id:" +str(userid_old))
				print("user new id: " +str(user_datastore.get_user(new_mail).id))
				print(newuser)
				
				
				r = requests.post('http://127.0.0.1:5000/login', data=json.dumps({'email':new_mail, 'password':new_password2change}), headers={'content-type': 'application/json'})
				print (r.json())
				if r.status_code > 201 :
					print( "Sum Thing Wong sending the user to virtuoso")
					return	
				else:
					print("User created")
					return
				
				
		if not user_datastore.get_user(new_mail):
			print("new user")
			user_datastore.create_user(email=new_mail, password=new_pass)
			db.session.commit()
			userid=user_datastore.get_user(new_mail).id
			new_user_url=baseURL+"users/"+str(userid)
			result = send_data('INSERT DATA IN GRAPH '+defaultgraph+' { <'+new_user_url+'> a <http://xmlns.com/foaf/0.1/Agent>; typon:Role "'+newUserRole+'"^^xsd:string}')
			r = requests.post('http://127.0.0.1:5000/login', data=json.dumps({'email':new_mail, 'password':new_pass}), headers={'content-type': 'application/json'})
			print (r.json())
			if result.status_code > 201 :
				print( "Sum Thing Wong")
				return
			else:
				print("User created")
				return
		
		print("user already exists")
		r = requests.post('http://127.0.0.1:5000/login', data=json.dumps({'email':new_mail, 'password':new_pass}), headers={'content-type': 'application/json'})
		print (r.json())
	return 'user already created'


if __name__ == '__main__':
	main()

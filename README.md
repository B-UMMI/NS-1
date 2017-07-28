# About:
This project is to be used in association with chewBBaca (https://github.com/mickaelsilva/chewBBACA/) for a RESTful way of navigating through the data available (and eventually have the data synced between users). It was and will continue to be developed at iMM (instituto de Medicina Molecular) Lisbon.

# Overview:
To run this you'll need:
- python 3.xxx (developed on 3.5.2)
- flask
- flask-restful
- flask-sqlalchemy
- Some type of Database setup (e.g. postgresql, sqlite, ...)
- (Optional/Recommended) virtualenv


# Detailed instructions:
1. Set up your Database (usually involves creating a user and initializing a database/schema)

2. Open the 'config.py' file (located on the root folder) and replace the 'SQLALCHEMY_DATABASE_URI' value with the corresponding one for your use case (for examples check: http://flask-sqlalchemy.pocoo.org/2.1/config/#connection-uri-format)

3. Open a terminal and type 'python3' (if you're using venv don't forget to activate it OR issue the command like so: 'flask/bin/python3'). Note that instead of 'python3' you might only have 'python' (maybe you have both). As long as it is version 3.xxx there's probably no problem. 
 3.1 Inside the interactive python shell initialize the Database:
 	 <<< from app import db
 	 <<< db.drop_all()
 	 <<< db.create_all()
 	 <<< exit()

4. Having exited the python shell, you should now be able to run the application with: './run.py' (if needed set permissions: )

5. You can now open a new terminal and use curl to test if the application is working: 'curl -i  http://localhost:5000/NS' properly. You can check more curl examples within the 'app/resources/resources.py' file associated with each GET/POST methods.

# Props to
Bruno Gonçalves, João Carriço, Mickael Silva and Tiago Jesus for the support on the development of this app.

# Nomenclature Server

## About:
This project main aim is to be used in association with chewBBaca_NS ( <https://github.com/B-UMMI/chewBBACA/tree/chewie_NS> ). The Nomenclature Server aims to provide a free MLST data repository (wgMLST, cgMLST,etc).

## notes:
 * The implementation enforces that every sequence needs to translate into a Coding Sequence. This will also be used to query the uniprot database for more info on the protein sequence.
 * Every submited sequence is hashed and checked against the database.
 * Sequences are species independent, while schemas, loci and isolates are not.
 * Every new species added needs to be found at <https://www.uniprot.org/taxonomy/> (exact string comparison). For instance: when adding `Acinetobacter calcoaceticus/baumannii complex` it will be mapped to <https://www.uniprot.org/taxonomy/909768>.
 * The presented project is a basic implementation of the ontology **TypOn: the microbial typing ontology** ( <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4290098/> ).

## Overview:
To run this you'll need (installation of the following requirements are covered at the detailed instructions) :
- python 3.xxx (developed on 3.5.2)
- flask
- virtualenv
- Some type of Database setup (e.g. postgresql, sqlite, ...)
- virtuoso triple store (developed on 06.01.3127)

# Installation detailed instructions:

1. get the app:
   1. create a folder where the app will be stored
   2. git pull the repository for the folder

2. Virtuoso installation
	1.  Ubutunu installation (see also <http://vos.openlinksw.com/owiki/wiki/VOS/VOSUbuntuNotes>)
`sudo apt-get install aptitude`
`sudo aptitude install  virtuoso-opensource`.  
Other dists (see <http://vos.openlinksw.com/owiki/wiki/VOS>).
	2. Usually the daemon is started after installation, kill the process or stop it
	3. copy the virtuoso.db file to /var/lib/virtuoso-opensource-6.1/db/ (replace if already existing). This file is preloaded with the typon and the configuration necessary to be used with the application.
	4. start manually virtuoso (use it in a screen environment)
`sudo virtuoso-t -fd`
	5. configuring your virtuoso instance
check http://localhost/8890 on your browser and go to conductor, default admin of virtuoso is set as u:dba p:dba
**change the password** of dba at "system admin" -> "user accounts". Also change the user "demo" password (default password is "demo" and **should be changed**). The "demo" user will be the one used to contact with the Nomenclature server application.

3. Install nginx
`sudo apt-get install nginx`
`sudo ufw allow 'Nginx HTTP'`
    1. Configure nginx for the application:  
We are going to route virtuoso and the application, which is in port 8890 and 5000 respectively. 
Create new server configuration, save the file in /etc/nginx/sites-available/myconf.conf and copy the following to the file:
```
server {
    listen 80;
    client_header_buffer_size 30k;
    large_client_header_buffers 4 30k; 
 
    location /app/ {
	rewrite ^/app/(.*) /$1  break;
        proxy_pass http://127.0.0.1:5000;
    }
	location / {
	proxy_pass http://127.0.0.1:8890;
            }
	}
```
Enable new configuration by creating a symbolic link in sites-enabled directory.  
`sudo ln -s /etc/nginx/sites-available/myconf.conf /etc/nginx/sites-enabled/`

4. Install redis for queue management
`sudo apt install redis-server`

5. Install postgres and create a new database called "test" with password "postgres" (change at your own preference):  
`sudo -i -u postgres`  
`psql`  
`CREATE database test;`  
#change password  
`\password postgres`  

6. Configure the app
   1. (Optional/Recommended) On the app folder run 'python3 -m venv flask' (or 'python' as long as it's calling version 3.xxx)
   2. install dependencies:  
`sudo pip3 install -r requirements.txt`
   3. Open the 'config.py' file (located on the root folder) and replace the 'SQLALCHEMY_DATABASE_URI' value with the corresponding one for your use case (for examples check <http://flask-sqlalchemy.pocoo.org/2.1/config/#connection-uri-format>). Configure the other values in config.py: SECRET_KEY, SECURITY_PASSWORD_SALT, BASE_URL (this will be used to define the resources URI), VIRTUOSO_USER, VIRTUOSO_PASS (VIRTUOSO_USER is "demo" and VIRTUOSO_PASS the new password you defined).
   4. Open a terminal and type 'python3' (if you're using venv don't forget to activate it OR issue the command like so: 'flask/bin/python3'). Note that instead of 'python3' you might only have 'python' (maybe you have both). As long as it is version 3.xxx there's probably no problem. 
   5. Inside the interactive python shell initialize the Database:
 		- from app import db
 		- db.drop_all()
 		- db.create_all()
 		- exit()

    6. Having exited the python shell, you should now be able to run the application with: './run.py' (if needed set permissions: chmod a+x run.py). Also take into consideration to run it on a screen environment.

# API described at:

<https://app.swaggerhub.com/apis/mickaelsilva/nomenclature_server/1.0.0#/>

# First time usage:

1. Create the "admin" user:
   1. Admin user will be the first user to be created. Usear creation is only reservered to the person with access to the app server. To create a user, use the `user_management.py` script at `$path2App/app/scripts/`, provide an email and a pass and it will return your token.
   2. The Created "admin" user is the only allowed to create a schema. **Schema creation is not allowed to other users**.
2. Create Schemas:
   1. Create a Schema based on a set of fasta files:  
Use the `load_schema.py` script at `$path2App/app/scripts/` (use the `-h` flag for more info on how to use). `-t` flag is to be used with the token made on 1.
   2. Create a Schema based on a set of loci already on the nomenclature server:  
Use the `load_schema_no_fasta.py` script at `$path2App/app/scripts/` (use the `-h` flag for more info on how to use). `-t` flag is to be used with the token made on 1.

# Future work
 - try latest virtuoso version (latest 6.x.xxx or 7)
 - improve users management
 - improve isolates associated metadata
 - improve api user inputs sanitization


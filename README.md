# About:
This project is to be used in association with chewBBaca (https://github.com/mickaelsilva/chewBBACA/) for a RESTful way of navigating through the data available (and eventually have the data synced between users). It was and will continue to be developed at iMM (instituto de Medicina Molecular) Lisbon.

# Overview:
To run this you'll need:
- python 3.xxx (developed on 3.5.2)
- flask
- flask-restful
- flask-sqlalchemy
- (Optional/Recommended) virtualenv
- Some type of Database setup (e.g. postgresql, sqlite, ...)
Except the last point everything can be downloaded using pip.

# Detailed Instructions:
0. (Optional/Recommended) On the root folder run 'python3 -m venv flask' (or 'python' as long as it's calling version 3.xxx)

1. Set up your Database (usually involves creating a user and initializing a database/schema)

2. Open the 'config.py' file (located on the root folder) and replace the 'SQLALCHEMY_DATABASE_URI' value with the corresponding one for your use case (for examples check: http://flask-sqlalchemy.pocoo.org/2.1/config/#connection-uri-format)

3. Open a terminal and type 'python3' (if you're using venv don't forget to activate it OR issue the command like so: 'flask/bin/python3'). Note that instead of 'python3' you might only have 'python' (maybe you have both). As long as it is version 3.xxx there's probably no problem. 

4. Inside the interactive python shell initialize the Database:
 	- from app import db
 	- db.drop_all()
 	- db.create_all()
 	- exit()

5. Having exited the python shell, you should now be able to run the application with: './run.py' (if needed set permissions: )

6. You can now open a new terminal and use curl to test if the application is working: 'curl -i  http://localhost:5000/NS' properly. You can check more curl examples within the 'app/resources/resources.py' file associated with each GET/POST methods.

# Detailed Example Usage:
### API Endpoints available:
- /NS/species/
- /NS/species/{species name}
- /NS/species/{species name}/schema/
- /NS/species/{species name}/schema/{schema id}
- /NS/species/{species name}/loci/
- /NS/species/{species name}/loci/{loci id}
- /NS/species/{species name}/loci/{loci id}/allele/
- /NS/species/{species name}/loci/{loci id}/allele/{allele id}

Running locally and considering the endpoints above we can (using a browser) list:
1. Species:
	> http://localhost:5000/NS/species 
2. Schemas for the species 'acinetobacter':
	> http://localhost:5000/NS/species/acinetobacter
3. Loci for species 'acinetobacter':
	> http://localhost:5000/NS/species/acinetobacter/loci
4. Specific allele with id 5 for species 'acinetobacter' and loci with id 1
	> http://localhost:5000/NS/species/acinetobacter/loci/1/allele/5
(Just precede the URLs with 'curl' if you want to use a terminal to GET the information, e.g. 'curl http://localhost:5000/NS/')


### Fields accepted to POST:
###### Species:
 - name
###### Schema:
 - id
 - loci
 - description
###### Loci:
 - id
 - aliases
 - allele_number
###### Allele:
 - id
 - time_stamp
 - sequence

Taking the field above in consideration, we can insert (POST) data using curl like so:
1. Species:
	> curl -i  http://localhost:5000/NS/species -d 'name=acinetobacter'
2. Schema:
	> curl -i http://localhost:5000/NS/species/bacteria/schema -d 'id=3' -d 'loci=XXXX' -d 'description=Acinetobacter spp.'
3. Loci:
	> curl -i http://localhost:5000/NS/species/bacteria/loci -d 'id=1' -d 'aliases=lociful' -d 'allele_number=40'
4. Allele:
	> curl -i http://localhost:5000/NS/species/bacteria/loci/1/alleles -d 'id=5' -d 'time_stamp=2017-07-24T17:16:59.688836' -d 'sequence=ACTCTGT'


# Props to
Bruno Gonçalves, João Carriço, Mickael Silva and Tiago Jesus for the support on the development of this app.

# AUTOMATED-USER-PUBLIC-INFORMATION-INTELLIGENCE-SYSTEM

### Purpose

The proposed system is designed and developed to provide individuals with comprehensive understanding of their digital presence across the web. It aims to address the next critical needs: Digital Footprint Awareness, Privacy Risk Assessment and Continuous Monitoring.

The project followed a hybrid development methodology. Initially the waterfall approach for the core system development was employed. Then the Scrum framework is planned to be used for maintenance and further feature enhancements or introductions. Such plan allows to (a) comply with initial time and operational requirements for the course work and then to (b) continuously respond to user feedback during the future work.

The system is specifically designed for individual end-users rather than marketing agencies or large organizations. It fills a gap in the current market, where most similar tools are enterprise focused. We prioritize user-centric design and privacy-first approach in the proposed system, as we aim to democratize access to personal digital intelligence tools.


### How to run

a) Original

1. `pip install --default-timeout=100 --no-cache-dir -r requirements.txt` (if new place)
2. `python backend/app.py` for dev/debug
3. Open `127.0.0.1:5000` in your browser
4. Enjoy ;)

b) Docker

1. `docker run -p 5000:5000 info-intelligence-system`
2. Open `127.0.0.1:5000` in your browser
3. Enjoy ;)

if updated the project, run

0. `export VERSION="1.0.0"` - your current version
1. `pip install pipreqs` (if done for the first time)
2. `pipreqs . --force` (some requirements should be manually added, specified below)
3. `docker build -t info-intelligence-system:$VERSION --build-arg APP_VERSION=$VERSION .`
4. `docker run -p 5001:5000 --env-file .env info-intelligence-system:$VERSION`

Requirements that may 
be overwritten by `pipreqs`, 
but have to be manually checked 
and manually added ot requirements.txt

- `Werkzeug==2.2.2` - 
necessary to run **Flask**
- `PyJWT==2.4.0`- 
sometimes pipreqs accidentally adds PyJWT==2.10.0, 
ensure that the correct version is used
- `crowdstrike-falconpy==1.5.0` - 
required by **Crowdstrike Falcon integration**
(dedicated SDK)
- `pypdf==5.4.0` -
required by pdf upload pipeline 
in particular (llama-index-readers-file, xhtml2pdf) for rag

c) Deploy with AWS Elastic Container
1. update credentials in `~/.aws/config`
2. connect aws cli using 
`aws ecr get-login-password --profile <profile> --region eu-north-1 | docker login --username AWS --password-stdin <...>eu-north-1.amazonaws.com`
3. build image again if needed
`docker build -t info-intelligence-system:$VERSION .`
 (do not to specify VERSION before" `export VERSION=<your version>`)
4. specify the remote
`docker tag info-intelligence-system:$VERSION <...>.eu-north-1.amazonaws.com/matsevytyi/info-intelligence-system:$VERSION`
5. push
`docker push <...>.eu-north-1.amazonaws.com/matsevytyi/info-intelligence-system:$VERSION`

d) Set up the database

The options are 
either **ChromaDB** (serverless, best for self use or POC)
or **AWS Postgress Aurora** (aws hosted, with load balancer and backups)

To set up **ChromaDB** just select the container that supports it
(it is already set in code, 
any updates should be done also in code with further container rebuilding)

To set up / update **AWS Postgress Aurora**, perform the next steps

0. Use **AWS Query Editor** if applicable (easy way)
1. Install postgresql client: `brew install psql`
2. obtain login info
`aws secretsmanager get-secret-value --secret-id <your cluster> --profile <your_profile> `
 (search for SecretString/username and SecretString/password) dbname=your_db_name 
3. `psql "host=database-1.<your_cluster> port=5432 user=<userma,e> sslmode=verify-full sslrootcert=<ad cert>"`

4. `CREATE DATABASE vector_;`
5. `\c vectordb`
6. `CREATE EXTENSION vector;`



### Acknowledgements

Developed by Andrii Matsevytyi as part of bachelor thesis at Vilnius University
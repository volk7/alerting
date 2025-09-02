This is an alerting platform written in python.  To run the project do the following:

Pre-requisites: docker, python 

From your local computer do the following

* Clone the project

 git clone https://github.com/volk7/alerting.git

 cd alerting

* Create an .env file (do an ls -la command to see the files)
 
 cd microservices

  cp .env_example .env

  ** modify the .env with your own settings and passwords

 * create a python environment (from the root of the project)

  python -m venv env

  source ./env/bin/activate

 * Install python dependencies

  pip install -r dashboard_requirements.txt

 * start the microservices via docker (from the root of the project) 

  cd microservices
  
  docker-compose up -d

 * Check to make sure all services are up

  docker ps
  
 * Start the react front end

** from the root of the project.  Make sure you are in the python environment
  
  python ./performance_dashboard.py

 * open a browser and go to http://localhost:5000
 
 in the website click the "Add Custom Alarm" button
 

** tail the logs using docker for the alarm-processor and alarm-scheduler

docker logs -f microservices-alarm-scheduler-1
docker logs -f microservices-alarm-processor-1

*** to scale test the alerting system.  From the python environment type the following

python ./thousand_alarm_test.py

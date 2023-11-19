FROM python:3.11-slim

RUN apt-get update && apt-get upgrade -y && apt-get install -y emacs &&\
    apt-get autoremove -y
	
# Install software 
RUN apt-get install -y git


# Clone the conf files into the docker container
RUN git clone https://github.com/ilya12077/futurebot.git
	
	
RUN cp -a ./futurebot/. /etc/futurebot/
RUN rm -r -f ./futurebot/

RUN pip install python-dotenv Flask waitress requests

ENV AM_I_IN_A_DOCKER_CONTAINER Yes
EXPOSE 8881/tcp
CMD ["python", "/etc/futurebot/main.py"]


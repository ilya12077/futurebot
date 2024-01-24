FROM python:3.11-slim

RUN apt-get update && apt-get upgrade -y && apt-get install -y emacs &&\
    apt-get autoremove -y
	
# Install software 
RUN apt-get install -y git

# Copy over private key, and set permissions
# Warning! Anyone who gets their hands on this image will be able
# to retrieve this private key file from the corresponding image layer
RUN echo "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNCQ2NwWk9WeDAxMkNGVW9JZlZVVlBJYUNKdXZOMzM2WXRiODkyMENrM2pYQUFBQUtDTG9yb05pNks2CkRRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQkNjcFpPVngwMTJDRlVvSWZWVVZQSWFDSnV2TjMzNll0Yjg5MjBDazNqWEEKQUFBRUQ0WjN0UUxGWG1Za29rMWFnSlFBWC9UeXo2ckFnaDMwTHVFSmV3NURzZURVSnlsazVYSFRYWUlWU2doOVZSVThobwpJbTY4M2ZmcGkxdnozYlFLVGVOY0FBQUFGbTF5TG1sc2VXRXVNVEl3TjBCbmJXRnBiQzVqYjIwQkFnTUVCUVlICi0tLS0tRU5EIE9QRU5TU0ggUFJJVkFURSBLRVktLS0tLQo=" | openssl base64 -A -d > /root/.ssh/id_ed25519
RUN chmod 700 /root/.ssh/id_ed25519

# Create known_hosts
RUN touch /root/.ssh/known_hosts
# Add bitbuckets key
RUN ssh-keyscan github.com >> /root/.ssh/known_hosts

# Clone the conf files into the docker container
RUN git clone git@github.com:ilya12077/futurebot.git
	
	
RUN cp -a ./futurebot/. /etc/futurebot/
RUN rm -r -f ./futurebot/

RUN pip install python-dotenv Flask waitress requests

ENV AM_I_IN_A_DOCKER_CONTAINER Yes
EXPOSE 8881/tcp
CMD ["python", "/etc/futurebot/main.py"]


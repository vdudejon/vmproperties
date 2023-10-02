FROM artifactory.ssnc.dev/docker-remote/python:3.11-alpine
WORKDIR /app
COPY app/ /app/
RUN apk add git
RUN pip install -r requirements.txt
CMD ["python", "vmproperties-mp.py"]

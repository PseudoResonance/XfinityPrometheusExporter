# syntax=docker/dockerfile:1
FROM python:3-alpine
RUN pip install --upgrade pip
COPY ./requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt
COPY ./app.py /opt/app.py
ENTRYPOINT ["python3", "/opt/app.py"]

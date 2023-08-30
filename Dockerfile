FROM python:3.11-slim

# Install system dependencies
RUN apt-get update \
    && apt-get install -y pkg-config default-libmysqlclient-dev gcc \
    && apt-get clean

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./
COPY config.ini ./config.ini

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "manage.py", "runserver", "0.0.0.0:8080"]
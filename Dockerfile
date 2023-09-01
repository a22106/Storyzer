FROM python:3.11-slim

# Install system dependencies
RUN apt-get update \
    && apt-get install -y pkg-config default-libmysqlclient-dev gcc \
    && apt-get clean

# Set environment variables
ENV PYTHONUNBUFFERED True
ENV APP_HOME /app

# Working directory
WORKDIR $APP_HOME

# Install python dependencies.
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

RUN python manage.py collectstatic --noinput

CMD ["python", "manage.py", "runserver", "0.0.0.0:8080"]
#to install the libraries 

pip install celery django django-celery-beat djangorestframework pandas sqlalchemy

#to migrate the database
python manage.py migrate

#to run server
python manage.py runserver 0.0.0.0:5000
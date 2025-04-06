@echo off
REM Create required directories
if not exist logs mkdir logs
if not exist run mkdir run

REM Start the application with Waitress (instead of Gunicorn)
python -m waitress --host=0.0.0.0 --port=8000 wsgi:app

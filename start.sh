#!/bin/bash

# Create required directories
mkdir -p logs run

# Start the application with Gunicorn
waitress --config gunicorn_config.py wsgi:app
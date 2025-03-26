#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys

def main():
    """Run administrative tasks for the Django project."""
    
    # Set the environment variable to tell Django where to find the settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'creditservice.settings')
    
    try:
        # Try to import the Django management command line utility
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # If Django is not installed, raise an error with a helpful message
        raise ImportError(
            "Couldn't import Django. Make sure it's installed and "
            "available in your Python environment. Did you forget to activate your virtual environment?"
        ) from exc
    
    # Execute the command line utility with the arguments provided
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()

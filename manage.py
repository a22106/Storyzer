#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import requests

def get_public_ip():
    try:
        return requests.get('https://api.ipify.org').text
    except requests.ConnectionError:
        return False
    except requests.Timeout:
        return False
    except Exception as e:
        print(e)
        return False

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'storyzer.settings')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    port = 8000
    
    for arg in sys.argv:
        if arg.startswith("--noreload"):
            continue
        if ":" in arg:
            _, port = arg.split(":")
            break
        
    public_ip = get_public_ip()
    if public_ip:
        print(f"Public address: http://{public_ip}:{port}")
    
    main()

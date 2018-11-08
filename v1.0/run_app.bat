@echo off
echo.

rem Set flask environmental variables.
set FLASK_APP=application.py
set FLASK_DEBUG=1

rem Create flask environment.
flask run
@echo on
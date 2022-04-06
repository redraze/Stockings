@echo off
echo.

:: Set environmental variables.
SET FLASK_APP=application.py
SET FLASK_DEBUG=1
SET APP_SECRET_KEY=......
SET MAIL_SERVER=smtp.sendgrid.net
SET MAIL_USERNAME=......
SET MAIL_PASSWORD=......
SET MAIL_DEFAULT_SENDER=......

:: Create flask environment.
python -m flask run
@echo on

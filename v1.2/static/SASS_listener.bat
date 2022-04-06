@ECHO off

rem While this program is running it will check for changes in the "styles.scss" once per second.
rem If changes are detected, the program will recompile the "styles.scss" file and overwrite the 
rem existing "styles.css" file.

ECHO.
ECHO Listening for changes in "styles.scss"...
:loop
	timeout 1 >NUL
	FOR %%I IN (styles.scss) DO ECHO %%~aI|find "a" >NUL||GOTO :loop
	ECHO.
	ECHO Changes found. 
	attrib -a styles.scss
	time /t
	ECHO Recompiling...
	ECHO.
	sass styles.scss styles.css|GOTO :loop
	GOTO :loop
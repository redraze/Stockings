@echo off

rem While this program is running it will listen for changes in the "styles.scss" file.
rem If changes are detected, the program will recompile the "styles.scss" file and overwrite the 
rem existing "styles.css" file.

echo.
echo Listening for changes in "styles.scss"...
:loop
	timeout 1 >nul
	for %%i in (styles.scss) do echo %%~ai|find "a" >nul||goto :loop
	echo.
	echo Changes found. 
	attrib -a styles.scss
	time /t
	echo Recompiling...
	echo.
	sass styles.scss styles.css|goto :loop
	goto :loop
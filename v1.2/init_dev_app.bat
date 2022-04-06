:: defines environmental variables and starts app
start run_app.bat

:: keeps news and tickers cache up to date
start daily_update.bat

:: listens for changes in 'styles.scss', compiles 'styles.css'
cd static
start SASS_listener.bat

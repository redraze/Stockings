:: starts app for local access
start run_app.bat

:: keeps news and tickers cache up to date
start daily_update.bat

:: listens for changes in 'styles.scss', compiles 'styles.css'
cd static
start SASS_listener.bat
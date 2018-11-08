import sqlite3
import feedparser
import logging
import requests

from flask import url_for
from time import sleep

from helpers import con, surround, get_time, get_news

def main():
	"""
	Updates the 'cache.db' database.
	
	ARGS:
		None
		
	RETURNS:
		None for success
		1 for error
		
	RASIES:
		None
	
	"""
	
	# RSS feed about the basics of investing in the stock market (provided by Nasdaq.com)
	url = 'http://articlefeeds.nasdaq.com/nasdaq/categories?category=Basics'
	
	# update the 'news' table of the cache
	if update_news(url) == 1:
		return 1
	print("News cache update complete.\n")
	
	
	# list of choice stocks to be displayed on the home page
	c_stocks = ['^GSPC', '^DJI', '^IXIC', '^RUT', 'CL=F', 'GC=F', 'SI=F', 'EURUSD=X', '^TNX', '^VIX', 'GBPUSD=X', 'JPY=X', 'BTC-USD', '^FTSE', '^N225']
	
	# updates the 'tickers' table of the cache
	if update_tickers(c_stocks) == 1:
		return 1
	print("\nTickers cache update complete.\n")
		
	# success
	return

def update_news(url):

	"""
	This program deletes the entries in the 'news' table of the 'cache.db' database,
	then uploads the 10 most recent articles from the provided RSS feed url.
	
	ARGS:
		parameter1: A url to an RSS feed in string form. ie: "http://sampleRSS.com"
	
	RETURNS:
		0 for success
		1 for error
		
	RAISES:
		raises exception to indicate that the maintainer has some maintaining to do...
	
	"""
	
	# get news
	news = get_news(url)
	
	try:
		# connect to database
		database = "cache.db"
		[conn, db] = con(database)
			
		# delete old news from table
		db.execute("DELETE FROM news WHERE 1=1")

		for entry in news:
			# compile news entry
			link = entry["link"]
			title = entry["title"]
			date = entry["date"]
			summary = entry["summary"]
			
			# insert news entry into table
			db.execute("INSERT INTO news" + 
				" ('link', 'title', 'date', 'summary')" +
				" VALUES("+link+","+title+","+date+","+summary+")")
		
		#update time stamp in 'news_last_updated' table
		db.execute("DELETE FROM news_last_updated WHERE 1=1")
		dt = surround(get_time())
		db.execute("INSERT INTO news_last_updated ('last_update') VALUES ("+dt+")")
		
		# success
		conn.commit()
		return 0
	
	# error
	except Exception as e:
		dt = get_time()
		logging.error(dt + " An error has occurred during news cache update.\n")
		logging.error(e)
		return 1

def update_tickers(c_stocks):
	"""
	Pulls stock information for list of tickers.
	
	ARGS:
		parameter1: list of stock symbols
	
	RETURNS:
		None
		
	RAISES:
		None
	"""
	
	# query Yahoo Finance for stock info
	info = []
	i = 0
	total = len(c_stocks)
	for s in c_stocks:
		url = 'https://query1.finance.yahoo.com/v7/finance/options/{}'.format(s)
		page = requests.get(url).json()
		
		# get previous close
		try:
			prev_close = page["optionChain"]["result"][0]["quote"]["regularMarketPreviousClose"]
		except:
			logging.error("no previous close found for {}".format(s))
			pass
		
		# format previous close price
		prev_close = float(prev_close)
		prev_close = "{:,.2f}".format(prev_close)
		prev_close = str(prev_close).replace(",","")

		# prepare entry and append to info
		entry = {'symbol':s, 'prev_close':prev_close}
		info.append(entry)
		
		# print progress to console
		i += 1
		print("{} of {} stock information gathered...".format(i, total))

	# connect to the "cache.db" database
	[conn, db] = con("cache.db")
	
	# clear old data from 'tickers' table
	db.execute("DELETE FROM tickers WHERE 1=1")
	
	# prepare info for insertion into 'tickers' table
	for i in range(len(info)):
		for key in info[i]:
			info[i][key] = surround(info[i][key])
	
	# update 'tickers' table in the database
	for entry in info:
		db.execute("INSERT INTO tickers"+
			" ('symbol', 'prev_close')"+
			" VALUES ("+entry['symbol']+
			","+entry['prev_close']+")")

	# success
	conn.commit()
	return
	
def intro_message():
	"""
	Prints the intro message.
	
	ARGS:
		None
		
	RETURNS:
		None
	
	RAISES:
		None
	
	"""
	print("\n" * 5)
	print("Now running cache updater. Press CTRL+C to quit.")
	print("\nThis program will update the cache once daily.")
	print("\n" * 5)
	return


# run main() once daily
while True:
	intro_message()
	if main() == 1:
		break
	dt = get_time()
	print("\n" + dt + " Cache update complete.\nGoing back to sleep...\n\n")
	sleep(86400)
import sqlite3, feedparser, logging, requests, json, os

from flask import url_for
from time import sleep

from helpers import con, surround, get_time, get_news

def main():
    """
    Updates the 'cache.db' database
    and the 'autocomplete.txt' file.
    
    ARGS:
        None
        
    RETURNS:
        None for success
        1 for error
        
    RASIES:
        None
    
    """
    
    # RSS feed about the basics of investing in the stock market (provided by Nasdaq.com)
    url = 'https://www.nasdaq.com/feed/rssoutbound?category=Investing'
    
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
        
    # update list of autcompelte terms
    if update_autocompete() == 1:
        return 1
    print("\nAutocomplete list update complete.\n")
    
    
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
    Scraps stock information from specified url and chaches the data in "cache.db".
    
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
    for symbol in c_stocks:
        url = 'https://query2.finance.yahoo.com/v7/finance/options/{}'.format(symbol)
        page = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}).json()

        # get previous close
        try:
            prev_close = page["optionChain"]["result"][0]["quote"]["regularMarketPreviousClose"]
        except:
            logging.error("no previous close found for {}".format(symbol))
            pass
        
        # format previous close price
        prev_close = float(prev_close)
        prev_close = "{:,.2f}".format(prev_close)
        prev_close = str(prev_close).replace(",","")
        
        # get name
        try:
            name = page['optionChain']['result'][0]['quote']['shortName']
        except Exception as e:
            logging.error("No shortName found for {}.".format(symbol))
            logging.error(e)
            try:
                name = page['optionChain']['result'][0]['quote']['longName']
            except Exception as e:
                logging.error("No longName found for {}.".format(symbol))
                logging.error(e)
                name = symbol
        
        # prepare entry and append to info
        entry = {'name':name, 'symbol':symbol, 'prev_close':prev_close}
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
        db.execute("INSERT INTO tickers ('name', 'symbol', 'prev_close') VALUES ("+entry['name']+', '+entry['symbol']+', '+entry['prev_close']+")")

    # success
    conn.commit()
    return
    
def update_autocompete():
    try:
        url = 'https://api.nasdaq.com/api/screener/stocks?download=true&marketcap=mega|large'
        page = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}).json()['data']['rows']

        # finds the top 250 market cap securities
        list = []
        for i in range(250):
            value = float(page[0]['marketCap'])
            index = 0

            # finds max market cap security
            for j in range(len(page)):
                if float(page[j]['marketCap']) > value:
                    value = float(page[j]['marketCap'])
                    index = j
                
            # adds max to list and removes max from page
            list.append([page[index]['symbol'], page[index]['name']])
            page = page[0:index] + page[index+1:]

        # reset vars
        page = list
        list = []

        # sorts list by symbol
        for i in range(len(page)):
            value = page[0][0]
            index = 0
            
            # finds alphabetically first symbol
            for j in range(len(page)):
                if page[j][0] < value:
                    value = page[j][0]
                    index = j

            # adds symbol to list and removes symbol from page
            list.append(page[index])
            page = page[0:index] + page[index+1:]
            
        # overwrite (or create) list in file system
        f = open('templates/autosuggestions.html', 'w')
        
        f.write('{% extends "nav.html" %}\n\n' +
                '{# Import title block  from "footer.html"#}\n' +
                '{% block title2 %}\n' +
                '\t{% block title1 %}{% endblock %}\n' +
                '{% endblock %}\n\n' +
                '{% block autosuggestions0 %}\n' +
                '<div id="autosuggestions" style="display: none;">')
        
        for i in range(len(list)):
            f.write(list[i][0] + ',' + list[i][1] + '\n')
        
        f.write('</div>\n' +
                '{% endblock %}\n\n' +
                '{# Import main block from "footer.html" #}\n' +
                '{% block main2 %}\n' +
                '\t{% block main1 %}{% endblock %}\n' +
                '{% endblock %}\n\n' +
                '{# Import footer block from "footer.html" #}\n' +
                '{% block footer1 %}\n' +
                '\t{% block footer0 %}{% endblock %}\n' +
                '{% endblock %}')
        
        f.close()
        
        # success
        return 0
    
    except Exception as e:
        dt = get_time()
        logging.error(dt + " An error has occurred during autcomplete update.\n")
        logging.error(e)
        return 1
    
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
    print("\nThis program will update the cache and autocomplete list once daily.")
    print("\nPress CTRL+C to quit.")
    print("\n" * 5)
    return


# run main() once daily
while True:
    intro_message()
    if main() == 1:
        break
    dt = get_time()
    print("\n" + dt + " Daily update complete.\nGoing back to sleep...\n\n")
    sleep(86400)
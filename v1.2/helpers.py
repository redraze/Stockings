import sqlite3
import requests
import logging
import feedparser
import datetime

from flask import redirect, request, session, url_for, flash
from functools import wraps
from lxml import html

def lookup(symbol):
    """
    Acquire current stock information.
    
    ARGS:
        parameter1: stock symbol
        
    RETURNS:
        dictionary containing information about stock searched. ie: {'name':(string), 'price':(float), 'symbol':(string)}
        conditionally, dictionry contains ...

        Returns 1 if results are empty
        Returns 2 if price is not found
        Returns 3 if market status not found
        
    RAISES:
        None
    """
    
    # format url
    url = 'https://query1.finance.yahoo.com/v7/finance/options/{}'.format(symbol)
    
    # send HTTP request and JSONify
    page = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}).json()
    if page['optionChain']['result'] == []:
        return 1
        
    # init dictionary
    info = {}
    
    # name
    try:
        info['name'] = page['optionChain']['result'][0]['quote']['shortName']
    except Exception as e:
        try:
            info['name'] = page['optionChain']['result'][0]['quote']['longName']
        except Exception as e:
            info['name'] = symbol
    
    # price
    try:
        info['price'] = page['optionChain']['result'][0]['quote']['regularMarketPrice']
    except Exception as e:
        return 2
    
    # is tradeable
    try:
        if page['optionChain']['result'][0]['quote']['quoteType'] != 'INDEX':
            info['tradeable'] = True
    except Exception as e:
        pass

    # market status
    try:
        page = page['optionChain']['result'][0]['quote']['marketState']
        if page != 'PRE' or page !=  'NORMAL' or page != 'POST':
            info['marketState'] = 1
    except Exception as e:
        return 3
        
    info['symbol'] = symbol
    
    # success
    return info

def surround(inp):
    """
    Formats input for SQL queries by surrounding it with quotes.
    
    ARGS:
        parameter1: string
    
    RETURNS:
        string surrounded by quotes
        
    RAISES:
        None
        
    """
    if inp is list:
        for i in range(len(inp)):
            inp[i] = "'"+str(inp[i])+"'"
        return inp
    return "'"+str(inp)+"'"

def con(database):
    """
    Connects to associated database.
    
    ARGS:
        database name
        
    RETURNS:
        list containing a sqlite3 connection object and cursor
        
    RAISES:
        None
    """
    
    conn = sqlite3.connect(database)
    db = conn.cursor()
    return [conn, db]

def cursor_data(c):
    """
    Extracts and parses data from a sqlite3.Cursor object

    ARGS:
        parameter1: sqlite3.Cursor object
        
    RETURNS:
        list of dictionaries parsed from sqlite3.Cursor object
            ie: [{"column1":column1_data1, "column2":column2_data1, ...}, {"column1":column1_data2, "column2":column2_data2, ...}, ...]
        
    RAISES:
        None
        
    """

    # pull column description
    d = []
    for i in range(len(c.description)):
        d.append(c.description[i][0])

    # fetch column entries
    c = c.fetchall()

    # compile list
    info = []
    for i in range(len(c)):
        # compile dictionary entry
        entry = {}
        for j in range(len(d)):
            entry[d[j]] = c[i][j]
        info.append(entry)	

    # success
    return info

def login_required(f):
    """
    Decorate routes to require login.
    http://flask.pocoo.org/docs/0.11/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            flash("You must log in to view that page.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def get_time():
    """
    Retrieves and parses current time stamp from the 'datetime' module. 
    
    ARGS:
        None
    
    RETURN:
        Current date and time, parsed.
        
    RAISES:
        None
    """
    
    dt = datetime.datetime.now()
    dt_parsed = dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt_parsed	

def usd(value):
    """
    Formats value as USD.

    ARGS:
        parameter1: float value
        
    RETURNS:
        value parsed into currency string (if able)
        or
        value (if unable)
        
    RAISES:
        None
        
    """
    try:
        value = float(value)
    except:
        return value
    if value >= 0:
        return "${:,.2f}".format(value)
    value *= (-1)
    return "(" + "${:,.2f}".format(value) + ")"
    
def form(s):
    """
    Formats data acquired via SQL query.
    
    ARGS:
        parameter1: string to be formatted
        
    RETURNS:
        apostrophe stripped string
        
    RAISES:
        None
    
    """
    
    # removes leading and trailing apostrophe's from string
    s = s.strip("'")
    
    # converts HTML hex back to characters
    s = s.replace("&#39;", "'")
    s = s.replace("&#8217;", "’")
    s = s.replace("&#8216;", '"')
    s = s.replace("&#8221;", "'")
    s = s.replace("&#8220;", "'")
    
    # success
    return s
    
def get_news(url):
    """
    Fetches the ten most recent news articles from an RSS feed.
    
    ARGS:
        parameter1: a url to the RSS feed
        
    RETURNS:
        a list of dictionaries containing each news article.
            ie: [{"link":link, "title":title, "date":date, "summary":summary}, {...}, ...]
            
    RAISES:
        None
        
    """
    
    # parse RSS feed into list of dictionaries
    feed = feedparser.parse(url)

    # no RSS feed articles for url
    if len(feed['entries']) == 0:
        return []
    
    # get first ten articles from the RSS feed
    news = []
    i = 0
    while True:
        if i == len(feed['entries']) or i > 30:
                break
            
        try:
            # get link to article
            link = feed["entries"][i]["link"]

            # get title of article
            title = feed["entries"][i]["title"]
            
            try:
                # get raw summary of article
                summary_raw = feed["entries"][i]["summary"]
                
                # format summary
                summary = ""
                for c in summary_raw:
                    if c == "<":
                        summary += "..."
                        break
                    summary += c
            except KeyError as e:
                logging.error("no summary for RSS feed article: {}".format(link))
                summary = "read more here..."
            
            # get raw date 
            date_raw = feed["entries"][i]["published_parsed"]
            
            if date_raw is None:
                date = feed["entries"][i]["published"]
            
            else:
                # format date
                year = str(date_raw.tm_year)
                months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
                month = months[date_raw.tm_mon - 1]
                day = str(date_raw.tm_mday)
                weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                wday = weekdays[date_raw.tm_wday]
                hour = str(date_raw.tm_hour)
                hour = "{:2}".format(hour).format(' ','0')
                min = str(date_raw.tm_min)
                min = "{:2}".format(min).replace(' ','0')
                date = hour + ":" + min + " - " + wday + " " + month + " " + day + ", " + year
            
            # compile entry and append to news list
            entry = {"link":link, "title":title, "date":date, "summary":summary}
            
            # sanitize entry
            for key in entry:
                # apostrophe
                entry[key] = entry[key].replace("&#39;", "'")
                # right single quotation mark
                entry[key] = entry[key].replace("’", "&#8217;")
                # left single quotation mark
                entry[key] = entry[key].replace('"', "&#8216;")
                # right double quotation mark
                entry[key] = entry[key].replace("'", "&#8221;")
                # left double quotation mark
                entry[key] = entry[key].replace("'", "&#8220;")
                # Weird ampersand formatting
                entry[key] = entry[key].replace("&amp;", "&")
                
                # prepare entry for sqlite queries
                entry[key] = surround(entry[key])
            
            # add entry to news list
            news.append(entry)
            
            # max 10 entries
            if len(news) == 10:
                break
            i += 1
            
        except Exception as e:
            logging.error(e)
            i += 1
            pass
            
    # success
    return news
    
def to_total(balance):
    """
    
    ARGS:
        parameter1: current balance (uninvested cash)
        
    RETURNS:
        total value of all owned securities and uninvested cash (formatted to USD)

    RAISES:
        None
        
    """

    # connect to database
    [conn, db] = con("stockings.db")

    # get stock portfolio for current user
    table = surround(session["p_table"])
    c = db.execute("SELECT * FROM "+table+" ORDER BY name")
    rows = cursor_data(c)
    
    for i in range(len(rows)):
        price = lookup(rows[i]['symbol'])['price']
        balance += rows[i]['amount'] * price
        
    return usd(balance)
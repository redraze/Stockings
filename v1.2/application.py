import hashlib
import datetime
import os

from flask import Flask, flash, redirect, render_template, request, session, url_for, Markup
from flask_session import Session
from flask_mail import Mail, Message
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)
app.secret_key = os.environ['APP_SECRET_KEY']
app.config.update(dict(
    MAIL_SERVER = os.environ['MAIL_SERVER'],
	MAIL_USE_TLS = True,		# if True, use port 587			!!!   DO NOT SET   !!!
	MAIL_USE_SSL = False,		# if True, use port 465			!!!  BOTH TO TRUE  !!!
    MAIL_PORT = 587,
    MAIL_USERNAME = os.environ['MAIL_USERNAME'],
    MAIL_PASSWORD = os.environ['MAIL_PASSWORD'],
	MAIL_DEFAULT_SENDER = os.environ['MAIL_DEFAULT_SENDER'],
    MAIL_SUPPRESS_SEND = False
))
mail = Mail(app)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["form"] = form
app.jinja_env.filters["to_total"] = to_total

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# news links
url_quote   = 'https://www.nasdaq.com/feed/rssoutbound?symbol={}'
url_general = 'https://www.investing.com/rss/stock_stock_picks.rss'

@app.route("/", methods=["GET"])
def home():
    """Displays homepage."""

    # connect to 'cache.db' database
    [conn, db] = con('cache.db')
    
    # get news from 'news' table
    news = db.execute("SELECT * FROM news")
    news = cursor_data(news)
    
    # get stock information from 'tickers' table
    ticker_info = db.execute("SELECT * FROM tickers")
    ticker_info = cursor_data(ticker_info)
    
    # insert query links into each entry in ticker_info
    for i in range(len(ticker_info)):
        name = ticker_info[i]['name']
        link = url_for('query', q=ticker_info[i]['symbol'])
        ticker_info[i]['link'] = link
        
        # format international stock symbols
        if "^" in name:
            name = name.strip("^") + "^"
            ticker_info[i]['name'] = name
    
    return render_template("home.html", news=news, ticker_info=ticker_info)

@app.route("/history", methods=["GET", "POST"])
@login_required
def history():
    # connect to database
    [conn, db] = con("stockings.db")

    # POST
    if request.method == "POST":
        # delete current and create a new history table
        table = surround(session["h_table"])
        db.execute("DROP TABLE "+table)
        db.execute("CREATE TABLE "+table+
            "('date_time' TEXT NOT NULL,"+
            " 'name' TEXT NOT NULL,"+
            " 'symbol' TEXT NOT NULL,"+
            " 'trans_type' TEXT NOT NULL,"+
            " 'price' FLOAT NOT NULL,"+
            " 'amount' INTEGER NOT NULL,"+
            " 'balance_change' FLOAT NOT NULL)")
    
        # success
        flash("History cleared!")
        conn.commit()
        return redirect(url_for('history'))

    # GET
    table = surround(session["h_table"])
    c = db.execute("SELECT * FROM "+table)
    rows = cursor_data(c)
    
    # insert link to each stock into each entry
    for i in range(len(rows)):
        link = url_for('query', q=[rows[i]['symbol']])
        rows[i]['link'] = link

    # get news
    news = get_news(url_general)
        
    # success
    if len(rows) != 0:
        return render_template("history.html", rows=rows, news=news)
    else:
    
        return render_template("history.html", news=news)

@app.route("/purchase", methods=["GET", "POST"])
@login_required
def purchase():
    # connect to database
    [conn, db] = con("stockings.db")

    # POST
    if request.method == "POST":
        """Complete purchase request"""
        # details from previous pages
        (amount, cost, new_balance) = session["purchase_details"]
        name = session["stock_info"]["name"]
        price = session["stock_info"]["price"]
        symbol = session["stock_info"]["symbol"]
        balance = session["balance"]
        
        # check for existing stock with matching name/symbol
        name = surround(name)
        symbol = surround(symbol)
        table = surround(session["p_table"])
        c = db.execute("SELECT *"
            " FROM "+table+
            " WHERE name="+name+
            " AND symbol="+symbol)
        rows = cursor_data(c)

        # update stock portfolio table
        if len(rows) == 0:
            amount = surround(amount)
            db.execute("INSERT INTO "+table+
                " ('name', 'symbol', 'amount')"
                " VALUES ("+name+","+symbol+","+amount+")")
        else:
            amount = surround(amount + rows[0]["amount"])
            db.execute("UPDATE "+table+
                " SET amount="+amount+
                " WHERE symbol="+symbol)

        # log recent purchase into history table
        table = surround(session["h_table"])
        date_time = surround(get_time())
        price = surround(price)
        trans_type = surround("Purchase")
        balance_change = surround(cost * (-1))
        db.execute("INSERT INTO "+table+
            " ('date_time', 'name', 'symbol', 'trans_type', 'price', 'amount', 'balance_change')"+
            " VALUES("+date_time+","+name+","+symbol+","+trans_type+","+price+","+amount+","+balance_change+")")

        # update and clear session details
        session["balance"] = new_balance
        session["purchase_details"] = None
        session["stock_info"] = None

        # update user's balance
        balance = surround(new_balance)
        id = surround(session["user_id"])
        db.execute("UPDATE 'users'"+
            " SET balance="+balance+
            " WHERE id="+id)

        # success
        conn.commit()
        flash("Stock purchased! New balance: " + usd(new_balance))
        return redirect(url_for("portfolio"))

    # GET
    return redirect(url_for("home"))

@app.route("/portfolio", methods=["GET", "POST"])
@login_required
def portfolio():
    # connect to database
    [conn, db] = con("stockings.db")

    """Display stock portfolio."""
    # GET
    if request.method == "GET":
        # get stock portfolio for current user
        table = surround(session["p_table"])
        c = db.execute("SELECT * FROM "+table+" ORDER BY name")
        rows = cursor_data(c)

        # insert current price per share and market state into each entry
        for i in range(len(rows)):
            info = lookup(rows[i]['symbol'])
            rows[i]['price'] = info['price']
            try:
                rows[i]['marketState'] = info['marketState']
            except KeyError:
                pass
        
        # insert link to each stock into each entry
        for i in range(len(rows)):
            link = url_for('query', q=[rows[i]['symbol']])
            rows[i]['link'] = link
        
        # insert market status into each entry
        
        # get news
        news = get_news(url_general)
        
        if len(rows) == 0:
            return render_template("portfolio.html", news=news)
        return render_template("portfolio.html", rows=rows, news=news)

    # POST
    """Stock liquidation confirmation."""
    
    # import session data
    data = session["data"]

    # update stock portfolio table
    table = surround(session["p_table"])
    for entry in data:
        symbol = surround(entry["symbol"])

        # get current number of stocks owned
        c = db.execute("SELECT *"+
            " FROM "+table+
            " WHERE symbol="+symbol)
        c = cursor_data(c)
        owned = c[0]["amount"]

        # delete stock from portfolio table if 0 shares are now owned...
        if owned == entry["amount"]:
            db.execute("DELETE FROM "+table+
                " WHERE symbol="+symbol)
        # ...or update number of shares owned
        else:
            amount = surround(owned - entry["amount"])
            db.execute("UPDATE "+table+
                " SET amount="+amount+
                " WHERE symbol="+symbol)

    # update session variables
    session["balance"] = session["new_balance"]
    session.pop("new_balance")
    session.pop("data")
    
    # update user balance
    balance = surround(session["balance"])
    id = surround(session["user_id"])
    db.execute("UPDATE users"+
        " SET balance="+balance+
        " WHERE id="+id)

    # log recent transaction(s) into history table
    for entry in data:
        date_time = surround(get_time())
        name = surround(entry["name"])
        symbol = surround(entry["symbol"])
        trans_type = surround("Liquidation")
        price = surround(entry["price"])
        amount = surround(entry["amount"])
        balance_change = surround(entry["gain"])
        db.execute("INSERT INTO "+session["h_table"]+
            " ('date_time', 'name', 'symbol', 'trans_type', 'price', 'amount', 'balance_change')"
            " VALUES("+date_time+","+name+","+symbol+","+trans_type+","+price+","+amount+","+balance_change+")")

    # success
    conn.commit()
    flash("Stocks sold! New balance: {}".format(usd(session["balance"])))
    return redirect(url_for("portfolio"))

def search(q):
    """Search function."""

    # check for correct formatting
    if "," in q:
        flash("You may search for only one symbol at a time.")
        return redirect(url_for("home"))

    # search for stock information on provided symbol
    session["stock_info"] = lookup(q)

    # ensure stock exists
    if session["stock_info"] == 1:
        flash("Could not find security with symbol \"{}\".".format(q))
        return redirect(url_for("home"))

    # ensure price was found
    if session["stock_info"] == 2:
        flash("Could not find market price for \"{}\".".format(q))
        return redirect(url_for("home"))

    # ensure market status was found
    if session["stock_info"] == 3:
        flash("No market status found for \"{}\".".format(q))
        return redirect(url_for("home"))

    # search for news on stock
    news = get_news(url_quote.format(q))
    
    # get number of stocks owned if logged in
    if "user" in session:
        
        # connect to database
        [conn, db] = con("stockings.db")

        table = surround(session["p_table"])
        symbol = surround(q)
        c = db.execute("SELECT * FROM "+table+
            " WHERE symbol="+symbol)
        c = cursor_data(c)
        if len(c) != 0:
            owned = c[0]["amount"]
        else:
            owned = 0
    
    # Flash messages
    try: 
        session['stock_info']['tradeable']
        try: 
            session['stock_info']['marketState']
        except KeyError:
            flash("Market is currently closed.")
    except KeyError:
        flash("{} is not tradeable on this platform.".format(session['stock_info']['name']))

    # render "quote.html" based on session['user']
    if "balance" in session:
        if owned != 0:
            return render_template("quote.html", info=session["stock_info"], news=news, balance=session["balance"], owned=owned)
        return render_template("quote.html", info=session["stock_info"], news=news, balance=session["balance"])
    return render_template("quote.html", info=session["stock_info"], news=news)

@app.route("/quote", methods=["GET", "POST"])
def quote():
    """Search for stock quote."""
    # POST
    if request.method == "POST":

        # ensure input
        if not request.form.get("symbol"):
            flash("You must enter a stock symbol to search.")
            return redirect(url_for("home"))

        # get and remember stock info
        symbol = request.form.get("symbol").upper()
        
        # pass symbol to search function
        return search(symbol)

    # GET
    return redirect(url_for("home"))

@app.route("/query/<q>", methods=["GET"])
def query(q):
    """Passes url query to search function."""
    q = q.strip("[").strip("]")
    q = form(q)
    
    return search(q)
    
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    # connect to database
    [conn, db] = con("stockings.db")

    """Buy shares of stock."""
    # POST
    if request.method == "POST":
        # variables from recent stock quote search
        balance = session["balance"]
        info = session["stock_info"]
        
        # ensure input is formatted corectly
        amount = request.form.get("amount")
        if amount.strip("-").replace(".","").isnumeric() is False:
            flash("Please enter a number.")
            return(search(session["stock_info"]["symbol"]))
        try:
            amount = int(amount)
        except ValueError:
            flash("Stockings Finance is unable to borker fractional shares. Sorry!")
            return(search(session["stock_info"]["symbol"]))
        if amount < 0:
            flash("Please enter a positive number.")
            return(search(session["stock_info"]["symbol"]))

        # calculate user's balance after transaction
        cost = float(amount) * float(info["price"])
        new_balance = balance - cost

        # check for sufficient funds
        if new_balance < 0:
            flash(Markup("Insufficient funds."))
            return(search(session["stock_info"]["symbol"]))

        # remember purchase details
        session["purchase_details"] = [amount, cost, new_balance]

        # continue to transaction confirmation page
        return render_template("buy.html", info=info, balance=balance, new_balance=new_balance, cost=cost, amount=amount)

    # GET
    else:
        return render_template("quote.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # connect to database
    [conn, db] = con("stockings.db")

    """Sell shares of stock."""
    # POST
    if request.method == "POST":

        # get input from posted form
        table = surround(session["p_table"])
        c = db.execute("SELECT * FROM "+table)
        c = cursor_data(c)
        inputs = []
        for row in c:
            inp = request.form.get(row["symbol"])
            if inp == "" or inp == None:
                continue
            symbol = row["symbol"]
            d = {'symbol':symbol, 'amount':inp}
            inputs.append(d)
        
        # ensure any input was posted
        if len(inputs) == 0:
            flash("Please enter an amount to sell.")
            return redirect(url_for("portfolio"))

        # ensure input was entered correctly
        for i in range(len(inputs)):
            try:
                inputs[i]["amount"] = int(inputs[i]["amount"])
            except ValueError:
                flash("Stockings Finance is unable to broker fractional shares. Sorry!")
                return redirect(url_for("portfolio"))
            if inputs[i]["amount"] < 0:
                flash("Please enter positive numbers.")
                return redirect(url_for("portfolio"))

        # ensure user has enough shares to sell desired amount
        for entry in inputs:
            for row in c:
                if row["symbol"] == entry["symbol"]:
                    if entry["amount"] > row["amount"]:
                        flash("You do not own enough of {}".format(row["name"]))
                        return redirect(url_for("portfolio"))
        
        # format data to send to sell.html
        data = []
        for entry in inputs:
            info = lookup(entry["symbol"])
            dat = {}
            dat["name"] = info["name"]
            dat["symbol"] = info["symbol"]
            dat["price"] = info["price"]
            dat["amount"] = entry["amount"]								# number of stocks to sell
            dat["gain"] = info["price"] * float(entry["amount"])		# monetary gain from selling stocks
            data.append(dat)

        # calculate new balance after transaction
        total_gain = float(0)
        for info in data:
            total_gain += info["gain"]
        new_balance = session["balance"] + total_gain

        # remember variables
        session["data"] = data
        session["new_balance"] = new_balance

        return render_template("sell.html", data=data, balance=session["balance"], total_gain=total_gain, new_balance=new_balance)

    # GET
    return redirect(url_for("portfolio"))

@app.route("/balance", methods=["GET", "POST"])
@login_required
def balance():
    """Displays balance services."""

    # connect to database
    [conn, db] = con("stockings.db")

    # get current user's balance and update session
    user = session['user']
    id = str(session['user_id'])
    c = db.execute("SELECT *"+
        " FROM users"+
        " WHERE id="+id)
    c = cursor_data(c)
    session['balance'] = float(c[0]['balance'])
    balance = session["balance"]

    # get stock portfolio for current user
    table = surround(session["p_table"])
    c = db.execute("SELECT * FROM "+table+" ORDER BY name")
    rows = cursor_data(c)

    # insert current price per share into each entry
    for i in range(len(rows)):
        info = lookup(rows[i]['symbol'])
        price = info['price']
        rows[i]['price'] = price
    
    # insert link to each stock into each entry
    for i in range(len(rows)):
        link = url_for('query', q=[rows[i]['symbol']])
        rows[i]['link'] = link

    for i in range(len(rows)):
        value = rows[i]['price'] * rows[i]['amount']
        rows[i]['value'] = value

    # tally up total value of cash and securities value
    total = balance
    for i in range(len(rows)):
        total += rows[i]['value']

    return render_template("balance.html", balance=balance, rows=rows, total=total)

@app.route("/unregister", methods=["GET", "POST"])
@login_required
def unregister():
    # connect to database
    [conn, db] = con("stockings.db")

    """Unregister current user"""
    # POST
    if request.method == "POST":
        
        # check password
        provided = request.form.get("password")
        provided = hashlib.sha512(provided.encode("UTF-8")).hexdigest()
        user = surround(session["user"])
        c = db.execute("SELECT * FROM USERS WHERE user="+user)
        c = cursor_data(c)
        password = c[0]['pw']
        if password != provided:
            flash("Incorrect password.")
            return render_template("unregister.html")
    
        # delete user from database, delete user portfolio/history tables, and clear session variables
        table = surround(session["user"]+"_portfolio")
        db.execute("DROP TABLE "+table)
        table = surround(session["user"]+"_history")
        db.execute("DROP TABLE "+table)
        user = surround(session["user_id"])
        db.execute("DELETE FROM users WHERE id="+user)
        conn.commit()
        session.clear()
    
        # success
        flash("Account deleted!")
        return redirect(url_for("home"))

    # GET
    return render_template("unregister.html")

@app.route("/reset", methods=["GET", "POST"])
@login_required
def reset():
    # POST
    if request.method == "POST":
        
        # CHECK PASSWORD
        # -----------------------------------------------------------------------------------------------
        
        # connect to database
        [conn, db] = con("stockings.db")
    
        # ensure password was submitted
        if not request.form.get("password"):
            flash("Must provide a password!")
            return render_template("reset.html")
        
        # ensure password doesn't contain quotes
        pw = request.form.get("password")
        if '"' in pw or "'" in pw:
            flash("Incorrect password.")
            return render_template("reset.html")
        
        # hash provided password
        hashed = surround(hashlib.sha512(request.form.get("password").encode("UTF-8")).hexdigest())

        # query database for username
        user_id = surround(session["user_id"])
        c = db.execute("SELECT *"+
            " FROM users"+
            " WHERE id="+user_id+
            " AND pw="+hashed)
        c = cursor_data(c)

        # check for registered user
        if len(c) < 1:
            flash("Invalid username and/or password.")
            return render_template("reset.html")

        # RESET PORTFOLIO
        # -----------------------------------------------------------------------------------------------
        
        # delete old portfolio table
        table = surround(session["user"]+"_portfolio")
        db.execute("DROP TABLE "+table)
        
        # create new portfolio table
        table = surround(session["p_table"])
        db.execute("CREATE TABLE "+table+" ("+
            "'name' TEXT NOT NULL,"+
            "'symbol' TEXT NOT NULL,"+
            "'amount' INTEGER NOT NULL)")
        
        # RESET HISTORY
        # -----------------------------------------------------------------------------------------------

        # drop old history table
        table = surround(session["user"]+"_history")
        db.execute("DROP TABLE "+table)
        
        # create new history table
        table = surround(session["h_table"])
        db.execute("CREATE TABLE "+table+" ("+
            "'date_time' TEXT NOT NULL,"+
            "'name' TEXT NOT NULL,"+
            "'symbol' TEXT NOT NULL,"+
            "'trans_type' TEXT NOT NULL,"+
            "'price' FLAOT NOT NULL,"+
            "'amount' INTEGER NOT NULL,"+
            "'balance_change' FLOAT NOT NULL)")
        
        # RESET BALANCE
        # -----------------------------------------------------------------------------------------------
        
        # reset balance in "stockings.db"
        balance = surround(float(5000))
        id = surround(session["user_id"])
        db.execute("UPDATE 'users'"+
            " SET balance="+balance+
            " WHERE id="+id)
        
        # update session variables
        session["balance"]      = float(5000)
        session["new_balance"]  = float(5000)
        
        # SUCCESS!
        # -----------------------------------------------------------------------------------------------
        conn.commit()
        flash("Your account has been successfully reset!")
        return redirect(url_for("balance"))
        
    # GET
    return render_template("reset.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    # check if already logged in
    if "user" in session:
        flash("You are already logged in.")
        redirect(url_for("home"))

    # connect to database
    [conn, db] = con("stockings.db")

    """Log user in."""
    # POST
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide a username!")
            return redirect(url_for("login"))

        # ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide a password!")
            return redirect(url_for("login"))
        
        # ensure username doesn't contain quotes
        user = request.form.get("username")
        if '"' in user or "'" in user:
            flash("Username not found.")
            return redirect(url_for("login"))
        
        # ensure password doesn't contain quotes
        pw = request.form.get("password")
        if '"' in pw or "'" in pw:
            flash("Incorrect password.")
            return redirect(url_for("login"))

        # hash provided password
        hashed = surround(hashlib.sha512(request.form.get("password").encode("UTF-8")).hexdigest())
        
        # query database for username
        user = surround(user)
        c = db.execute("SELECT *"+
            " FROM users"+
            " WHERE user="+user+
            " AND pw="+hashed)
        c = cursor_data(c)

        # check for registered user
        if len(c) < 1:
            flash("Invalid username and/or password.")
            return redirect(url_for("login"))

        # remember user information
        session["user_id"] = c[0]["id"]
        session["balance"] = float(c[0]["balance"])
        session["user"] = c[0]["user"]
        session["p_table"] = session["user"] + "_portfolio"
        session["h_table"] = session["user"] + "_history"

        # redirect user to home page
        flash('You were succesfully logged in. Welcome back, {}!'.format(session["user"]))
        return redirect(url_for("home"))

    # GET
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    """Log user out."""
    # forget session variables
    session.clear()

    # redirect user to login form
    flash('You were successfully logged out!')
    return redirect(url_for("home"))

@app.route("/register", methods=["GET", "POST"])
def register():

    """Register user."""
    # POST
    if request.method == "POST":

        # connect to database
        [conn, db] = con("stockings.db")

        # ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide a username.")
            return redirect(url_for("register"))

        # check for quotes in username
        user = request.form.get("username")
        if "'" in user or '"' in user:
            flash("Please exclude any single or double quotes in your username.")
            return redirect(url_for("register"))

        # ensure username isn't taken
        user = surround(user)
        c = db.execute("SELECT *"+
            " FROM users"+
            " WHERE user="+user)
        c = c.fetchall()
        if len(c) != 0:
            flash("Username already taken.")
            return redirect(url_for("register"))

        # ensure both password forms were completed
        if not request.form.get("password1"):
            flash("Must provide a password.")
            return redirect(url_for("register"))
        if not request.form.get("password2"):
            flash("Must provide matching passwords.")
            return redirect(url_for("register"))
            
        # ensure passwords match
        if request.form.get("password1") != request.form.get("password2"):
            flash("Passwords do not match.")
            return redirect(url_for("register"))

        # check for quotes in password
        pw = request.form.get("password1")
        if "'" in pw or '"' in pw:			
            flash("Please exclude any single or double quotes in your password.")
            return redirect(url_for("register"))
    
        # hash password
        hashed = hashlib.sha512(pw.encode("UTF-8")).hexdigest()
        
        # enter new user into database with hashed password
        hashed = surround(hashed)
        balance = surround(float(5000))
        db.execute("INSERT INTO users"+
            " (user, pw, balance)"+
            " VALUES("+user+","+hashed+","+balance+")")

        # remember user's ID, username, and balance
        c = db.execute("SELECT *"+
            " FROM users"+
            " WHERE user="+user)
        c = cursor_data(c)
        session["user_id"] = c[0]["id"]
        session["user"] = c[0]["user"]
        session["balance"] = float(c[0]["balance"])

        # create and remember portfolio table for new user
        session["p_table"] = session["user"] + "_portfolio"
        table = surround(session["p_table"])
        db.execute("CREATE TABLE "+table+" ("+
            "'name' TEXT NOT NULL,"+
            "'symbol' TEXT NOT NULL,"+
            "'amount' INTEGER NOT NULL)")

        # create and remember history table for new user
        session["h_table"] = session["user"] + "_history"
        table = surround(session["h_table"])
        db.execute("CREATE TABLE "+table+" ("+
            "'date_time' TEXT NOT NULL,"+
            "'name' TEXT NOT NULL,"+
            "'symbol' TEXT NOT NULL,"+
            "'trans_type' TEXT NOT NULL,"+
            "'price' FLAOT NOT NULL,"+
            "'amount' INTEGER NOT NULL,"+
            "'balance_change' FLOAT NOT NULL)")

        # success
        conn.commit()
        flash('Account successfuly registered! Welcome to the Stockings family, ' + session["user"] + "!")
        return redirect(url_for("home"))

    # GET
    return render_template("register.html")
    
@app.route("/info", methods=["GET", "POST"])
def info():

    """ Send a message."""
    # POST
    if request.method == "POST":
        # Get contact details
        a = request.form.get("contact", type=str)
        if a == "":
            a = 'no contact details provided'
        
        # Get message body
        b = request.form.get("body", type=str)
        if b == "":
            flash("Feedback not sent. Must provide a message.")
            return render_template("info.html")
        
        # Format and send message
        m = "From: " + a + '\n\nMessage: ' + b
        msg = Message(
                subject='Stockings feedback',
                recipients=[os.environ['MAIL_DEFAULT_SENDER']],
                body=m)
        try:
            mail.send(msg)
        except Exception as e:
            logging.error(e)
            flash("An error occured while attempting to send your message. Sorry!")
            return render_template("info.html")
        
        # Success!
        flash("Your message was sent! Thank you for your feedback.")
        return render_template("info.html")

    # GET
    return render_template("info.html")

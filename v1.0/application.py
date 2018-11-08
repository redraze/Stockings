import hashlib
import datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for, Markup
from flask_session import Session
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)
app.secret_key = b"iu&]=<SV(2f-*"

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

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

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
		symbol = ticker_info[i]['symbol']
		link = url_for('query', q=symbol)
		ticker_info[i]['link'] = link
		
		# format international stock symbols
		if "^" in symbol:
			symbol = symbol.strip("^") + "^"
			ticker_info[i]['symbol'] = symbol
	
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
	url = 'https://www.investing.com/rss/stock_stock_picks.rss'
	news = get_news(url)
		
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

		# insert current price per share into each entry
		for i in range(len(rows)):
			info = lookup(rows[i]['symbol'])
			price = info['price']
			rows[i]['price'] = price
		
		# insert link to each stock into each entry
		for i in range(len(rows)):
			link = url_for('query', q=[rows[i]['symbol']])
			rows[i]['link'] = link
		
		# get news
		url = 'https://www.investing.com/rss/stock_stock_picks.rss'
		news = get_news(url)
		
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

	# connect to database
	[conn, db] = con("stockings.db")

	# check for correct formatting
	if "," in q:
		message = "You may search for only one symbol at a time."
		return render_template("quote.html", message=message)

	# search for stock information on provided symbol
	session["stock_info"] = lookup(q)

	# ensure stock exists
	if session["stock_info"] == 1:
		message = "Could not find stock with symbol \"{}\".".format(q)
		return render_template("quote.html", message=message)

	# ensure both stock name and price exist
	if session["stock_info"] == 2 or session["stock_info"] == 3:
		message = "An error occurred while searching for \"{}\".".format(q)
		return render_template("quote.html", message=message)

	# search for news on stock
	url = 'http://articlefeeds.nasdaq.com/nasdaq/symbols?symbol={}'.format(q)
	news = get_news(url)
	
	# get number of stocks owned if logged in
	if "user" in session:
		table = surround(session["p_table"])
		symbol = surround(q)
		c = db.execute("SELECT * FROM "+table+
			" WHERE symbol="+symbol)
		c = cursor_data(c)
		if len(c) != 0:
			owned = c[0]["amount"]
		else:
			owned = 0
	
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
			message = "You must enter a stock symbol."
			return render_template("quote.html", message=message)

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
			return render_template("quote.html", info=info, balance=balance)
		try:
			amount = int(amount)
		except ValueError:
			flash("Please enter a whole number.")
			return render_template("quote.html", info=info, balance=balance)
		if amount < 0:
			flash("Please enter a positive number.")
			return render_template("quote.html", info=info, balance=balance)

		# calculate user's balance after transaction
		cost = float(amount) * float(info["price"])
		new_balance = balance - cost

		# check for sufficient funds
		if new_balance < 0:
			flash(Markup("Insufficient funds! <a href='/balance'>Add money to your account?</a>"))
			return render_template("quote.html", info=info, balance=balance)

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
				flash("Please ensure whole numbers were entered.")
				return redirect(url_for("portfolio"))
			if inputs[i]["amount"] < 0:
				flash("Please ensure positive numbers were entered.")
				return redirect(url_for("portfolio"))

		# ensure user has enough shares to sell desired amount
		for entry in inputs:
			for row in c:
				if row["symbol"] == entry["symbol"]:
					if entry["amount"] > row["amount"]:
						flash("You do not own enough shares of {}".format(row["name"]))
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

	# get current user's balance
	balance = session["balance"]

	# POST
	if request.method == "POST":

		# ensure deposit amount is formatted correctly
		deposit = request.form.get("amount").strip("$").replace(",","")
		try:
			deposit = float(deposit)
		except ValueError:
			flash("Please enter an amount.")
			return render_template("balance.html", balance=balance)
		if deposit < 0:
			flash("Withdrawal function not yet available...")
			return render_template("balance.html", balance=balance)

		# update user's balance and session["balance"]
		session["balance"] = balance + deposit
		new_balance = surround(session["balance"])
		id = surround(session["user_id"])
		db.execute("UPDATE users"
			" SET balance="+new_balance+
			" WHERE id="+id)

		conn.commit()
		flash(usd(deposit) + " has been deposited into your account.")
		return redirect(url_for("balance"))

	# GET
	return render_template("balance.html", balance=balance)

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
		flash("Account deleted! YOUR MONEY IS NOW OUR MONEY.")
		return redirect(url_for("home"))

	# GET
	return render_template("unregister.html")

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

		# hash password provided
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
	# connect to database
	[conn, db] = con("stockings.db")

	"""Register user."""
	# POST
	if request.method == "POST":

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
		balance = surround(float(0))
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
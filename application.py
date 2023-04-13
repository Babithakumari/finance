import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from helpers import apology, login_required, lookup, usd

# datetime object containing current date and time
now = datetime.now()

# dd/mm/YY H:M:S
dt_string = now.strftime("%d/%m/%Y %H:%M:%S")


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = cash[0]["cash"]
    data = db.execute("SELECT symbol,name,shares FROM display WHERE user_id = ?", session["user_id"])

    # Add current price of stocks and total price
    Total = 0
    for stock in data:
        share = lookup(stock["symbol"])
        stock["sharePrice"] = share["price"]
        stock["Total"] = stock["shares"] * share["price"]
        Total = Total+stock["Total"]

    return render_template("index.html", stocks=data, cash=cash, Total=Total + cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol is provided
        symbol = request.form.get("symbol")
        symbol = symbol.upper()
        if not symbol:
            return apology("symbol not provided", 400)

        # Ensure that symbol exists
        if lookup(symbol) == None:
            return apology("symbol not found", 400)

        # Ensure shares is provided
        shares = request.form.get("shares")
        if not shares:
            return apology("share not provided", 400)
        if shares.isnumeric() == False:
            return apology("invalid format", 400)

        shares = int(shares)

        # query database for cash
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = cash[0]["cash"]

        # Evaluate net worth of shares to buy
        net_worth = shares * lookup(symbol)["price"]

        # Avoid Buy if cash insufficient
        if net_worth > cash:
            return apology("Not enough cash to buy stock(s)", 400)

        # Update users cash after each buy
        cash = cash - net_worth
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])

        # Store purchase details
        name = lookup(symbol)["name"]
        share_price = lookup(symbol)["price"]
        db.execute("INSERT INTO transactions (user_id,symbol,name,shares,share_price,datetime) VALUES(?,?,?,?,?,?)",session["user_id"], symbol, name, shares, share_price, dt_string)

        total_shares = db.execute("SELECT shares FROM display WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)

        # if symbol not in transaction insert transaction details
        if len(total_shares) == 0:
            db.execute("INSERT INTO display (user_id,symbol,name,shares,share_price,datetime) VALUES(?,?,?,?,?,?)",session["user_id"], symbol, name, shares, share_price, dt_string)

        # if symbol in transaction Update transaction details
        else:
            shares = total_shares[0]["shares"]+shares
            db.execute("UPDATE display SET shares = ?,share_price = ?,datetime = ? WHERE user_id = ? AND symbol = ?",shares, share_price, dt_string, session["user_id"], symbol)

        # Redirect back to index
        return redirect("/")

    # User reached route via GET or redirected
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        symbol = request.form.get("symbol")
        data = lookup(symbol)

        if data == None:
            return apology("symbol not found", 400)

        else:
            return render_template("quoted.html", data=data)

    # User reached route via GET
    if request.method == "GET":
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password has atleast 8 characters and no special characters:
        elif len(password) < 8 or password.isalnum == False:
            return apology("Password must contain atleast 8 characters(letter/numbers only")

        # Ensure password confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must Confirm password", 400)

        # Ensure confirmation of password
        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("Passwords don't match!", 400)

        # Ensure username is unique
        Registrants = db.execute("SELECT username FROM users")
        for registrant in Registrants:
            if registrant["username"] == username:
                return apology("username already exists", 400)

        hash_password = generate_password_hash(password)

        # Store credentials of registered users
        db.execute("INSERT INTO users (username,hash) VALUES(?,?)", username, hash_password)

        # after register go to login page
        return redirect("/login")
    # User reached route via GET
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    SYMBOLS = db.execute("SELECT symbol FROM display WHERE user_id = ?", session["user_id"])

    # User reached route via POST(as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol is provided
        symbol = request.form.get("symbol")
        print(symbol)
        if not symbol:
            return apology("must provide symbol ", 400)

        # Ensure symbol is valid
        found = False
        for SYMBOL in SYMBOLS:
            if SYMBOL["symbol"] == symbol:
                found = True
                break
        if not found:
            return apology("must provide valid symbol", 400)

        # Ensure share is provided
        shares = request.form.get("shares")
        if not shares:
            return apology("must provide shares", 400)

        # Ensure valid entries
        if shares.isnumeric() == False:
            return apology("invalid format", 400)

        shares = int(shares)

        # prevent sale if share insufficient
        shares_owned = db.execute("SELECT shares FROM display WHERE user_id = ? AND symbol = ? ", session["user_id"], symbol)
        shares_owned = shares_owned[0]["shares"]

        if shares > shares_owned:
            return apology("Insufficient shares!", 400)

        # store sale details
        name = lookup(symbol)["name"]
        share_price = lookup(symbol)["price"]
        db.execute("INSERT INTO transactions (user_id,symbol,name,shares,share_price,datetime) VALUES(?,?,?,?,?,?)",session["user_id"], symbol, name, -shares, share_price, dt_string)

        # Update cash of user after sale
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = cash[0]["cash"]
        net_worth = shares * share_price
        cash = cash + net_worth
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])

        # Update shares of the user after sale
        shares = shares_owned - shares
        db.execute("UPDATE display SET shares = ?,share_price = ?,datetime = ?   WHERE user_id = ? AND symbol = ?",shares, share_price, dt_string, session["user_id"], symbol)

        # reroute to index
        return redirect("/")

    # User reached route via GET
    else:

        return render_template("sell.html", symbols=SYMBOLS)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

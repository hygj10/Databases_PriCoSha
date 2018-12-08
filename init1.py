#Import Flask Library
from flask import Flask, render_template, request, session, url_for, redirect
import pymysql.cursors
import hashlib

#Initialize the app from Flask
app = Flask(__name__)

#Configure MySQL
conn = pymysql.connect(host='127.0.0.1',
                       port = 3306,
                       user='root',
                       password='',
                       db='pricosha_new',
                       charset='utf8mb4',
                       cursorclass=pymysql.cursors.DictCursor)

#Define a route to hello function
@app.route('/')
def hello():
    cursor = conn.cursor();
    query = 'SELECT item_id, email_post, post_time, file_path,' \
            'item_name FROM contentitem WHERE post_time >= now() - INTERVAL 1 DAY' \
            ' AND is_pub = TRUE ORDER BY post_time DESC;'
    cursor.execute(query)
    data = cursor.fetchall()
    cursor.close()
    return render_template('index.html', posts=data)

#Define route for login
@app.route('/login')
def login():
    return render_template('login.html')

#Define route for register
@app.route('/register')
def register():
    return render_template('register.html')

#Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    #grabs information from the forms
    email = request.form['email']
    password = request.form['password']

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM person WHERE email = %s and password = %s'
    cursor.execute(query, (email, password))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None
    if(data):
        #creates a session for the the user
        #session is a built in
        session['email'] = email
        return redirect(url_for('home'))
    else:
        #returns an error message to the html page
        error = 'Invalid login or email'
        return render_template('login.html', error=error)

#Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
    #grabs information from the forms
    email = request.form['email']
    password = request.form['password']
    fname = request.form['fname']
    lname = request.form['lname']

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM person WHERE email = %s'
    cursor.execute(query, (email))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    error = None
    if(data):
        #If the previous query returns data, then user exists
        error = "This user already exists"
        return render_template('register.html', error=error)
    else:
        ins = 'INSERT INTO person VALUES(%s, %s, %s, %s)'
        cursor.execute(ins, (email, password, fname, lname))
        conn.commit()
        cursor.close()
        return render_template('index.html')

#home page once user logs in
@app.route('/home')
def home():
    user = session['email']
    cursor = conn.cursor();
    query = 'SELECT fg_name, description FROM friendgroup WHERE owner_email = %s'
    cursor.execute(query, (user))
    fg = cursor.fetchall()

    #get visible posts
    query = 'SELECT item_id, email_post, post_time, file_path, item_name' \
            ' FROM contentitem WHERE is_pub = TRUE OR item_id IN ' \
            '(SELECT item_id FROM share NATURAL JOIN belong WHERE email = %s) ' \
            'ORDER BY post_time DESC'
    cursor.execute(query, (user))
    posts = cursor.fetchall()

    #get tags
    query = 'SELECT email_tagged, email_tagger, tagtime, item_id FROM tag WHERE item_id in (' \
            'SELECT item_id' \
            ' FROM contentitem WHERE is_pub = TRUE OR item_id IN ' \
            '(SELECT item_id FROM share NATURAL JOIN belong WHERE email = %s))' \
            'ORDER BY tagtime DESC'
    cursor.execute(query, (user))
    tags = cursor.fetchall()

    query = 'SELECT emoji, rate_time, item_id FROM rate WHERE item_id in (' \
            'SELECT item_id' \
            ' FROM contentitem WHERE is_pub = TRUE OR item_id IN ' \
            '(SELECT item_id FROM share NATURAL JOIN belong WHERE email = %s))' \
            'ORDER BY rate_time DESC'
    cursor.execute(query, (user))
    ratings = cursor.fetchall()

    query = 'SELECT item_id FROM tag WHERE email_tagged=%s AND status = \'Pending\''
    cursor.execute(query, (user))
    proptags = cursor.fetchall()

    cursor.close()
    return render_template('home.html', email=user, fg=fg, posts=posts, tags=tags, ratings=ratings, proptags = proptags)

#when users want more info about the post
@app.route('/more_info', methods=['GET', 'POST'])
def more_info():

    contentid = request.form['contentid']
    approved = "Approved"
    cursor = conn.cursor();
    #select approved tags
    query = 'SELECT fname, lname FROM tag JOIN person on email_tagged = email WHERE item_id = %s AND ' \
            'status = \'Approved\''
    cursor.execute(query, (contentid))
    tags = cursor.fetchall()
    #show ratings
    query = 'SELECT emoji, rate_time, item_id FROM rate WHERE item_id = %s'
    cursor.execute(query, (contentid))
    ratings = cursor.fetchall()

    cursor.close()
    return render_template('more_info.html', ratings=ratings, tags=tags)

#to rate a post
@app.route('/rate', methods=['GET', 'POST'])
def rate():
    email = session['email']
    emoji = request.form['emoji']
    contentid = request.form['contentid']

    cursor = conn.cursor()

    check_rate = ('SELECT * FROM rate WHERE email = %s '
                             'AND item_id = %s', (email, contentid))
    if (check_rate):
        error = "You already rated this content."
        cursor.close()
        return render_template('tag_error.html', error=error)


    query = 'INSERT INTO rate(email, item_id, rate_time, emoji) ' \
            'VALUES(%s, %s, Now(), %s)'
    cursor.execute(query, (email, contentid, emoji))
    conn.commit()
    cursor.close()
    return redirect(url_for('home'))

#to tag someone
@app.route('/tag', methods=['GET', 'POST'])
def tag():
    tagger = session['email']
    taggee = request.form['taggee']
    contentid = request.form['contentid']

    cursor = conn.cursor()

    check_group = cursor.execute('SELECT email FROM belong WHERE email = %s AND fg_name IN ' \
                                 '(SELECT fg_name from share WHERE item_id = %s)', (taggee, contentid))
    check_pub = cursor.execute('SELECT * FROM contentitem WHERE is_pub = 1 and item_id = %s', (contentid))

    #check if the user is part of the friend group or if the post is public
    if (not check_group and not check_pub):
        error = "This user is not allowed to view this content or does not exist."
        cursor.close()
        return render_template('tag_error.html', error=error)

    already = cursor.execute('SELECT * FROM tag WHERE email_tagged = %s '
                             'AND email_tagger = %s AND item_id = %s', (taggee, tagger, contentid))
    #check if user was already tagged
    if (already):
        error = "You already tagged this user on this content."
        cursor.close()
        return render_template('tag_error.html', error=error)

    # if the user is tagging oneself
    if taggee == tagger:
        status = "Approved"

    # if the user tagged someone (valid).
    else:
        status = "Pending"
    #insert into database
    query = 'INSERT INTO tag(item_id, email_tagger, email_tagged, status, tagtime) ' \
            'VALUES(%s, %s, %s, %s, Now())'
    cursor.execute(query, (contentid, tagger, taggee, status))
    conn.commit()
    cursor.close()
    return redirect(url_for('home'))

#to accept tags from others
@app.route('/accepttag', methods=['GET','POST'])
def accepttags():
	email = session['email']
	cursor = conn.cursor();
	contentID = request.form['contentid']
	query = 'UPDATE tag SET status = \'Approved\' WHERE item_id = %s AND email_tagged = %s'
	cursor.execute(query, (contentID, email))
	conn.commit()
	cursor.close();
	return redirect(url_for('home'))

#to reject tags from others
@app.route('/rejecttag', methods=['GET','POST'])
def rejecttags():
	email = session['email']
	cursor = conn.cursor();
	contentID = request.form['contentid']
	query = 'DELETE FROM tag WHERE item_id = %s AND email_tagged = %s'
	cursor.execute(query, (contentID, email))
	conn.commit()
	cursor.close();
	return redirect(url_for('home'))

#to post
@app.route('/post', methods=['GET', 'POST'])
def post():
    email = session['email']
    cursor = conn.cursor();
    content_name = request.form['item_name']
    file_path = request.form['file_path']
    public = 0
    #if the post is public just add it right away to contentitem
    if request.form.get('public'):
        public = 1
        query = 'INSERT INTO contentitem (email_post, file_path, item_name, is_pub, post_time) ' \
                'VALUES(%s, %s, %s, %s, Now())'
        cursor.execute(query, (email, file_path, content_name, public))
    #if not, get the friend group, and insert data in contentitem and share
    else:
        query = 'INSERT INTO contentitem (email_post, file_path, item_name, is_pub, post_time) ' \
                'VALUES(%s, %s, %s, %s, Now());'
        cursor.execute(query, (email, file_path, content_name, public))
        fg = request.form['friendg']
        query = 'INSERT INTO share (owner_email, fg_name, item_id) ' \
                'VALUE (%s, %s, (SELECT item_id FROM contentitem WHERE post_time = ' \
                '(SELECT MAX(post_time) FROM contentitem)))'
        cursor.execute(query, (email, fg))



    conn.commit()
    cursor.close()
    return redirect(url_for('home'))

#for creating a friend group
@app.route('/createfg', methods=['GET', 'POST'])
def createfg():
    email = session['email']
    cursor = conn.cursor()
    name = request.form['name']
    description = request.form['description']
    query = 'INSERT INTO friendgroup (fg_name, description, owner_email) VALUES (%s, %s, %s)'
    cursor.execute(query, (name, description, email))
    query = 'INSERT INTO belong (email, fg_name, owner_email) VALUES (%s, %s, %s)'
    cursor.execute(query, (email, name, email))
    conn.commit()
    cursor.close()
    return redirect(url_for('home'))

#to add someone to a friend group
@app.route('/addtofg', methods=['GET', 'POST'])
def addtofg():
    email = session['email']
    fg_name = request.form['group']
    fname = request.form['fname']
    lname = request.form['lname']

    cursor = conn.cursor()
    #check if the name exists
    exist = 'SELECT * FROM person WHERE fname = %s AND lname = %s'
    if (not cursor.execute(exist, (fname, lname))):
        error = "This name does not exist."
        cursor.close()
        return render_template('addfg_error.html', error=error)


    query = 'SELECT * FROM belong WHERE email = ' \
            '(SELECT email FROM person WHERE fname = %s AND lname = %s)'
    #if name already exists in friend group, let user check again with email.
    if (cursor.execute(query, (fname, lname))):
        error = "This user either already exists in the group or has the same name " \
                "as one of the members. If you wish to try again, type in the email of the user you " \
                "would like to add."
        cursor.close()
        return render_template('addfg_error.html', error=error, email = email, fg_name = fg_name)
    else:
        query = 'INSERT INTO belong(email, owner_email, fg_name) ' \
                'VALUES ((SELECT email FROM person WHERE fname = %s AND lname = %s) , %s, %s)'
        cursor.execute(query, (fname, lname, email, fg_name))
    conn.commit()
    cursor.close()

    return redirect(url_for('home'))

#if names are already in friend group, check the person's email
@app.route('/check_again', methods=['GET', 'POST'])
def check_again():
    email = session['email']
    user = request.form['being_checked']
    fg_name = request.form['fg_name']
    cursor = conn.cursor()
    #check if email is in friendgroup, and if not return error message
    query = 'SELECT * FROM belong WHERE email = %s '
    if (cursor.execute(query, (user))):
        error = "This user already exists."
        cursor.close()
        return render_template('addfg_error.html', error=error, email=email, fg_name=fg_name)
    query = 'INSERT INTO belong(email, owner_email, fg_name) ' \
            'VALUES (%s , %s, %s)'
    cursor.execute(query, (user, email, fg_name))
    return redirect(url_for('home'))

#remove from friend group
@app.route('/remfromfg', methods=['GET', 'POST'])
def remfromfg():
    email = session['email']
    fg_name = request.form['group']
    fname = request.form['fname']
    lname = request.form['lname']

    cursor = conn.cursor()
    query = 'DELETE FROM belong WHERE email = (SELECT email FROM person ' \
            'WHERE fname = %s AND lname = %s) ' \
            'AND fg_name = %s AND owner_email = %s'
    cursor.execute(query, (fname, lname, fg_name, email))
    conn.commit()
    cursor.close()

    return redirect(url_for('home'))


@app.route('/logout')
def logout():
    session.pop('email')
    return redirect('/')
        
app.secret_key = 'some key that you will never guess'
#Run the app on localhost port 5000
#debug = True -> you don't have to restart flask
#for changes to go through, TURN OFF FOR PRODUCTION
if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug = True)

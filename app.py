# app.py
# Complete Flask app with registration, login, and private notes (CRUD).
# Comments below explain every step for a beginner.

from flask import Flask, render_template, request, redirect, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string
import sqlite3

# -------- App Initialization --------
app = Flask(__name__)
app.secret_key = "myverysecretkey"  # change this in production

# ------- Database Connection Helper ---------
def get_db_connection():
    conn = sqlite3.connect("notes.db")
    conn.row_factory = sqlite3.Row
    return conn    

def send_reset_email(to_email, reset_link):
    sender_email = "vinathik509@gmail.com"        # 🔴 YOUR GMAIL
    sender_password = "hgen gccg bpin seut"       # 🔴 APP PASSWORD
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = "Reset Your Notes App Password"
    body = f"""
Hi,
Click the link below to reset your password:
{reset_link}
This link is valid for 15 minutes.
Thanks,
Notes App Team
"""
    msg.attach(MIMEText(body, 'plain'))
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.send_message(msg)
    server.quit()

# -------- Home (redirect) ----------
@app.route('/')
def home():
    # If logged in -> show notes, else -> show login
    if 'user_id' in session:
        return redirect('/viewall')
    return redirect('/login')

# --------- about ---------
@app.route('/about')
def about():
    return render_template('about.html')

# --------- contact --------
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash("Thank you for contacting us. We'll get back to you.", "success")
        return redirect('/contact')
    return render_template('contact.html')

# -------- Register Route ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        firstname = request.form['firstname'].strip()
        lastname = request.form['lastname'].strip()
        email = request.form['email'].strip()
        username = request.form['username'].strip()
        password = request.form['password']

        # 1. Basic validation
        if not firstname or not lastname or not username or not email or not password:
            flash("Please fill all fields.", "danger")
            return redirect('/register')

        conn = get_db_connection()
        cur = conn.cursor()

        # 2. Check if user already exists (username OR email)
        cur.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))

        if cur.fetchone():
            cur.close()
            conn.close()
            flash("You are already registered. Please login.", "info")
            return redirect('/register')

        # 3. Hash password
        hashed_pw = generate_password_hash(password)

        # 4. Insert new user
        cur.execute(""" INSERT INTO users (firstname, lastname, username, email, password) VALUES (?, ?, ?, ?, ?) """, (firstname, lastname, username, email, hashed_pw))

        conn.commit()
        cur.close()
        conn.close()

        flash("Registration successful! Please login.", "success")
        return redirect('/login')

    # GET request
    return render_template('register.html')

def generate_captcha():
    captcha = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
    session['captcha'] = captcha
    return captcha

# ------ Login Route --------
@app.route('/login', methods=['GET', 'POST'])
def login():

    # 👉 If GET request → generate CAPTCHA
    if request.method == 'GET':
        captcha_text = generate_captcha()
        return render_template('login.html', captcha=captcha_text)

    # 👉 If POST request → validate
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user_captcha = request.form.get('captcha')

        # Basic check
        if not username or not password:
            flash("Please enter username and password.", "danger")
            return redirect('/login')

        # ✅ CAPTCHA validation (IMPORTANT FIX)
        if user_captcha != session.get('captcha'):
            flash("Invalid CAPTCHA. Please try again.", "danger")
            return redirect('/login')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f"Welcome, {user['username']}!", "success")
            return redirect('/viewall')
        else:
            flash("Invalid username or password.", "danger")
            return redirect('/login')

# -------- forgot password -----
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email=?", (email,))
        user = cur.fetchone()

        if not user:
            flash("Email not registered.", "danger")
            return redirect('/forgot-password')

        token = str(uuid.uuid4())
        expiry = datetime.now() + timedelta(minutes=15)

        cur.execute("UPDATE users SET reset_token=?, token_expiry=? WHERE email=?", (token, expiry, email))
        conn.commit()
        cur.close()
        conn.close()

        reset_link = f"http://127.0.0.1:5000/reset-password/{token}"
        send_reset_email(email, reset_link) # (email integration later)

        flash("Password reset link sent to your email.", "success")
        return redirect('/login')

    return render_template('forgot_password.html')

# --------- reset password --------
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_db_connection()
    cur = conn.cursor()

    # 1️⃣ Get user by token (SQLite safe)
    cur.execute(
        "SELECT id, token_expiry FROM users WHERE reset_token=?",
        (token,)
    )
    user = cur.fetchone()

    # 2️⃣ Token valid aa kaadha check
    if not user:
        cur.close()
        conn.close()
        flash("Invalid or expired link.", "danger")
        return redirect('/login')

    # 3️⃣ Expiry check in PYTHON (NOT SQL)
    from datetime import datetime

    token_expiry = datetime.fromisoformat(user["token_expiry"])
    if token_expiry < datetime.now():
        cur.close()
        conn.close()
        flash("Reset link expired.", "danger")
        return redirect('/login')

    # 4️⃣ If password submitted
    if request.method == 'POST':
        new_password = request.form['password']
        hashed_pw = generate_password_hash(new_password)

        cur.execute(
            "UPDATE users SET password=?, reset_token=NULL, token_expiry=NULL WHERE id=?",
            (hashed_pw, user["id"])
        )
        conn.commit()
        cur.close()
        conn.close()

        flash("Password updated successfully. Please login.", "success")
        return redirect('/login')

    cur.close()
    conn.close()
    return render_template('reset_password.html')

# -------- Add Note (CREATE) -----------
@app.route('/addnote', methods=['GET', 'POST'])
def addnote():
    # Ensure user is logged in
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        user_id = session['user_id']

        if not title or not content:
            flash("Title and content cannot be empty.", "danger")
            return redirect('/addnote')

        conn = get_db_connection()
        cur = conn.cursor()
        # Save note with user_id to keep notes private
        cur.execute("INSERT INTO notes (title, content, user_id) VALUES (?, ?, ?)",
                    (title, content, user_id))
        conn.commit()
        cur.close()
        conn.close()

        flash("Note added successfully.", "success")
        return redirect('/viewall')

    # GET -> show add note form
    return render_template('addnote.html')

# -------- View All Notes (READ ALL for logged-in user) -----------
@app.route('/viewall')
def viewall():
    # Ensure user logged in
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    search = request.args.get('q')  # <-- search query from URL

    conn = get_db_connection()
    cur = conn.cursor()

    # If search text exists, filter notes
    if search:
        cur.execute(""" SELECT id, title, content, created_at FROM notes WHERE user_id = ? AND (title LIKE ? OR content LIKE ?) ORDER BY created_at DESC """, (user_id, f"%{search}%", f"%{search}%"))
    else:
        # Fetch all notes (default)
        cur.execute(""" SELECT id, title, content, created_at FROM notes WHERE user_id = ? ORDER BY created_at DESC """, (user_id,))

    notes = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('viewnotes.html', notes=notes)

# ------- View Single Note (READ ONE) - restricted -----------
@app.route('/viewnotes/<int:note_id>')
def viewnotes(note_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    # Select note only if it belongs to current user
    cur.execute("SELECT id, title, content, created_at FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
    note = cur.fetchone()
    cur.close()
    conn.close()

    if not note:
        # Either note doesn't exist or doesn't belong to the user
        flash("You don't have access to this note.", "danger")
        return redirect('/viewall')

    return render_template('singlenote.html', note=note)

# ------- Update Note (UPDATE) - restricted ----------
@app.route('/updatenote/<int:note_id>', methods=['GET', 'POST'])
def updatenote(note_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()

    # Check existence and ownership
    cur.execute("SELECT id, title, content FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
    note = cur.fetchone()

    if not note:
        cur.close()
        conn.close()
        flash("You are not authorized to edit this note.", "danger")
        return redirect('/viewall')

    if request.method == 'POST':
        # Get updated data
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        if not title or not content:
            flash("Title and content cannot be empty.", "danger")
            return redirect(url_for('updatenote', note_id=note_id))

        # Update query guarded by user_id
        cur.execute("UPDATE notes SET title = ?, content = ? WHERE id = ? AND user_id = ?",
                    (title, content, note_id, user_id))
        conn.commit()
        cur.close()
        conn.close()
        flash("Note updated successfully.", "success")
        return redirect('/viewall')

    # If GET -> render update form with existing note data
    cur.close()
    conn.close()
    return render_template('updatenote.html', note=note)

# ------ Delete Note (DELETE) - restrict -----------
@app.route('/deletenote/<int:note_id>', methods=['POST'])
def deletenote(note_id):
    # This route expects a POST request (safer than GET for delete)
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    # Delete only if the note belongs to the current user
    cur.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
    conn.commit()
    cur.close()
    conn.close()
    flash("Note deleted.", "info")
    return redirect('/viewall')

# ------- Logout Route ---------
@app.route('/logout')
def logout():
    # Clear session data
    session.clear()
    flash("You have been logged out.", "info")
    return redirect('/login')

# ------- Run App ---------
if __name__ == '__main__':
    # debug=True for development only
    app.run(debug=True)
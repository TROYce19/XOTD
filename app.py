from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import sqlite3
import json
import re
import random
import os
import smtplib
from email.mime.text import MIMEText
from functools import wraps
from deep_translator import GoogleTranslator
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'xotd_super_secret_key_2026'

# 这样写才是绝对安全的“无默认值”状态！
NETEASE_EMAIL = os.environ.get('NETEASE_EMAIL')
NETEASE_PASSWORD = os.environ.get('NETEASE_PASSWORD')

DB_PATH = '/home/xotd.db' if 'WEBSITE_SITE_NAME' in os.environ else 'xotd.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT UNIQUE")
    except:
        pass 
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            translated_item TEXT,
            definition TEXT NOT NULL,
            translated_definition TEXT,
            example TEXT,
            reference_urls TEXT,
            author TEXT DEFAULT '匿名用户',
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn

def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def format_bilingual(row):
    if not row: return None
    item = dict(row)
    item['urls'] = json.loads(item['reference_urls']) if item.get('reference_urls') else []
    item['date_only'] = item['created_at'].split(' ')[0]
    
    if contains_chinese(item['item_name']):
        item['name_zh'] = item['item_name']
        item['name_en'] = item['translated_item'] or item['item_name']
        item['def_zh'] = item['definition']
        item['def_en'] = item['translated_definition'] or item['definition']
    else:
        item['name_en'] = item['item_name']
        item['name_zh'] = item['translated_item'] or item['item_name']
        item['def_en'] = item['definition']
        item['def_zh'] = item['translated_definition'] or item['definition']
    return item

def translate_text(item_name, definition):
    translated_item = ""
    translated_definition = ""
    try:
        if contains_chinese(item_name):
            translated_item = GoogleTranslator(source='auto', target='en').translate(item_name)
            translated_definition = GoogleTranslator(source='auto', target='en').translate(definition)
        else:
            translated_item = GoogleTranslator(source='auto', target='zh-CN').translate(item_name)
            translated_definition = GoogleTranslator(source='auto', target='zh-CN').translate(definition)
    except Exception as e:
        print(f"Translation API error: {e}")
        translated_item = item_name
        translated_definition = definition
    return translated_item, translated_definition

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# ==== 页面路由 ====
@app.route('/')
def index():
    conn = get_db_connection()
    today_str = datetime.now().strftime('%Y-%m-%d')
    rows = conn.execute("SELECT * FROM items WHERE created_at LIKE ? ORDER BY created_at DESC", (f"{today_str}%",)).fetchall()
    conn.close()
    today_items = [format_bilingual(row) for row in rows]
    return render_template('index.html', items=today_items, today_date=today_str)

@app.route('/explore')
def explore():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM items ORDER BY created_at DESC").fetchall()
    conn.close()
    items = []
    custom_types = set()
    for row in rows:
        item = format_bilingual(row)
        items.append(item)
        if item['item_type'] not in ['word', 'concept']:
            custom_types.add(item['item_type'])
    return render_template('explore.html', items=items, custom_types=list(custom_types))

@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/submit-page')
@login_required
def submit_page():
    return render_template('submit.html', item=None)

@app.route('/edit-page/<int:item_id>')
@login_required
def edit_page(item_id):
    if session.get('username') != 'TROYCE':
        return redirect(url_for('index'))
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    if not row:
        return redirect(url_for('index'))
    return render_template('submit.html', item=format_bilingual(row))


# ==== API 接口路由 ====

@app.route('/api/send-code', methods=['POST'])
def send_code():
    data = request.json
    email = data.get('email', '').strip()
    
    if not email or '@' not in email:
        return jsonify({"error": "Invalid email format"}), 400
        
    conn = get_db_connection()
    existing_user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    if existing_user:
        return jsonify({"error": "Email already registered"}), 409

    code = str(random.randint(100000, 999999))
    session['email_code'] = code
    session['reg_email'] = email

    # 核心修改：使用网易的 SMTP_SSL
    try:
        msg = MIMEText(f"Hello!\n\nYour XOTD verification code is: {code}\n\nWelcome to the community!", 'plain', 'utf-8')
        msg['Subject'] = 'XOTD - Your Verification Code'
        msg['From'] = f"XOTD Community <{NETEASE_EMAIL}>"
        msg['To'] = email

        # 网易邮箱通常使用 465 端口的 SSL 加密
        server = smtplib.SMTP_SSL('smtp.163.com', 465) 
        server.login(NETEASE_EMAIL, NETEASE_PASSWORD)
        server.sendmail(NETEASE_EMAIL, [email], msg.as_string())
        server.quit()
        
        return jsonify({"message": "Code sent successfully"}), 200
    except Exception as e:
        print(f"SMTP Error: {e}")
        return jsonify({"error": "Failed to send email. Check server configuration."}), 500

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    user_code = data.get('code', '').strip()

    correct_code = session.get('email_code')
    reg_email = session.get('reg_email')
    
    if not correct_code or user_code != correct_code or email != reg_email:
        return jsonify({"error": "Invalid or expired verification code"}), 400

    if not username or not password or len(password) < 6:
        return jsonify({"error": "Invalid username or password (min 6 chars)"}), 400

    hashed_pw = generate_password_hash(password)

    try:
        conn = get_db_connection()
        cursor = conn.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)', (username, email, hashed_pw))
        conn.commit()
        session['user_id'] = cursor.lastrowid
        session['username'] = username
        session.pop('email_code', None)
        session.pop('reg_email', None)
        conn.close()
        return jsonify({"message": "Registration successful"}), 201
    except sqlite3.IntegrityError as e:
        if 'email' in str(e).lower():
            return jsonify({"error": "Email already exists"}), 409
        return jsonify({"error": "Username already exists"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        return jsonify({"message": "Login successful"}), 200
    else:
        return jsonify({"error": "Invalid username or password"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/submit', methods=['POST'])
@login_required
def submit():
    data = request.json
    item_type = data.get('type')
    item_name = data.get('item')
    definition = data.get('definition')
    example = data.get('example', '')
    reference_urls = data.get('reference_urls', [])
    is_anonymous = data.get('is_anonymous', False) 
    
    user_id = session['user_id']
    if is_anonymous:
        author = "Anonymous" if request.headers.get('Accept-Language', '').startswith('en') else "匿名用户"
    else:
        author = session['username']

    urls_json = json.dumps(reference_urls)
    translated_item, translated_definition = translate_text(item_name, definition)

    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO items (item_type, item_name, translated_item, definition, translated_definition, example, reference_urls, author, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (item_type, item_name, translated_item, definition, translated_definition, example, urls_json, author, user_id))
        conn.commit()
        conn.close()
        return jsonify({"message": "Success"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/edit/<int:item_id>', methods=['PUT'])
@login_required
def api_edit(item_id):
    if session.get('username') != 'TROYCE':
        return jsonify({"error": "Admin access required"}), 403
    data = request.json
    item_type = data.get('type')
    item_name = data.get('item')
    definition = data.get('definition')
    example = data.get('example', '')
    reference_urls = data.get('reference_urls', [])
    urls_json = json.dumps(reference_urls)
    translated_item, translated_definition = translate_text(item_name, definition)
    try:
        conn = get_db_connection()
        conn.execute('''
            UPDATE items 
            SET item_type=?, item_name=?, translated_item=?, definition=?, translated_definition=?, example=?, reference_urls=?
            WHERE id=?
        ''', (item_type, item_name, translated_item, definition, translated_definition, example, urls_json, item_id))
        conn.commit()
        conn.close()
        return jsonify({"message": "Updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete/<int:item_id>', methods=['DELETE'])
@login_required
def delete_item(item_id):
    if session.get('username') != 'TROYCE':
        return jsonify({"error": "Admin access required"}), 403
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM items WHERE id = ?', (item_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
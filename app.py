from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, abort
from datetime import datetime, timedelta
import sqlite3
import json
import re
import uuid
import random
import os
import time
import threading
import smtplib
from email.mime.text import MIMEText
from functools import wraps
from deep_translator import GoogleTranslator
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件中的环境变量

app = Flask(__name__)

IS_PROD = 'WEBSITE_SITE_NAME' in os.environ
_DEFAULT_SECRET = 'xotd_dev_secret_key_2026'
app.secret_key = os.environ.get('SECRET_KEY', _DEFAULT_SECRET)
if IS_PROD and app.secret_key == _DEFAULT_SECRET:
    # 生产环境务必通过环境变量设置 SECRET_KEY,否则 session 可被伪造
    print("WARNING: SECRET_KEY is using the insecure default in production. Set the SECRET_KEY env var.")

# 这样写才是绝对安全的“无默认值”状态！
NETEASE_EMAIL = os.environ.get('NETEASE_EMAIL')
NETEASE_PASSWORD = os.environ.get('NETEASE_PASSWORD')
# 每日邮件定时接口的保护密钥(未设置则该接口拒绝服务)
CRON_SECRET = os.environ.get('CRON_SECRET')
# 站点对外基础 URL(用于邮件里的链接),默认值可被环境变量覆盖
SITE_URL = os.environ.get('SITE_URL', 'https://xotd.azurewebsites.net')

DB_PATH = '/home/xotd.db' if 'WEBSITE_SITE_NAME' in os.environ else 'xotd.db'

# ==== 附件上传配置 ====
# Azure 上只有 /home 是持久化存储,本地则放在项目目录下的 uploads/
UPLOAD_DIR = '/home/uploads' if 'WEBSITE_SITE_NAME' in os.environ else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_DOC_EXT = {'md', 'txt', 'pdf'}
STORED_NAME_RE = re.compile(r'^[a-f0-9]{32}\.[a-z0-9]{1,8}$')  # uuid.hex + 扩展名
ANON_NAMES = {'Anonymous', '匿名用户'}  # 匿名署名:绝不关联真实用户身份

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 单次请求上限 10 MB

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
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
            tags TEXT,
            author TEXT DEFAULT '匿名用户',
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 旧库无损升级:逐列尝试添加,已存在则忽略(表已在上方创建)
    for ddl in (
        "ALTER TABLE users ADD COLUMN email TEXT",
        "ALTER TABLE users ADD COLUMN avatar TEXT",
        "ALTER TABLE users ADD COLUMN email_subscribed INTEGER DEFAULT 0",
        "ALTER TABLE items ADD COLUMN tags TEXT",
    ):
        try:
            cursor.execute(ddl)
        except sqlite3.OperationalError:
            pass  # 列已存在，忽略

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            user_id INTEGER,
            stored_name TEXT UNIQUE NOT NULL,
            original_name TEXT NOT NULL,
            ext TEXT NOT NULL,
            kind TEXT NOT NULL,
            file_size INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, item_id)
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
    item['tag_list'] = json.loads(item['tags']) if item.get('tags') else []
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

def load_attachments(conn, items):
    """为 items 批量挂载附件,拆出 images / docs 两类"""
    for item in items:
        item['attachments'] = []
        item['images'] = []
        item['docs'] = []
    if not items:
        return
    ids = [item['id'] for item in items]
    placeholders = ','.join('?' * len(ids))
    rows = conn.execute(
        f"SELECT * FROM attachments WHERE item_id IN ({placeholders}) ORDER BY id", ids
    ).fetchall()
    by_item = {}
    for row in rows:
        by_item.setdefault(row['item_id'], []).append(dict(row))
    for item in items:
        atts = by_item.get(item['id'], [])
        item['attachments'] = atts
        item['images'] = [a for a in atts if a['kind'] == 'image']
        item['docs'] = [a for a in atts if a['kind'] == 'doc']

def attach_author_avatars(conn, items):
    """为 items 批量挂上作者头像与主页链接。
    匿名词条(author 在 ANON_NAMES 中)不暴露其 user_id 对应的真实身份。"""
    ids = list({
        item['user_id'] for item in items
        if item.get('user_id') and item.get('author') not in ANON_NAMES
    })
    user_map = {}
    if ids:
        placeholders = ','.join('?' * len(ids))
        rows = conn.execute(
            f"SELECT id, username, avatar FROM users WHERE id IN ({placeholders})", ids
        ).fetchall()
        user_map = {r['id']: r for r in rows}
    for item in items:
        item['author_avatar'] = None
        item['author_link'] = None
        if item.get('author') in ANON_NAMES:
            continue
        u = user_map.get(item.get('user_id'))
        # 仅当存储的署名与该用户当前用户名一致时才链接,避免改名/历史数据错配
        if u and u['username'] == item.get('author'):
            item['author_avatar'] = u['avatar']
            item['author_link'] = u['username']

def attach_likes(conn, items):
    """批量挂上点赞数与当前用户是否已赞。"""
    for item in items:
        item['like_count'] = 0
        item['liked_by_me'] = False
    if not items:
        return
    ids = [item['id'] for item in items]
    ph = ','.join('?' * len(ids))
    counts = conn.execute(
        f"SELECT item_id, COUNT(*) c FROM likes WHERE item_id IN ({ph}) GROUP BY item_id", ids
    ).fetchall()
    cmap = {r['item_id']: r['c'] for r in counts}
    mine = set()
    uid = session.get('user_id')
    if uid:
        rows = conn.execute(
            f"SELECT item_id FROM likes WHERE user_id = ? AND item_id IN ({ph})", [uid, *ids]
        ).fetchall()
        mine = {r['item_id'] for r in rows}
    for item in items:
        item['like_count'] = cmap.get(item['id'], 0)
        item['liked_by_me'] = item['id'] in mine

def query_items(conn, q='', type_='all', tag='', date='', page=1, per_page=12):
    """统一的条目查询(搜索 + 筛选 + 分页),供 /explore 与 /api/items 复用。
    返回 (enriched_items, has_more)。"""
    where, params = [], []
    if type_ and type_ != 'all':
        if type_ == 'only-others':
            where.append("item_type NOT IN ('word','concept')")
        else:
            where.append("item_type = ?")
            params.append(type_)
    if tag:
        where.append("tags LIKE ?")
        params.append(f'%"{tag}"%')
    if date:
        where.append("created_at LIKE ?")
        params.append(f"{date}%")
    if q:
        like = f"%{q}%"
        where.append("(item_name LIKE ? OR definition LIKE ? OR translated_item LIKE ? "
                      "OR translated_definition LIKE ? OR author LIKE ? OR tags LIKE ?)")
        params.extend([like] * 6)
    where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
    offset = (max(page, 1) - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM items{where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [*params, per_page + 1, offset]
    ).fetchall()
    has_more = len(rows) > per_page
    rows = rows[:per_page]
    items = [format_bilingual(r) for r in rows]
    load_attachments(conn, items)
    attach_author_avatars(conn, items)
    attach_likes(conn, items)
    return items, has_more

def format_file_size(num):
    if num is None:
        return ''
    num = float(num)
    for unit in ('B', 'KB', 'MB'):
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == 'B' else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"

def normalize_tags(raw):
    """把标签输入(逗号字符串或列表)清洗成去重、限长的列表(最多 8 个,每个 ≤30 字)。"""
    if isinstance(raw, str):
        parts = re.split(r'[,，]', raw)
    elif isinstance(raw, list):
        parts = raw
    else:
        parts = []
    out = []
    for p in parts:
        t = str(p).strip()[:30]
        if t and t not in out:
            out.append(t)
        if len(out) >= 8:
            break
    return out

def contribution_streak(conn, user_id):
    """当前连续贡献天数:从今天(或昨天)往前数,有词条产出的连续自然日数量。"""
    rows = conn.execute(
        "SELECT DISTINCT substr(created_at, 1, 10) d FROM items WHERE user_id = ?", (user_id,)
    ).fetchall()
    dset = {r['d'] for r in rows if r['d']}
    if not dset:
        return 0
    today = datetime.now().date()
    start = today
    if today.isoformat() not in dset:
        start = today - timedelta(days=1)
        if start.isoformat() not in dset:
            return 0  # 今天和昨天都没贡献,连续中断
    streak = 0
    cur = start
    while cur.isoformat() in dset:
        streak += 1
        cur = cur - timedelta(days=1)
    return streak

def user_can_modify(conn, item_id):
    """返回 (item_row, 是否有权修改)。管理员 TROYCE 或条目作者本人可改。"""
    row = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    if not row:
        return None, False
    is_admin = session.get('username') == 'TROYCE'
    is_owner = row['user_id'] is not None and row['user_id'] == session.get('user_id')
    return row, (is_admin or is_owner)

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

def _translate_and_store(item_id, item_name, definition):
    """后台线程:翻译完成后写回该条目。译文暂缺时前端会回退显示原文。"""
    t_item, t_def = translate_text(item_name, definition)
    try:
        conn = get_db_connection()
        conn.execute(
            'UPDATE items SET translated_item=?, translated_definition=? WHERE id=?',
            (t_item, t_def, item_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Async translate store error: {e}")

def translate_async(item_id, item_name, definition):
    threading.Thread(
        target=_translate_and_store, args=(item_id, item_name, definition), daemon=True
    ).start()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_current_user():
    """把当前登录用户的头像注入所有模板(nav 用)。
    session 里有则走快路径,否则懒加载一次并缓存,兼容头像功能上线前的旧会话。"""
    avatar = None
    if session.get('user_id'):
        if 'avatar' in session:
            avatar = session['avatar']
        else:
            conn = get_db_connection()
            row = conn.execute('SELECT avatar FROM users WHERE id = ?', (session['user_id'],)).fetchone()
            conn.close()
            avatar = row['avatar'] if row else None
            session['avatar'] = avatar
    return {'current_avatar': avatar}

# ==== 页面路由 ====
@app.route('/')
def index():
    conn = get_db_connection()
    today_str = datetime.now().strftime('%Y-%m-%d')
    rows = conn.execute("SELECT * FROM items WHERE created_at LIKE ? ORDER BY created_at DESC", (f"{today_str}%",)).fetchall()
    today_items = [format_bilingual(row) for row in rows]
    load_attachments(conn, today_items)
    attach_author_avatars(conn, today_items)
    attach_likes(conn, today_items)
    conn.close()
    return render_template('index.html', items=today_items, today_date=today_str)

PER_PAGE = 12

@app.route('/explore')
def explore():
    q = request.args.get('q', '').strip()
    type_ = request.args.get('type', 'all')
    tag = request.args.get('tag', '').strip()
    date = request.args.get('date', '').strip()
    conn = get_db_connection()
    items, has_more = query_items(conn, q=q, type_=type_, tag=tag, date=date, page=1, per_page=PER_PAGE)
    ct_rows = conn.execute(
        "SELECT DISTINCT item_type FROM items WHERE item_type NOT IN ('word','concept')"
    ).fetchall()
    custom_types = [r['item_type'] for r in ct_rows]
    conn.close()
    return render_template('explore.html', items=items, custom_types=custom_types,
                           has_more=has_more, active_q=q, active_type=type_,
                           active_tag=tag, active_date=date)

@app.route('/api/items')
def api_items():
    q = request.args.get('q', '').strip()
    type_ = request.args.get('type', 'all')
    tag = request.args.get('tag', '').strip()
    date = request.args.get('date', '').strip()
    try:
        page = max(int(request.args.get('page', 1)), 1)
    except ValueError:
        page = 1
    conn = get_db_connection()
    items, has_more = query_items(conn, q=q, type_=type_, tag=tag, date=date, page=page, per_page=PER_PAGE)
    conn.close()
    html = ''.join(render_template('_card.html', item=it) for it in items)
    return jsonify({"html": html, "has_more": has_more, "page": page})

@app.route('/flashcards')
def flashcards():
    type_ = request.args.get('type', 'all')
    tag = request.args.get('tag', '').strip()
    conn = get_db_connection()
    items, _ = query_items(conn, type_=type_, tag=tag, page=1, per_page=100)
    ct_rows = conn.execute(
        "SELECT DISTINCT item_type FROM items WHERE item_type NOT IN ('word','concept')"
    ).fetchall()
    custom_types = [r['item_type'] for r in ct_rows]
    conn.close()
    # 只传卡片正反面需要的字段给前端
    cards = [{
        'name_en': it['name_en'], 'name_zh': it['name_zh'],
        'def_en': it['def_en'], 'def_zh': it['def_zh'],
        'type': it['item_type'], 'id': it['id']
    } for it in items]
    return render_template('flashcards.html', cards=cards, custom_types=custom_types,
                           active_type=type_, active_tag=tag)

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
    conn = get_db_connection()
    row, allowed = user_can_modify(conn, item_id)
    if not row or not allowed:
        conn.close()
        return redirect(url_for('index'))
    item = format_bilingual(row)
    load_attachments(conn, [item])
    conn.close()
    return render_template('submit.html', item=item)

@app.route('/user/<username>')
def user_profile(username):
    conn = get_db_connection()
    user = conn.execute(
        'SELECT id, username, avatar, created_at FROM users WHERE username = ?', (username,)
    ).fetchone()
    if not user:
        conn.close()
        return render_template('user.html', profile=None, items=[]), 404
    # 只展示该用户实名发布的词条(匿名词条不计入公开主页)
    rows = conn.execute(
        "SELECT * FROM items WHERE user_id = ? AND author = ? ORDER BY created_at DESC",
        (user['id'], username)
    ).fetchall()
    items = [format_bilingual(r) for r in rows]
    load_attachments(conn, items)
    attach_author_avatars(conn, items)
    attach_likes(conn, items)
    streak = contribution_streak(conn, user['id'])
    conn.close()
    profile = dict(user)
    profile['join_date'] = (user['created_at'] or '').split(' ')[0]
    profile['item_count'] = len(items)
    profile['streak'] = streak
    profile['is_self'] = (session.get('user_id') == user['id'])
    return render_template('user.html', profile=profile, items=items)

@app.route('/settings')
@login_required
def settings_page():
    conn = get_db_connection()
    row = conn.execute(
        'SELECT avatar, email, email_subscribed FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()
    conn.close()
    return render_template(
        'settings.html',
        avatar=row['avatar'] if row else None,
        has_email=bool(row and row['email']),
        subscribed=bool(row and row['email_subscribed'])
    )


# ==== API 接口路由 ====

@app.route('/api/send-code', methods=['POST'])
def send_code():
    if not NETEASE_EMAIL or not NETEASE_PASSWORD:
        return jsonify({"error": "Email service not configured. Please contact the administrator."}), 503

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
        session['avatar'] = None
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
        session['avatar'] = user['avatar'] if 'avatar' in user.keys() else None
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
    
    if not item_name or not definition:
        return jsonify({"error": "Item name and definition are required"}), 400

    # 简单频率限制:同一会话两次提交至少间隔 5 秒
    now = time.time()
    if now - session.get('last_submit_ts', 0) < 5:
        return jsonify({"error": "You're submitting too fast. Please wait a moment."}), 429

    user_id = session['user_id']
    if is_anonymous:
        author = "Anonymous" if request.headers.get('Accept-Language', '').startswith('en') else "匿名用户"
    else:
        author = session['username']

    urls_json = json.dumps(reference_urls)
    tags_json = json.dumps(normalize_tags(data.get('tags')))

    try:
        conn = get_db_connection()
        # 译文先留空,提交后由后台线程补写(避免同步调用翻译 API 阻塞请求)
        cursor = conn.execute('''
            INSERT INTO items (item_type, item_name, translated_item, definition, translated_definition, example, reference_urls, tags, author, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (item_type, item_name, None, definition, None, example, urls_json, tags_json, author, user_id))
        item_id = cursor.lastrowid
        # 把本次上传的待挂载附件绑定到新条目(只能绑自己的、尚未挂载的)
        att_ids = [a for a in (data.get('attachment_ids') or []) if isinstance(a, int)]
        if att_ids:
            placeholders = ','.join('?' * len(att_ids))
            conn.execute(
                f"UPDATE attachments SET item_id = ? WHERE id IN ({placeholders}) AND user_id = ? AND item_id IS NULL",
                [item_id, *att_ids, user_id]
            )
        conn.commit()
        conn.close()
        session['last_submit_ts'] = now
        translate_async(item_id, item_name, definition)
        return jsonify({"message": "Success"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/edit/<int:item_id>', methods=['PUT'])
@login_required
def api_edit(item_id):
    data = request.json
    item_type = data.get('type')
    item_name = data.get('item')
    definition = data.get('definition')
    example = data.get('example', '')
    reference_urls = data.get('reference_urls', [])
    urls_json = json.dumps(reference_urls)
    tags_json = json.dumps(normalize_tags(data.get('tags')))
    try:
        conn = get_db_connection()
        _, allowed = user_can_modify(conn, item_id)
        if not allowed:
            conn.close()
            return jsonify({"error": "Permission denied"}), 403
        # 译文清空,交由后台线程按新内容重新翻译
        conn.execute('''
            UPDATE items
            SET item_type=?, item_name=?, translated_item=?, definition=?, translated_definition=?, example=?, reference_urls=?, tags=?
            WHERE id=?
        ''', (item_type, item_name, None, definition, None, example, urls_json, tags_json, item_id))
        # 编辑时新上传的附件同样挂载到该条目
        att_ids = [a for a in (data.get('attachment_ids') or []) if isinstance(a, int)]
        if att_ids:
            placeholders = ','.join('?' * len(att_ids))
            conn.execute(
                f"UPDATE attachments SET item_id = ? WHERE id IN ({placeholders}) AND user_id = ? AND item_id IS NULL",
                [item_id, *att_ids, session['user_id']]
            )
        conn.commit()
        conn.close()
        translate_async(item_id, item_name, definition)
        return jsonify({"message": "Updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete/<int:item_id>', methods=['DELETE'])
@login_required
def delete_item(item_id):
    try:
        conn = get_db_connection()
        _, allowed = user_can_modify(conn, item_id)
        if not allowed:
            conn.close()
            return jsonify({"error": "Permission denied"}), 403
        # 一并清理该条目的附件(数据库记录 + 磁盘文件)
        rows = conn.execute('SELECT stored_name FROM attachments WHERE item_id = ?', (item_id,)).fetchall()
        for row in rows:
            try:
                os.remove(os.path.join(UPLOAD_DIR, row['stored_name']))
            except OSError:
                pass
        conn.execute('DELETE FROM attachments WHERE item_id = ?', (item_id,))
        conn.execute('DELETE FROM likes WHERE item_id = ?', (item_id,))
        conn.execute('DELETE FROM items WHERE id = ?', (item_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/like/<int:item_id>', methods=['POST'])
@login_required
def toggle_like(item_id):
    conn = get_db_connection()
    if not conn.execute('SELECT 1 FROM items WHERE id = ?', (item_id,)).fetchone():
        conn.close()
        return jsonify({"error": "Item not found"}), 404
    uid = session['user_id']
    existing = conn.execute(
        'SELECT id FROM likes WHERE user_id = ? AND item_id = ?', (uid, item_id)
    ).fetchone()
    if existing:
        conn.execute('DELETE FROM likes WHERE id = ?', (existing['id'],))
        liked = False
    else:
        conn.execute('INSERT INTO likes (user_id, item_id) VALUES (?, ?)', (uid, item_id))
        liked = True
    conn.commit()
    count = conn.execute('SELECT COUNT(*) c FROM likes WHERE item_id = ?', (item_id,)).fetchone()['c']
    conn.close()
    return jsonify({"liked": liked, "count": count}), 200

# ==== 附件:上传 / 文件服务 / 在线查看 ====

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({"error": "File too large (max 10 MB)"}), 413

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({"error": "No file provided"}), 400

    original_name = file.filename
    ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''
    if ext in ALLOWED_IMAGE_EXT:
        kind = 'image'
    elif ext in ALLOWED_DOC_EXT:
        kind = 'doc'
    else:
        return jsonify({"error": f"File type .{ext or '?'} is not allowed"}), 400

    # 用 uuid 重命名存储,原始文件名只存数据库,杜绝路径注入
    stored_name = uuid.uuid4().hex + '.' + ext
    save_path = os.path.join(UPLOAD_DIR, stored_name)
    file.save(save_path)
    file_size = os.path.getsize(save_path)

    conn = get_db_connection()
    cursor = conn.execute('''
        INSERT INTO attachments (user_id, stored_name, original_name, ext, kind, file_size)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (session['user_id'], stored_name, original_name, ext, kind, file_size))
    conn.commit()
    att_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "id": att_id,
        "url": f"/files/{stored_name}",
        "view_url": f"/view/{att_id}",
        "name": original_name,
        "kind": kind
    }), 201

@app.route('/files/<stored_name>')
def serve_file(stored_name):
    if not STORED_NAME_RE.match(stored_name):
        abort(404)
    ext = stored_name.rsplit('.', 1)[-1]
    # md/txt 强制纯文本输出,供查看页 fetch,且绝不会被当作 HTML 解析(Flask 会自动补 charset)
    mimetype = 'text/plain' if ext in ('md', 'txt') else None
    response = send_from_directory(UPLOAD_DIR, stored_name, mimetype=mimetype)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@app.route('/view/<int:attachment_id>')
def view_attachment(attachment_id):
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM attachments WHERE id = ?', (attachment_id,)).fetchone()
    conn.close()
    if not row:
        return redirect(url_for('index'))
    att = dict(row)
    att['url'] = f"/files/{att['stored_name']}"
    att['size_label'] = format_file_size(att['file_size'])
    att['date_only'] = (att['created_at'] or '').split(' ')[0]
    return render_template('viewer.html', att=att)

@app.route('/api/attachment/<int:att_id>', methods=['DELETE'])
@login_required
def delete_attachment(att_id):
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM attachments WHERE id = ?', (att_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    # 管理员可删任意附件;普通用户只能删自己尚未挂载到条目的附件
    is_admin = session.get('username') == 'TROYCE'
    is_owner_pending = (row['user_id'] == session['user_id'] and row['item_id'] is None)
    if not (is_admin or is_owner_pending):
        conn.close()
        return jsonify({"error": "Permission denied"}), 403
    try:
        os.remove(os.path.join(UPLOAD_DIR, row['stored_name']))
    except OSError:
        pass
    conn.execute('DELETE FROM attachments WHERE id = ?', (att_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"}), 200

# ==== 用户头像 ====

def _remove_upload(stored_name):
    """安全删除上传目录下的文件(校验文件名格式)"""
    if stored_name and STORED_NAME_RE.match(stored_name):
        try:
            os.remove(os.path.join(UPLOAD_DIR, stored_name))
        except OSError:
            pass

@app.route('/api/avatar', methods=['POST'])
@login_required
def api_set_avatar():
    file = request.files.get('avatar')
    if not file or not file.filename:
        return jsonify({"error": "No file provided"}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_IMAGE_EXT:
        return jsonify({"error": "Avatar must be an image (png/jpg/jpeg/gif/webp)"}), 400

    stored_name = uuid.uuid4().hex + '.' + ext
    file.save(os.path.join(UPLOAD_DIR, stored_name))

    conn = get_db_connection()
    old = conn.execute('SELECT avatar FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.execute('UPDATE users SET avatar = ? WHERE id = ?', (stored_name, session['user_id']))
    conn.commit()
    conn.close()

    if old and old['avatar'] and old['avatar'] != stored_name:
        _remove_upload(old['avatar'])  # 清理旧头像文件
    session['avatar'] = stored_name

    return jsonify({"avatar_url": f"/files/{stored_name}"}), 200

@app.route('/api/avatar', methods=['DELETE'])
@login_required
def api_remove_avatar():
    conn = get_db_connection()
    old = conn.execute('SELECT avatar FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.execute('UPDATE users SET avatar = NULL WHERE id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    if old and old['avatar']:
        _remove_upload(old['avatar'])
    session['avatar'] = None
    return jsonify({"message": "Avatar removed"}), 200

# ==== 每日邮件订阅 ====

def send_email(to_addr, subject, body):
    """通过网易 SMTP 发送一封纯文本邮件。返回 True/False。"""
    if not NETEASE_EMAIL or not NETEASE_PASSWORD:
        return False
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = f"XOTD Community <{NETEASE_EMAIL}>"
        msg['To'] = to_addr
        server = smtplib.SMTP_SSL('smtp.163.com', 465)
        server.login(NETEASE_EMAIL, NETEASE_PASSWORD)
        server.sendmail(NETEASE_EMAIL, [to_addr], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"send_email error to {to_addr}: {e}")
        return False

@app.route('/api/subscription', methods=['POST'])
@login_required
def api_subscription():
    subscribe = bool((request.json or {}).get('subscribe'))
    conn = get_db_connection()
    row = conn.execute('SELECT email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    if subscribe and not (row and row['email']):
        conn.close()
        return jsonify({"error": "No email on file for this account"}), 400
    conn.execute('UPDATE users SET email_subscribed = ? WHERE id = ?',
                 (1 if subscribe else 0, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({"subscribed": subscribe}), 200

def build_digest_body(items):
    lines = ["今天的 XOTD 知识精选 / Today's XOTD highlights", ""]
    for it in items:
        name = it['item_name']
        translated = it.get('translated_item')
        title = f"{name}" + (f"  ({translated})" if translated and translated != name else "")
        lines.append(f"• {title}  [{it['item_type']}]")
        definition = (it.get('definition') or '').strip().replace('\n', ' ')
        if len(definition) > 200:
            definition = definition[:200] + '…'
        lines.append(f"  {definition}")
        lines.append("")
    lines.append(f"查看全部 / See more: {SITE_URL}/")
    lines.append("")
    lines.append(f"不想再收到?到 {SITE_URL}/settings 取消订阅。")
    return "\n".join(lines)

def send_daily_digest():
    """给所有已订阅且有邮箱的用户发送今天的词条精选。返回发送成功数。"""
    conn = get_db_connection()
    today_str = datetime.now().strftime('%Y-%m-%d')
    rows = conn.execute(
        "SELECT * FROM items WHERE created_at LIKE ? ORDER BY created_at DESC", (f"{today_str}%",)
    ).fetchall()
    items = [dict(r) for r in rows]
    subscribers = conn.execute(
        "SELECT email FROM users WHERE email_subscribed = 1 AND email IS NOT NULL AND email != ''"
    ).fetchall()
    conn.close()
    if not items or not subscribers:
        return 0
    body = build_digest_body(items)
    subject = f"XOTD · {today_str} · {len(items)} 条新知识"
    sent = 0
    for sub in subscribers:
        if send_email(sub['email'], subject, body):
            sent += 1
    return sent

@app.route('/cron/daily-digest')
def cron_daily_digest():
    # 受 CRON_SECRET 保护:仅供定时任务调用
    if not CRON_SECRET or request.args.get('key') != CRON_SECRET:
        abort(403)
    sent = send_daily_digest()
    return jsonify({"sent": sent}), 200

if __name__ == '__main__':
    # 本地默认开启 debug;设 FLASK_DEBUG=0 可关闭。生产用 gunicorn 不走这里。
    debug = os.environ.get('FLASK_DEBUG', '1') != '0'
    app.run(debug=debug, port=5000)
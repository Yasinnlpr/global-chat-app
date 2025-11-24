import os
import base64
import uuid
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from werkzeug.utils import secure_filename

# ----------------------------
# تنظیمات پایه
# ----------------------------
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_fallback_secret_key')

UPLOAD_DIR = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_AUDIO_EXT = {'wav', 'mp3', 'ogg', 'webm'}

socketio = SocketIO(app, cors_allowed_origins="*")

# ----------------------------
# داده‌های درون‌حافظه
# ----------------------------
rooms = {}
users_in_room = {}

# حساب‌های اولیه
accounts = {
    "yasin": {"password": "yasin.7734", "display_name": "یاسین"},
    "leila": {"password": "1365", "display_name": "لیلا"},
    "zeynab": {"password": "1362", "display_name": "زینب"},
    "tasnim": {"password": "1388", "display_name": "تسنیم"},
}

# ادمین برای حالت توسعه‌دهنده
ADMIN_USER = os.environ.get('ADMIN_USER', 'devadmin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'devpass')
DEV_MODE_USERS = set()

GLOBAL_ROOM = 'global_chat_room'
rooms.setdefault(GLOBAL_ROOM, {'users': [], 'messages': []})

# ----------------------------
# مسیرها
# ----------------------------
@app.route('/', methods=['GET'])
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    data = request.form
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return render_template('login.html', error="نام کاربری و رمز عبور را وارد کنید")

    # حالت توسعه‌دهنده
    if username == ADMIN_USER and password == ADMIN_PASS:
        session['username'] = username
        DEV_MODE_USERS.add(username)
        return redirect(url_for('index'))

    # حساب معمولی
    acct = accounts.get(username)
    if acct and acct.get('password') == password:
        session['username'] = username
        return redirect(url_for('index'))

    return render_template('login.html', error="ورود ناموفق بود. حساب وجود ندارد یا رمز اشتباه است.")

@app.route('/logout', methods=['POST'])
def logout():
    username = session.pop('username', None)
    if username in DEV_MODE_USERS:
        DEV_MODE_USERS.discard(username)
    return redirect(url_for('login'))

@app.route('/dev/create_user', methods=['POST'])
def dev_create_user():
    if 'username' not in session or session['username'] not in DEV_MODE_USERS:
        return jsonify({'ok': False, 'error': 'دسترسی غیرمجاز'}), 403

    data = request.json or {}
    new_user = data.get('username', '').strip()
    new_pass = data.get('password', '').strip()
    display_name = data.get('display_name', '').strip() or new_user

    if not new_user or not new_pass:
        return jsonify({'ok': False, 'error': 'نام کاربری و رمز عبور الزامی است'}), 400
    if new_user in accounts:
        return jsonify({'ok': False, 'error': 'این نام کاربری از قبل وجود دارد'}), 400

    accounts[new_user] = {'password': new_pass, 'display_name': display_name}
    return jsonify({'ok': True})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return jsonify({'ok': False, 'error': 'ابتدا وارد شوید'}), 403

    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'فایلی ارسال نشده'}), 400

    f = request.files['file']
    filename = secure_filename(f.filename)
    if not filename:
        return jsonify({'ok': False, 'error': 'نام فایل نامعتبر'}), 400

    ext = filename.split('.')[-1].lower()
    if ext not in ALLOWED_IMAGE_EXT.union(ALLOWED_AUDIO_EXT):
        return jsonify({'ok': False, 'error': 'پسوند فایل پشتیبانی نمی‌شود'}), 400

    unique = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_DIR, unique)
    f.save(save_path)

    file_url = url_for('static', filename=f'uploads/{unique}', _external=True)
    return jsonify({'ok': True, 'url': file_url, 'type': 'image' if ext in ALLOWED_IMAGE_EXT else 'audio'})

# ----------------------------
# رویدادهای Socket.IO
# ----------------------------
@socketio.on('join')
def on_join(data):
    username = data.get('username')
    room = data.get('room', GLOBAL_ROOM)
    if not room or not username:
        return
    join_room(room)
    users_in_room.setdefault(room, [])
    if username not in [u['username'] for u in users_in_room[room]]:
        users_in_room[room].append({'username': username, 'id': request.sid})
    if room not in rooms:
        rooms[room] = {'users': [], 'messages': []}
    if username not in [u['username'] for u in rooms[room]['users']]:
        rooms[room]['users'].append({'username': username, 'sid': request.sid})
    emit('status', {'msg': f'{username} به چت پیوست.'}, room=room)
    emit('user_list', {'users': rooms[room]['users']}, room=room)
    emit('presence', {'username': username, 'state': 'online'}, room=room)

@socketio.on('left')
def on_leave(data=None):
    sid = request.sid
    room = None
    username = None
    for r, user_list in users_in_room.items():
        for user in user_list:
            if user['id'] == sid:
                room = r
                username = user['username']
                break
        if room:
            break
    if room and username:
        users_in_room[room] = [user for user in users_in_room[room] if user['id'] != sid]
        leave_room(room)
        rooms[room]['users'] = [u for u in rooms[room]['users'] if u['sid'] != sid]
        emit('status', {'msg': f'{username} از چت خارج شد.'}, room=room)
        emit('user_list', {'users': rooms[room]['users']}, room=room)
        emit('presence', {'username': username, 'state': 'offline'}, room=room)

@socketio.on('send_message')
def handle_message(data):
    username = data.get('username')
    room = data.get('room', GLOBAL_ROOM)
    msg = data.get('msg', '').strip()
    reply_to = data.get('reply_to')
    if not msg:
        return
    message_obj = {
        'username': username,
        'msg': msg,
        'type': 'text',
        'time': datetime.utcnow().isoformat(),
        'reply_to': reply_to
    }
    rooms[room]['messages'].append(message_obj)
    emit('new_message', message_obj, room=room)

@socketio.on('send_media')
def handle_media(data):
    username = data.get('username')
    room = data.get('room', GLOBAL_ROOM)
    media_url = data.get('url')
    media_type = data.get('type')
    if not media_url or media_type not in ('image', 'audio'):
        return
    message_obj = {
        'username': username,
        'msg': media_url,
        'type': media_type,
        'time': datetime.utcnow().isoformat(),
        'reply_to': data.get('reply_to')
    }
    rooms[room]['messages'].append(message_obj)
    emit('new_message', message_obj, room=room)

@socketio.on('typing')
def handle_typing(data):
    room = data.get('room', GLOBAL_ROOM)
    username = data.get('username')
    state = data.get('state')
    emit('activity', {'username': username, 'state': state}, room=room)

@socketio.on('rtc_offer')
def rtc_offer(data):
    room = data.get('room', GLOBAL_ROOM)
    emit('rtc_offer', data, room=room, include_self=False)

@socketio.on('rtc_answer')
def rtc_answer(data):
    room = data.get('room', GLOBAL_ROOM)
    emit('
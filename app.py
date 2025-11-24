from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, send, emit
from os import environ

# --- تنظیمات ---
# ۱. متغیر محیطی SECRET_KEY را می‌خوانیم و در صورت نبود، یک کلید پیش‌فرض قرار می‌دهیم
app = Flask(__name__)
app.config['SECRET_KEY'] = environ.get('SECRET_KEY', 'your_fallback_secret_key')

# ۲. SocketIO را با تنظیمات CORS (برای ارتباط امن با Render) تنظیم می‌کنیم
# cors_allowed_origins="*" اجازه می‌دهد کلاینت از هر آدرسی (از جمله آدرس Render) متصل شود
socketio = SocketIO(app, cors_allowed_origins="*")

users_in_room = {} # یک دیکشنری برای نگهداری کاربران در هر روم
# user_info = {} # یک دیکشنری برای نگهداری اطلاعات کاربر (session ID, username, room)

# --- مسیرهای Flask (HTTP) ---
@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

# --- رویدادهای SocketIO (WebSocket) ---
@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']

    if not room:
        return # اگر روم خالی باشد، کاری نمی‌کنیم

    # ۲. اضافه کردن کاربر به روم در SocketIO
    join_room(room)

    # ۳. نگهداری اطلاعات کاربر در دیکشنری لوکال
    # اگر قبلا کاربرانی در روم نبودند، یک لیست جدید می‌سازیم
    if room not in users_in_room:
        users_in_room[room] = []
    
    # اطمینان از اینکه نام کاربری تکراری نباشد
    if username not in [u['username'] for u in users_in_room[room]]:
        # اطلاعات کاربر را ذخیره می‌کنیم
        users_in_room[room].append({'username': username, 'id': request.sid}) 

    # ۴. ارسال پیام خوش آمدگویی و لیست کاربران به همه (broadcast)
    emit('status', {'msg': f'{username} به چت پیوست.'}, room=room)
    emit('user_list', {'users': users_in_room[room]}, room=room)


@socketio.on('left')
def on_leave(data):
    # ۱. اطلاعات کاربر و روم را از دیکشنری پیدا می‌کنیم
    sid = request.sid
    room = None
    username = None

    # پیدا کردن اطلاعات کاربر بر اساس sid (Session ID)
    for r, user_list in users_in_room.items():
        for user in user_list:
            if user['id'] == sid:
                room = r
                username = user['username']
                break
        if room:
            break

    if room and username:
        # ۲. حذف کاربر از دیکشنری
        users_in_room[room] = [user for user in users_in_room[room] if user['id'] != sid]

        # ۳. حذف کاربر از روم در SocketIO
        leave_room(room)

        # ۴. ارسال پیام خروج و لیست کاربران به‌روز شده
        emit('status', {'msg': f'{username} از چت خارج شد.'}, room=room)
        emit('user_list', {'users': users_in_room[room]}, room=room)


@socketio.on('send_message')
def handle_message(data):
    username = data['username']
    room = data['room']
    msg = data['msg']
    
    if msg:
        # ارسال پیام به تمام کاربران در روم
        emit('new_message', {'username': username, 'msg': msg}, room=room)

# ----------------------------------------------------------------------
# ❌ این بخش برای اجرای لوکال بود و باید در سرور Render کاملاً حذف شود!
# if __name__ == '__main__':
#     socketio.run(app, host='0.0.0.0', port=8080, debug=True)
# ----------------------------------------------------------------------
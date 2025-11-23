from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import os

# --- ۱. تنظیمات Flask و SocketIO ---
app = Flask(__name__)
# SECRET_KEY برای امنیت ضروری است.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_fallback_secret_key') 

# تنظیمات CORS: این خط اجازه اتصال از هر آدرسی را می‌دهد (برای حل مشکلات اتصال محلی و خارجی ضروری است)
socketio = SocketIO(app, cors_allowed_origins="*")

# یک دیکشنری برای نگهداری از نام کاربران و اتاق‌هایشان
users_in_room = {}

# --- ۲. روت‌های وب (HTTP) ---
@app.route('/')
def index():
    """نمایش صفحه چت."""
    return render_template('index.html')

# --- ۳. رویدادهای WebSocket (SocketIO) ---

@socketio.on('join')
def on_join(data):
    """مدیریت ورود کاربر به اتاق چت."""
    username = data.get('username')
    # نام اتاق چت ثابت است، چون فقط یک اتاق داریم
    room = 'main_chat_room' 
    
    if username:
        # کاربر را به اتاق ملحق می‌کند
        join_room(room)
        # ثبت کاربر با استفاده از Session ID
        users_in_room[request.sid] = {'username': username, 'room': room}
        
        # ارسال پیام به همه افراد اتاق (به جز خود شخص)
        emit('status', {'msg': f'👋 {username} به چت ملحق شد.'}, room=room, include_self=False)
        # ارسال پیام خوش آمدگویی به خود شخص
        emit('status', {'msg': f'به اتاق چت خوش آمدید، {username}!'}, room=request.sid)

@socketio.on('text')
def handle_message(data):
    """مدیریت ارسال پیام متنی."""
    msg = data.get('msg')
    
    # اطلاعات کاربر را از دیکشنری بر اساس Session ID فعلی (request.sid) می‌گیریم
    user_info = users_in_room.get(request.sid)
    
    if user_info and msg:
        username = user_info['username']
        room = user_info['room']
        
        # ارسال پیام به همه افراد اتاق
        emit('message', {'username': username, 'msg': msg}, room=room)

@socketio.on('disconnect')
def on_disconnect():
    """مدیریت قطع اتصال کاربر."""
    user_info = users_in_room.pop(request.sid, None)
    
    if user_info:
        username = user_info['username']
        room = user_info['room']
        
        # ارسال پیام به همه افراد اتاق
        emit('status', {'msg': f'🚪 {username} از چت خارج شد.'}, room=room)

# --- ۴. اجرای سرور (تغییر حیاتی برای حل مشکل فایروال کروم‌بوک) ---
if __name__ == '__main__':
    # host='0.0.0.0' باعث می‌شود سرور به تمام آدرس‌های شبکه گوش دهد، 
    # که برای دور زدن فایروال داخلی لینوکس کروم‌بوک ضروری است.
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)
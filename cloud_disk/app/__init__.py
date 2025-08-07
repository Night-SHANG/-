import os
import sys
import time
import webbrowser
import atexit
import signal
import threading
from flask import Flask
from flask_socketio import SocketIO
from .config import Config
from .utils import get_local_ip, find_available_port
from .models import FileWatcher

# ================= Flask应用初始化 =================
app = Flask(__name__, 
            template_folder='../templates',
            static_folder='static')
app.config.from_object(Config)

# SocketIO初始化
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化文件监控器
file_watcher = FileWatcher(Config.UPLOAD_FOLDER, socketio)

# 确保共享目录存在
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

# 导入视图
from . import views

def exit_handler():
    """退出时的清理操作"""
    print("\n正在安全关闭服务...")
    file_watcher.stop()
    print("资源清理完成")
    # 注意：不再清理共享文件夹中的文件
    os._exit(0)

def register_exit_handlers():
    """注册退出处理器"""
    atexit.register(exit_handler)
    signal.signal(signal.SIGTERM, lambda s, f: exit_handler())
    signal.signal(signal.SIGINT, lambda s, f: exit_handler())

def run_server(port):
    """启动服务器主逻辑"""
    local_ip = get_local_ip()
    
    print(f"\n服务器启动信息:")
    print(f"电脑访问: http://127.0.0.1:{port}")
    print(f"手机访问: http://{local_ip}:{port}")
    print(f"共享目录: {os.path.abspath(Config.UPLOAD_FOLDER)}\n")
    
    # 启动文件监控
    file_watcher.start()
    
    # 启动Flask服务器（不自动打开浏览器，由主程序控制）
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
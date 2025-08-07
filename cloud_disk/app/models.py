import os
import time
import threading
from flask import jsonify
from flask_socketio import emit
from .utils import get_file_info

class FileWatcher:
    """文件监控类"""
    
    def __init__(self, base_path, socketio):
        self.base_path = base_path
        self.socketio = socketio
        self.last_files = []
        self.running = False
        self.thread = None
    
    def start(self):
        """启动文件监控"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._watch_files, daemon=True)
            self.thread.start()
    
    def stop(self):
        """停止文件监控"""
        self.running = False
        if self.thread:
            self.thread.join()
    
    def _watch_files(self):
        """后台监控文件变化"""
        while self.running:
            try:
                current_files = get_file_info(self.base_path)
                if current_files != self.last_files:
                    # 通知所有客户端
                    self.socketio.emit('file_update', {'files': current_files}, namespace='/file')
                    self.last_files = current_files
                time.sleep(1)
            except Exception as e:
                print(f"文件监控出错: {e}")
                time.sleep(5)
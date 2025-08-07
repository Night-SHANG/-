import os
import sys

# 路径转换，用于打包后寻找资源
def resource_path(relative_path):
    """获取资源的绝对路径，无论是开发环境还是打包后。"""
    try:
        # PyInstaller 创建一个临时文件夹，并把路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ================= 配置部分 =================
class Config:
    # 共享文件夹路径（默认为shared目录，但可以在运行时更改）
    DEFAULT_UPLOAD_FOLDER = resource_path('shared')
    UPLOAD_FOLDER = DEFAULT_UPLOAD_FOLDER
    
    # 允许所有文件类型
    ALLOWED_EXTENSIONS = {'*'}
    
    # 默认端口
    DEFAULT_PORT = 5000
    
    # 文件清理间隔(秒)
    CLEANUP_INTERVAL = 3600
    
    # 最大上传文件大小 (100GB)
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024 * 1024
    
    # Flask密钥
    SECRET_KEY = os.urandom(24)
    
    @classmethod
    def set_upload_folder(cls, path):
        """设置新的共享文件夹路径"""
        if os.path.exists(path) and os.path.isdir(path):
            cls.UPLOAD_FOLDER = os.path.abspath(path)
            return True
        return False
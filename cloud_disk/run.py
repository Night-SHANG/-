import os
import sys
import threading
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox, filedialog
import webbrowser
import configparser
import winreg
import time
import atexit
import signal
from pathlib import Path
from PIL import Image
import pystray
import psutil

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app'))

from app import app, socketio, register_exit_handlers
from app.config import Config
from app.utils import get_local_ip, find_available_port

# 路径转换，用于打包后寻找资源
def resource_path(relative_path):
    """获取资源的绝对路径，无论是开发环境还是打包后。"""
    try:
        # PyInstaller 创建一个临时文件夹，并把路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 配置文件路径
CONFIG_FILE = "cloud_disk.ini"
# 单实例锁文件
LOCK_FILE = "cloud_disk.lock"

class CloudDiskApp:
    def __init__(self):
        # 检查是否已经运行
        if not self.check_single_instance():
            root = ttk.Window()
            root.withdraw()
            messagebox.showwarning("警告", "程序已经在运行中！", parent=root)
            root.destroy()
            sys.exit(0)
            
        self.root = ttk.Window(themename="litera")
        self.root.title("局域网云盘控制台")
        self.root.geometry("500x400")
        
        # 读取配置
        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_FILE)
        
        # 初始化变量
        self.port = int(self.get_config('settings', 'port', str(Config.DEFAULT_PORT)))
        self.auto_open_browser = self.get_config('settings', 'auto_open_browser', 'False').lower() == 'true'
        self.shared_folder = self.get_config('settings', 'shared_folder', Config.DEFAULT_UPLOAD_FOLDER)
        
        # 设置共享目录
        Config.set_upload_folder(self.shared_folder)
        
        # 初始化服务状态
        self.server_thread = None
        self.is_running = False
        self.server_instance = None
        self.icon = None  # 托盘图标
        
        # 注册退出处理函数
        self.register_app_exit_handlers()
        
        # 设置窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 初始化UI
        self.setup_ui()
        
        # 初始化托盘图标
        self.setup_tray()
            
        # 自动启动服务
        self.root.after(100, self.start_service)

    def check_single_instance(self):
        """检查是否已经运行了程序实例"""
        current_pid = os.getpid()
        
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, 'r') as f:
                    pid = int(f.read().strip())
                if psutil.pid_exists(pid):
                    process = psutil.Process(pid)
                    if "run.py" in " ".join(process.cmdline()):
                        return False
            except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
                try:
                    os.remove(LOCK_FILE)
                except:
                    pass
        
        with open(LOCK_FILE, 'w') as f:
            f.write(str(current_pid))
        return True

    def get_config(self, section, key, default):
        """获取配置项"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        return self.config.get(section, key, fallback=default)

    def set_config(self, section, key, value):
        """设置配置项"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
        with open(CONFIG_FILE, 'w') as f:
            self.config.write(f)

    def register_app_exit_handlers(self):
        """注册应用退出处理函数"""
        atexit.register(self.cleanup)
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signum, frame):
        """信号处理函数"""
        self.cleanup()
        sys.exit(0)

    def cleanup(self):
        """清理资源"""
        print("\n正在关闭服务...")
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
        print("服务已关闭")

    def on_closing(self):
        """窗口关闭事件处理 - 最小化到托盘"""
        self.root.withdraw()

    def show_window(self):
        """显示主窗口"""
        self.root.deiconify()

    def setup_ui(self):
        """设置主界面"""
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        self.status_frame = ttk.Frame(notebook)
        notebook.add(self.status_frame, text="状态")
        self.setup_status_tab()
        
        self.settings_frame = ttk.Frame(notebook)
        notebook.add(self.settings_frame, text="设置")
        self.setup_settings_tab()
        
        self.about_frame = ttk.Frame(notebook)
        notebook.add(self.about_frame, text="关于")
        self.setup_about_tab()

    def setup_status_tab(self):
        """设置状态标签页"""
        status_frame = ttk.LabelFrame(self.status_frame, text="服务状态", padding=(10, 5))
        status_frame.pack(fill=X, padx=10, pady=10)
        
        self.status_label = ttk.Label(status_frame, text="● 运行中", bootstyle="success")
        self.status_label.pack(side=LEFT, padx=5, pady=5)
        
        address_frame = ttk.Frame(self.status_frame)
        address_frame.pack(fill=X, padx=10, pady=5)
        
        ttk.Label(address_frame, text="局域网地址：").pack(side=LEFT)
        self.address_label = ttk.Label(address_frame, text="http://0.0.0.0:0")
        self.address_label.pack(side=LEFT, padx=5)
        
        button_frame = ttk.Frame(self.status_frame)
        button_frame.pack(fill=X, padx=10, pady=5)
        
        self.copy_btn = ttk.Button(button_frame, text="一键复制网址", command=self.copy_url, bootstyle="outline")
        self.copy_btn.pack(side=LEFT, padx=5)
        
        self.open_btn = ttk.Button(button_frame, text="一键在浏览器打开", command=self.open_browser, bootstyle="outline")
        self.open_btn.pack(side=LEFT, padx=5)
        
        service_btn_frame = ttk.Frame(self.status_frame)
        service_btn_frame.pack(fill=X, padx=10, pady=10)
        
        self.stop_btn = ttk.Button(service_btn_frame, text="停止服务并退出", command=self.stop_and_exit, bootstyle="danger")
        self.stop_btn.pack(side=LEFT, padx=5)
        
        share_frame = ttk.LabelFrame(self.status_frame, text="当前共享", padding=(10, 5))
        share_frame.pack(fill=X, padx=10, pady=10)
        
        self.share_path_label = ttk.Label(share_frame, text=os.path.abspath(Config.UPLOAD_FOLDER))
        self.share_path_label.pack(side=LEFT, padx=5, pady=5)
        
        self.change_share_btn = ttk.Button(share_frame, text="修改共享目录…", command=self.change_shared_folder, bootstyle="info-outline")
        self.change_share_btn.pack(side=RIGHT, padx=5, pady=5)

    def setup_settings_tab(self):
        """设置标签页"""
        port_frame = ttk.Frame(self.settings_frame)
        port_frame.pack(fill=X, padx=10, pady=10)
        
        ttk.Label(port_frame, text="端口：").pack(side=LEFT)
        self.port_var = ttk.StringVar(value=str(self.port))
        port_entry = ttk.Entry(port_frame, textvariable=self.port_var, width=10)
        port_entry.pack(side=LEFT, padx=5)
        
        self.change_port_btn = ttk.Button(port_frame, text="更改", command=self.change_port, bootstyle="secondary")
        self.change_port_btn.pack(side=LEFT, padx=5)
        
        browser_frame = ttk.Frame(self.settings_frame)
        browser_frame.pack(fill=X, padx=10, pady=10)
        
        ttk.Label(browser_frame, text="自动打开浏览器：").pack(side=LEFT)
        self.auto_open_var = ttk.BooleanVar(value=self.auto_open_browser)
        auto_open_check = ttk.Checkbutton(
            browser_frame, 
            variable=self.auto_open_var,
            command=self.toggle_auto_open,
            bootstyle="square-toggle"
        )
        auto_open_check.pack(side=LEFT, padx=5)

    def setup_about_tab(self):
        """设置关于标签页"""
        about_text = """
局域网云盘 v1.0

功能特点：
- 将电脑文件夹映射到局域网
- 支持文件上传、下载
- 响应式网页界面，适配手机和电脑
- 实时文件列表更新

        """
        
        text_widget = ttk.Text(self.about_frame, wrap=WORD, relief=FLAT)
        text_widget.pack(fill=BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(END, about_text)
        text_widget.config(state=DISABLED)
        
        log_btn = ttk.Button(self.about_frame, text="打开日志文件夹", command=self.open_log_folder, bootstyle="link")
        log_btn.pack(pady=10)

    def setup_tray(self):
        """设置系统托盘"""
        try:
            icon_path = resource_path("icon.ico")
            image = Image.open(icon_path) if os.path.exists(icon_path) else Image.new('RGB', (64, 64), color=(73, 109, 137))
            
            menu = pystray.Menu(
                pystray.MenuItem('显示主界面', self.show_window),
                pystray.MenuItem('打开网页', self.open_browser_from_tray),
                pystray.MenuItem('退出程序', self.stop_and_exit)
            )
            
            self.icon = pystray.Icon("局域网云盘", image, menu=menu)
        except Exception as e:
            print(f"创建托盘图标失败: {e}")

    def run_tray(self):
        """运行托盘图标"""
        if self.icon:
            self.icon.run_detached()

    def open_browser_from_tray(self):
        """从托盘打开浏览器"""
        if self.is_running:
            webbrowser.open(f"http://127.0.0.1:{self.port}")
        else:
            messagebox.showwarning("警告", "服务未启动")

    def copy_url(self):
        """复制网址到剪贴板"""
        url = f"http://{get_local_ip()}:{self.port}"
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        messagebox.showinfo("提示", "网址已复制到剪贴板")

    def open_browser(self):
        """在浏览器中打开"""
        if self.is_running:
            webbrowser.open(f"http://127.0.0.1:{self.port}")
        else:
            messagebox.showwarning("警告", "服务未启动")

    def start_service(self):
        """启动服务"""
        # 检查是否设置了共享文件夹
        if not self.shared_folder or not os.path.exists(self.shared_folder):
            messagebox.showwarning("警告", "请先设置共享文件夹路径！")
            self.change_shared_folder()
            return
            
        if not self.is_running:
            try:
                self.port = int(self.port_var.get())
                self.server_thread = threading.Thread(target=self._run_server, daemon=True)
                self.server_thread.start()
                
                time.sleep(1)
                
                self.is_running = True
                self.status_label.config(text="● 运行中", bootstyle="success")
                self.address_label.config(text=f"http://{get_local_ip()}:{self.port}")
                
                if self.auto_open_browser:
                    self.open_browser()
                print("服务已启动")
            except Exception as e:
                messagebox.showerror("错误", f"启动服务失败：{str(e)}")

    def _run_server(self):
        """运行服务器"""
        try:
            from app import run_server
            run_server(self.port)
        except Exception as e:
            print(f"服务器运行错误: {e}")

    def stop_and_exit(self):
        """停止服务并退出"""
        try:
            self.set_config('settings', 'shared_folder', Config.UPLOAD_FOLDER)
            self.cleanup()
            if self.icon:
                self.icon.stop()
        except Exception as e:
            print(f"关闭服务时出错: {e}")
        finally:
            # Schedule the destruction on the main thread to be thread-safe
            self.root.after(0, self.root.destroy)

    def change_shared_folder(self):
        """更改共享文件夹"""
        folder_path = filedialog.askdirectory(title="选择共享文件夹")
        if folder_path and os.path.exists(folder_path) and os.path.isdir(folder_path):
            if Config.set_upload_folder(folder_path):
                self.share_path_label.config(text=os.path.abspath(Config.UPLOAD_FOLDER))
                self.set_config('settings', 'shared_folder', folder_path)
                messagebox.showinfo("成功", f"共享目录已更改为: {Config.UPLOAD_FOLDER}")
            else:
                messagebox.showerror("错误", "无法设置共享目录")
        elif folder_path:
            messagebox.showerror("错误", "选择的路径无效")

    def change_port(self):
        """更改端口"""
        try:
            new_port = int(self.port_var.get())
            if new_port != self.port:
                try:
                    test_port = find_available_port(new_port)
                    if test_port != new_port:
                        messagebox.showwarning("警告", f"端口 {new_port} 已被占用，建议使用 {test_port}")
                        return
                except:
                    messagebox.showerror("错误", f"无法绑定端口 {new_port}")
                    return
                
                self.port = new_port
                self.set_config('settings', 'port', self.port)
                messagebox.showinfo("提示", f"端口已更改为: {self.port}")
                
                if self.is_running:
                    if messagebox.askyesno("提示", "需要重启服务以应用端口更改，是否立即重启？"):
                        self.stop_and_exit()
                        python = sys.executable
                        os.execl(python, python, *sys.argv)
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字")

    def toggle_auto_open(self):
        """切换自动打开浏览器"""
        self.auto_open_browser = self.auto_open_var.get()
        self.set_config('settings', 'auto_open_browser', self.auto_open_browser)

    def open_log_folder(self):
        """打开日志文件夹"""
        os.startfile(os.path.abspath(Config.UPLOAD_FOLDER))

    def run(self):
        """运行应用"""
        if self.icon:
            self.icon.run_detached()
        self.root.mainloop()

def main():
    register_exit_handlers()
    app_instance = CloudDiskApp()
    app_instance.run()

if __name__ == '__main__':
    main()

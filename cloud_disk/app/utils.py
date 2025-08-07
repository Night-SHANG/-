import os
import time
import socket
import psutil

def get_local_ip():
    """获取本机局域网IP"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except:
        return '127.0.0.1'

def find_available_port(start_port):
    """自动寻找可用端口"""
    port = start_port
    while port < start_port + 100:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', port))
                s.close()
                return port
        except OSError:
            port += 1
    raise RuntimeError("找不到可用端口")

def allowed_file(filename):
    """检查文件扩展名是否合法"""
    # 允许所有文件类型
    return True

def get_file_info(base_path, path=''):
    """获取文件列表信息"""
    files = []
    # 确保路径安全
    if path:
        # 规范化路径并确保它在base_path内
        folder_path = os.path.normpath(os.path.join(base_path, path))
        # 检查是否在base_path内
        if not folder_path.startswith(os.path.normpath(base_path)):
            return files
    else:
        folder_path = base_path
    
    if not os.path.exists(folder_path):
        return files
        
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        stat = os.stat(item_path)
        
        # 判断是否为文件夹
        is_dir = os.path.isdir(item_path)
        
        # 计算相对路径
        if path:
            relative_path = os.path.join(path, item)
        else:
            relative_path = item
            
        files.append({
            'name': item,
            'is_dir': is_dir,
            'size': stat.st_size if not is_dir else 0,
            'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
            'path': relative_path
        })
        
    return sorted(files, key=lambda x: (not x['is_dir'], x['name'].lower()))

def safe_file_download(filepath, filename):
    """安全下载文件（解决文件锁定问题）"""
    from flask import send_file
    import os
    
    # 使用 Flask 内置的 send_file 函数，它经过优化，能提供更好的下载性能
    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename
    )

def format_file_size(bytes_size):
    """格式化文件大小"""
    if bytes_size == 0:
        return '0 Bytes'
    size_names = ['Bytes', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while bytes_size >= 1024 and i < len(size_names) - 1:
        bytes_size /= 1024.0
        i += 1
    return f"{bytes_size:.1f} {size_names[i]}"

def read_txt_chunk(file_path, chunk_index=0, chunk_size=100):
    """高效、分块地读取TXT文件，自动检测编码并忽略错误"""
    import itertools

    def read_lines_from_file(f):
        start_line = chunk_index * chunk_size
        # 高效地获取目标块的行
        chunk_lines = list(itertools.islice(f, start_line, start_line + chunk_size))
        
        # 检查是否还有更多行，以决定是否显示“加载更多”
        try:
            next(f)
            has_more = True
        except StopIteration:
            has_more = False
            
        return "".join(chunk_lines), has_more

    try:
        # 尝试用 utf-8-sig (处理BOM) 打开
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            return read_lines_from_file(f)
    except UnicodeDecodeError:
        # 如果失败，回退到 gbk 并忽略错误
        try:
            with open(file_path, 'r', encoding='gbk', errors='ignore') as f:
                return read_lines_from_file(f)
        except Exception as e:
            return f"无法读取文件: {e}", False
    except Exception as e:
        return f"无法读取文件: {e}", False
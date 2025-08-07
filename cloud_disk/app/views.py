from flask import render_template, request, jsonify, send_from_directory
from flask_socketio import emit
import os
from . import app, socketio
from .config import Config
from .utils import get_file_info, safe_file_download, allowed_file, format_file_size, read_txt_chunk

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/files')
@app.route('/files/', defaults={'subpath': ''})
@app.route('/files/<path:subpath>')
def list_files(subpath=''):
    """获取文件列表"""
    return jsonify(get_file_info(Config.UPLOAD_FOLDER, subpath))

@app.route('/download/<path:filepath>')
def download_file(filepath):
    """下载文件"""
    # 安全检查，确保路径在共享目录内
    safe_path = os.path.normpath(filepath)
    if safe_path.startswith('..') or safe_path.startswith('/'):
        return "非法路径", 400
    
    file_path = os.path.join(Config.UPLOAD_FOLDER, safe_path)
    if not os.path.exists(file_path):
        return "File not found", 404
    
    if os.path.isdir(file_path):
        return "不能下载文件夹", 400
    
    return safe_file_download(file_path, os.path.basename(filepath))

@app.route('/upload', methods=['POST'])
def upload_file():
    """上传文件"""
    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '空文件名'}), 400
    
    # 获取目标路径
    target_path = request.form.get('path', '')
    save_dir = os.path.join(Config.UPLOAD_FOLDER, target_path)
    os.makedirs(save_dir, exist_ok=True)
    
    if file:  # 不再检查文件类型
        filename = file.filename.split('/')[-1].split('\\')[-1]
        save_path = os.path.join(save_dir, filename)
        
        # 分块写入大文件
        chunk_size = 1024 * 1024 * 10  # 10MB chunks
        with open(save_path, 'wb') as f:
            while chunk := file.stream.read(chunk_size):
                f.write(chunk)
                f.flush()
        
        # 通知所有客户端
        socketio.emit('file_update', {'files': get_file_info(Config.UPLOAD_FOLDER, target_path)}, namespace='/file')
        return jsonify({'success': True, 'filename': filename})
    return jsonify({'error': '文件上传失败'}), 400

@app.route('/create_folder', methods=['POST'])
def create_folder():
    """创建文件夹"""
    folder_name = request.json.get('folder_name')
    target_path = request.json.get('path', '')
    
    if not folder_name:
        return jsonify({'success': False, 'error': '文件夹名称不能为空'}), 400
    
    # 防止路径遍历攻击
    if '..' in folder_name or folder_name.startswith('/'):
        return jsonify({'success': False, 'error': '无效的文件夹名称'}), 400
    
    full_path = os.path.join(Config.UPLOAD_FOLDER, target_path, folder_name)
    
    try:
        os.makedirs(full_path, exist_ok=False)
        # 通知所有客户端
        socketio.emit('file_update', {'files': get_file_info(Config.UPLOAD_FOLDER, target_path)}, namespace='/file')
        return jsonify({'success': True, 'message': f'文件夹 {folder_name} 创建成功'})
    except OSError as e:
        return jsonify({'success': False, 'error': f'创建文件夹失败: {str(e)}'}), 400

@app.route('/batch_delete', methods=['POST'])
def batch_delete_files():
    """批量删除文件或文件夹"""
    filepaths = request.json.get('filepaths', [])
    
    if not filepaths:
        return jsonify({'success': False, 'error': '文件路径列表不能为空'}), 400
    
    deleted_count = 0
    errors = []
    
    for filepath in filepaths:
        # 安全检查，确保路径在共享目录内
        safe_path = os.path.normpath(filepath)
        if safe_path.startswith('..') or safe_path.startswith('/'):
            errors.append(f'非法路径: {filepath}')
            continue
        
        file_path = os.path.join(Config.UPLOAD_FOLDER, safe_path)
        
        # 检查文件/文件夹是否存在
        if not os.path.exists(file_path):
            errors.append(f'文件或文件夹不存在: {filepath}')
            continue
        
        try:
            # 删除文件或文件夹
            if os.path.isfile(file_path):
                os.remove(file_path)
            else:
                import shutil
                shutil.rmtree(file_path)
            deleted_count += 1
        except Exception as e:
            errors.append(f'删除失败 {filepath}: {str(e)}')
    
    # 获取父目录路径以刷新正确的文件列表
    parent_path = os.path.dirname(filepaths[0]) if filepaths else ''
    socketio.emit('file_update', {'files': get_file_info(Config.UPLOAD_FOLDER, parent_path)}, namespace='/file')
    
    if errors:
        return jsonify({
            'success': True, 
            'deleted_count': deleted_count,
            'message': f'成功删除 {deleted_count} 个文件/文件夹',
            'errors': errors
        })
    else:
        return jsonify({
            'success': True, 
            'deleted_count': deleted_count,
            'message': f'成功删除 {deleted_count} 个文件/文件夹'
        })

@app.route('/view/<path:filepath>')
def view_file(filepath):
    """在线预览文件"""
    # 安全检查，确保路径在共享目录内
    safe_path = os.path.normpath(filepath)
    if safe_path.startswith('..') or safe_path.startswith('/'):
        return "非法路径", 400
    
    file_path = os.path.join(Config.UPLOAD_FOLDER, safe_path)
    if not os.path.exists(file_path):
        return "File not found", 404
    
    if os.path.isdir(file_path):
        return "不能查看文件夹", 400
    
    ext = os.path.splitext(filepath)[1].lower()

    if ext == '.txt':
        page = request.args.get('page', 0, type=int)
        content, has_more = read_txt_chunk(file_path, chunk_index=page)
        return jsonify({'content': content, 'has_more': has_more, 'page': page + 1})

    # 根据文件类型返回不同的预览方式
    mime_type = None
    
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        mime_type = 'image/*'
    elif ext in ['.mp4', '.avi', '.mov', '.wmv', '.mkv']:
        mime_type = 'video/*'
    elif ext in ['.mp3', '.wav', '.flac']:
        mime_type = 'audio/*'
    elif ext in ['.pdf']:
        mime_type = 'application/pdf'
    
    from urllib.parse import quote
    
    if mime_type:
        response = send_from_directory(
            os.path.dirname(file_path),
            os.path.basename(file_path),
            as_attachment=False,
            mimetype=mime_type
        )
        # 设置正确的Content-Disposition头以支持中文文件名
        if isinstance(response, tuple):
            response = response[0]
        filename = os.path.basename(file_path)
        ascii_filename = filename.encode('ascii', 'ignore').decode('ascii')
        utf8_filename = quote(filename)
        response.headers['Content-Disposition'] = f'inline; filename="{ascii_filename}"; filename*=UTF-8''{utf8_filename}'
        print(f"Previewing file: {file_path}, MIME type: {mime_type}")  # 调试信息
        return response
    
    # 默认以附件形式下载
    response = send_from_directory(
        os.path.dirname(file_path),
        os.path.basename(file_path),
        as_attachment=True
    )
    # 设置正确的Content-Disposition头以支持中文文件名
    if isinstance(response, tuple):
        response = response[0]
    filename = os.path.basename(file_path)
    ascii_filename = filename.encode('ascii', 'ignore').decode('ascii')
    utf8_filename = quote(filename)
    response.headers['Content-Disposition'] = f'attachment; filename="{ascii_filename}"; filename*=UTF-8''{utf8_filename}'
    return response

# ================= SocketIO事件 =================
@socketio.on('connect', namespace='/file')
def handle_connect():
    """处理客户端连接"""
    emit('file_update', {'files': get_file_info(Config.UPLOAD_FOLDER)})






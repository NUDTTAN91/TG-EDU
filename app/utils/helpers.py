"""辅助函数"""
import os
import re
from datetime import timezone, timedelta
from flask import current_app


BEIJING_TZ = timezone(timedelta(hours=8))


def safe_chinese_filename(filename):
    """创建支持中文的安全文件名"""
    if not filename:
        return 'untitled'
    
    safe_name = re.sub(r'[<>:"/\\|?*]', '', filename)
    safe_name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe_name)
    safe_name = safe_name.strip()
    
    if not safe_name:
        return 'untitled'
    
    if len(safe_name.encode('utf-8')) > 200:
        truncated = safe_name[:100]
        while len(truncated.encode('utf-8')) > 200 and len(truncated) > 0:
            truncated = truncated[:-1]
        safe_name = truncated
    
    return safe_name


def to_beijing_time(utc_dt):
    """将UTC时间转换为北京时间"""
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(BEIJING_TZ)


def get_file_size(file_path):
    """获取文件大小"""
    try:
        return os.path.getsize(file_path)
    except:
        return 0


def allowed_file(filename, allowed_extensions=None):
    """检查文件类型是否允许"""
    if not allowed_extensions:
        allowed_extensions = {'txt', 'pdf', 'doc', 'docx', 'zip', 'rar',
                            'py', 'java', 'cpp', 'c', 'html', 'css', 'js'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

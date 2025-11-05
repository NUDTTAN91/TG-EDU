"""文件处理服务"""
import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename
from app.utils.helpers import safe_chinese_filename, get_file_size


class FileService:
    """文件服务类"""
    
    @staticmethod
    def save_assignment_attachment(attachment_file):
        """保存作业附件"""
        if not attachment_file or not attachment_file.filename:
            return None, None, None, None
        
        original_filename = attachment_file.filename
        filename = secure_filename(original_filename)
        
        if not filename:
            file_ext = os.path.splitext(original_filename)[1] if '.' in original_filename else ''
            filename = str(uuid.uuid4()) + file_ext
        
        unique_filename = f"{uuid.uuid4()}_{filename}"
        appendix_folder = current_app.config['APPENDIX_FOLDER']
        os.makedirs(appendix_folder, exist_ok=True)
        
        file_path = os.path.join(appendix_folder, unique_filename)
        
        try:
            attachment_file.save(file_path)
            file_size = get_file_size(file_path)
            return filename, original_filename, file_path, file_size
        except Exception as e:
            current_app.logger.error(f"保存附件失败: {e}")
            return None, None, None, None
    
    @staticmethod
    def delete_file(file_path):
        """删除文件"""
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except Exception as e:
                current_app.logger.error(f"删除文件失败: {e}")
                return False
        return True
    
    @staticmethod
    def validate_file_path(file_path, allowed_base_dir):
        """验证文件路径是否在允许的目录内"""
        abs_file_path = os.path.abspath(file_path)
        abs_base_dir = os.path.abspath(allowed_base_dir)
        return abs_file_path.startswith(abs_base_dir)

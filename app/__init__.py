"""应用工厂"""
import os
from flask import Flask
from flask_login import current_user
from config import config
from app.extensions import db, login_manager, init_extensions
from app.models import User
from app.utils import to_beijing_time, BEIJING_TZ


def create_app(config_name='default'):
    """创建Flask应用实例"""
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(config[config_name])
    
    # 确保必要的目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['STORAGE_DIR'], 'data'), exist_ok=True)
    os.makedirs(app.config['APPENDIX_FOLDER'], exist_ok=True)
    
    # 初始化扩展
    init_extensions(app)
    
    # 注册user_loader
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # 注册Jinja2过滤器
    register_filters(app)
    
    # 注册上下文处理器
    register_context_processors(app)
    
    # 注册蓝图
    register_blueprints(app)
    
    # 初始化定时任务调度器
    init_scheduler(app)
    
    return app


def register_filters(app):
    """注册Jinja2过滤器"""
    @app.template_filter('beijing_time')
    def beijing_time_filter(utc_dt):
        """将UTC时间转换为北京时间并格式化"""
        beijing_dt = to_beijing_time(utc_dt)
        if beijing_dt is None:
            return '未知'
        return beijing_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    @app.template_filter('beijing_date')
    def beijing_date_filter(utc_dt):
        """将UTC时间转换为北京时间日期"""
        beijing_dt = to_beijing_time(utc_dt)
        if beijing_dt is None:
            return '未知'
        return beijing_dt.strftime('%Y-%m-%d')
    
    @app.template_filter('beijing_short')
    def beijing_short_filter(utc_dt):
        """将UTC时间转换为北京时间短格式"""
        beijing_dt = to_beijing_time(utc_dt)
        if beijing_dt is None:
            return '未知'
        return beijing_dt.strftime('%m-%d %H:%M')
    
    @app.template_filter('beijing_datetime_local')
    def beijing_datetime_local_filter(utc_dt):
        """将UTC时间转换为北京时间，用于datetime-local输入框"""
        beijing_dt = to_beijing_time(utc_dt)
        if beijing_dt is None:
            return ''
        return beijing_dt.strftime('%Y-%m-%dT%H:%M')
    
    @app.template_filter('nl2br')
    def nl2br_filter(text):
        """将换行符转换为HTML换行标签"""
        if not text:
            return ''
        from markupsafe import Markup
        return Markup(text.replace('\n', '<br>'))
    
    @app.template_filter('filesize')
    def filesize_filter(size_bytes):
        """智能格式化文件大小"""
        if not size_bytes or size_bytes == 0:
            return '0 B'
        
        # 定义单位
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        # 找到合适的单位
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        # 格式化：小于1KB显示整数字节，其他显示1位小数
        if unit_index == 0:
            return f'{int(size)} {units[unit_index]}'
        else:
            return f'{size:.1f} {units[unit_index]}'


def register_context_processors(app):
    """注册上下文处理器"""
    from app.services.notification_service import NotificationService
    
    @app.context_processor
    def inject_unread_notifications():
        if current_user.is_authenticated:
            unread_count = NotificationService.get_unread_count(current_user.id)
            return dict(unread_notification_count=unread_count)
        return dict(unread_notification_count=0)


def register_blueprints(app):
    """注册所有蓝图"""
    # 延迟导入避免循环依赖
    from app.routes import (main, auth, admin, student, user_mgmt, 
                            class_mgmt, assignment, submission, grading,
                            download, notification, advanced, import_export, major_assignment, makeup, logs)
    
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(student.bp)
    app.register_blueprint(user_mgmt.bp)
    app.register_blueprint(class_mgmt.bp)
    app.register_blueprint(assignment.bp)
    app.register_blueprint(submission.bp)
    app.register_blueprint(grading.bp)
    app.register_blueprint(download.bp)
    app.register_blueprint(notification.bp)
    app.register_blueprint(advanced.bp)
    app.register_blueprint(import_export.bp)
    app.register_blueprint(major_assignment.bp)
    app.register_blueprint(makeup.bp)
    app.register_blueprint(logs.bp)


def init_scheduler(app):
    """初始化定时任务调度器"""
    from app.services.scheduler_service import init_scheduler as _init_scheduler
    _init_scheduler(app)

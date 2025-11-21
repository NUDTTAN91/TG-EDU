"""权限装饰器"""
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from app.models import UserRole


def check_password_change_required(f):
    """
    检查用户是否需要强制修改密码
    如果用户需要修改密码（非超级管理员），则重定向到修改密码页面
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 如果用户已登录且需要修改密码（非超级管理员）
        if current_user.is_authenticated and current_user.must_change_password and not current_user.is_super_admin:
            # 允许访问强制修改密码页面和登出页面
            from flask import request
            if request.endpoint not in ['auth.force_change_password', 'auth.logout']:
                flash('您必须先修改密码才能继续使用系统', 'warning')
                return redirect(url_for('auth.force_change_password'))
        return f(*args, **kwargs)
    return decorated_function


def require_role(role):
    """要求特定角色的装饰器"""
    def decorator(f):
        @wraps(f)
        @check_password_change_required
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role != role and current_user.role != UserRole.SUPER_ADMIN:
                flash('您没有权限访问此页面')
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_teacher_or_admin(f):
    """要求教师或管理员权限"""
    @wraps(f)
    @check_password_change_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not (current_user.is_teacher or current_user.is_super_admin):
            flash('您没有权限访问此页面')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def require_login(f):
    """要求登录"""
    @wraps(f)
    @check_password_change_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def log_operation(operation_type, operation_desc=None):
    """
    记录操作日志的装饰器
    
    Args:
        operation_type: 操作类型（login, submit, view, apply等）
        operation_desc: 操作描述（可选，如果不提供则使用函数名）
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from app.services.log_service import LogService
            
            # 执行函数
            try:
                result = f(*args, **kwargs)
                # 记录成功日志
                desc = operation_desc if operation_desc else f"{f.__name__}"
                LogService.log_operation(operation_type, desc, result='success')
                return result
            except Exception as e:
                # 记录失败日志
                desc = operation_desc if operation_desc else f"{f.__name__}"
                LogService.log_operation(operation_type, desc, result='failed', error_msg=str(e))
                raise  # 重新抛出异常
        
        return decorated_function
    return decorator

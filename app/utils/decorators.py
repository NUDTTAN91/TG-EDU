"""权限装饰器"""
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from app.models import UserRole


def require_role(role):
    """要求特定角色的装饰器"""
    def decorator(f):
        @wraps(f)
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
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

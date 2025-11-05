"""认证相关路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, UserRole
from app.extensions import db

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # 支持用户名、真实姓名、学号登录
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User.query.filter_by(real_name=username).first()
        if not user:
            user = User.query.filter_by(student_id=username).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            
            # 检查是否需要强制修改密码
            if user.must_change_password and not user.is_super_admin:
                flash('您是首次登录，必须修改密码后才能继续使用系统')
                return redirect(url_for('auth.force_change_password'))
            
            # 根据角色重定向
            if user.is_super_admin:
                return redirect(url_for('admin.super_admin_dashboard'))
            elif user.is_teacher:
                return redirect(url_for('admin.teacher_dashboard'))
            else:
                return redirect(url_for('student.dashboard'))
        else:
            flash('用户名或密码错误，或者账户已被禁用')
    
    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    """登出"""
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/force-change-password', methods=['GET', 'POST'])
@login_required
def force_change_password():
    """强制修改密码"""
    if not current_user.must_change_password or current_user.is_super_admin:
        if current_user.is_super_admin:
            return redirect(url_for('admin.super_admin_dashboard'))
        elif current_user.is_teacher:
            return redirect(url_for('admin.teacher_dashboard'))
        else:
            return redirect(url_for('student.dashboard'))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if not current_user.check_password(current_password):
            flash('当前密码错误')
            return render_template('force_change_password.html')
        
        if len(new_password) < 6:
            flash('新密码长度至少6位')
            return render_template('force_change_password.html')
        
        if new_password != confirm_password:
            flash('两次输入的新密码不一致')
            return render_template('force_change_password.html')
        
        if new_password == current_password:
            flash('新密码不能与当前密码相同')
            return render_template('force_change_password.html')
        
        current_user.set_password(new_password)
        current_user.must_change_password = False
        db.session.commit()
        
        flash('密码修改成功，欢迎使用系统！')
        
        if current_user.is_teacher:
            return redirect(url_for('admin.teacher_dashboard'))
        else:
            return redirect(url_for('student.dashboard'))
    
    return render_template('force_change_password.html')

"""管理员相关路由"""
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import (
    User, UserRole, Class, Assignment, Submission
)
from app.utils import require_role, require_teacher_or_admin

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route('/')
@login_required
def dashboard():
    """管理员仪表板 - 根据角色重定向"""
    if current_user.is_super_admin:
        return redirect(url_for('admin.super_admin_dashboard'))
    elif current_user.is_teacher:
        return redirect(url_for('admin.teacher_dashboard'))
    else:
        return redirect(url_for('student.dashboard'))


@bp.route('/super-admin')
@login_required
@require_role(UserRole.SUPER_ADMIN)
def super_admin_dashboard():
    """超级管理员仪表板"""
    total_users = User.query.count()
    total_teachers = User.query.filter_by(role=UserRole.TEACHER).count()
    total_students = User.query.filter_by(role=UserRole.STUDENT).count()
    total_assignments = Assignment.query.count()
    total_submissions = Submission.query.count()
    total_classes = Class.query.count()
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_assignments = Assignment.query.order_by(Assignment.created_at.desc()).limit(5).all()
    
    # 获取所有作业用于管理
    assignments = Assignment.query.order_by(Assignment.created_at.desc()).all()
    
    return render_template('super_admin_dashboard.html',
                         total_users=total_users,
                         total_teachers=total_teachers,
                         total_students=total_students,
                         total_assignments=total_assignments,
                         total_submissions=total_submissions,
                         total_classes=total_classes,
                         recent_users=recent_users,
                         recent_assignments=recent_assignments,
                         assignments=assignments)


@bp.route('/teacher')
@login_required
@require_teacher_or_admin
def teacher_dashboard():
    """教师仪表板"""
    # 教师可以看到两种作业：
    # 1. 自己创建的作业
    # 2. 分配给自己负责班级的作业（由超级管理员创建）
    
    # 获取教师自己创建的作业
    own_assignments = Assignment.query.filter_by(teacher_id=current_user.id).all()
    
    # 获取教师负责班级的所有作业
    teacher_classes = current_user.teaching_classes
    class_assignments = []
    if teacher_classes:
        class_ids = [c.id for c in teacher_classes]
        class_assignments = Assignment.query.filter(
            Assignment.class_id.in_(class_ids),
            Assignment.teacher_id != current_user.id
        ).all()
    
    # 合并所有作业并按创建时间排序
    all_assignments = own_assignments + class_assignments
    assignments = sorted(all_assignments, key=lambda x: x.created_at, reverse=True)
    
    # 获取教师创建的学生
    my_students = User.query.filter_by(role=UserRole.STUDENT, created_by=current_user.id).all()
    
    return render_template('teacher_dashboard.html',
                         assignments=assignments,
                         my_students=my_students)

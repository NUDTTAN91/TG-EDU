"""管理员相关路由"""
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
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
    from flask import request
    
    # 获取班级筛选参数
    class_filter = request.args.get('class_id', type=int)
    
    # 使用缓存或异步方式获取统计数据，避免阻塞
    from sqlalchemy import func
    
    # 批量获取统计数据，减少数据库往返
    stats = db.session.query(
        func.count(User.id).label('total_users'),
        func.sum(db.case((User.role == UserRole.TEACHER, 1), else_=0)).label('total_teachers'),
        func.sum(db.case((User.role == UserRole.STUDENT, 1), else_=0)).label('total_students')
    ).first()
    
    total_users = stats.total_users or 0
    total_teachers = int(stats.total_teachers or 0)
    total_students = int(stats.total_students or 0)
    
    # 简单计数，使用较短超时避免长时间阻塞
    # 如果数据库被锁，这些查询会很快返回或超时
    try:
        total_assignments = db.session.execute(db.text('SELECT COUNT(*) FROM assignment')).scalar()
        total_submissions = db.session.execute(db.text('SELECT COUNT(*) FROM submission')).scalar()
        total_classes = db.session.execute(db.text('SELECT COUNT(*) FROM class WHERE is_active = 1')).scalar()
    except Exception as e:
        # 如果查询失败，使用缓存值或默认值
        total_assignments = 0
        total_submissions = 0
        total_classes = 0
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_assignments = Assignment.query.order_by(Assignment.created_at.desc()).limit(5).all()
    
    # 获取所有作业用于管理
    assignments_query = Assignment.query
    
    # 应用班级筛选
    if class_filter is not None:
        if class_filter == 0:
            # 筛选公共作业（class_id 为 None）
            assignments_query = assignments_query.filter(Assignment.class_id.is_(None))
        else:
            # 筛选指定班级
            assignments_query = assignments_query.filter_by(class_id=class_filter)
    
    assignments = assignments_query.order_by(Assignment.created_at.desc()).all()
    
    # 获取所有班级用于筛选
    all_classes = Class.query.filter_by(is_active=True).order_by(Class.name).all()
    
    return render_template('super_admin_dashboard.html',
                         total_users=total_users,
                         total_teachers=total_teachers,
                         total_students=total_students,
                         total_assignments=total_assignments,
                         total_submissions=total_submissions,
                         total_classes=total_classes,
                         recent_users=recent_users,
                         recent_assignments=recent_assignments,
                         assignments=assignments,
                         all_classes=all_classes,
                         selected_class_id=class_filter)


@bp.route('/teacher')
@login_required
@require_teacher_or_admin
def teacher_dashboard():
    """教师仪表板"""
    from flask import request
    
    # 检查是否需要强制修改密码
    if current_user.must_change_password:
        return redirect(url_for('auth.force_change_password'))
    
    # 获取班级筛选参数
    class_filter = request.args.get('class_id', type=int)
    
    # 教师可以看到两种作业：
    # 1. 自己创建的作业
    # 2. 分配给自己负责班级的作业（由超级管理员创建）
    
    # 获取教师自己创建的作业
    own_assignments_query = Assignment.query.filter_by(teacher_id=current_user.id)
    
    # 获取教师负责班级的所有作业
    teacher_classes = current_user.teaching_classes
    class_assignments = []
    if teacher_classes:
        class_ids = [c.id for c in teacher_classes]
        class_assignments_query = Assignment.query.filter(
            Assignment.class_id.in_(class_ids),
            Assignment.teacher_id != current_user.id
        )
        
        # 应用班级筛选
        if class_filter:
            # 检查教师是否有权限查看该班级
            if class_filter in class_ids:
                own_assignments_query = own_assignments_query.filter_by(class_id=class_filter)
                class_assignments_query = class_assignments_query.filter_by(class_id=class_filter)
            else:
                class_filter = None  # 无权限，重置筛选
        
        class_assignments = class_assignments_query.all()
    
    # 应用班级筛选到自己的作业
    if class_filter:
        own_assignments = own_assignments_query.all()
    else:
        own_assignments = own_assignments_query.all()
    
    # 合并所有作业并按创建时间排序
    all_assignments = own_assignments + class_assignments
    assignments = sorted(all_assignments, key=lambda x: x.created_at, reverse=True)
    
    # 获取教师创建的学生
    my_students = User.query.filter_by(role=UserRole.STUDENT, created_by=current_user.id).all()
    
    # 获取待处理的补交申请数量
    from app.models import MakeupRequest
    pending_makeup_count = 0
    if current_user.is_super_admin:
        pending_makeup_count = MakeupRequest.query.filter_by(status='pending').count()
    elif teacher_classes:
        # 普通老师只看自己班级的申请
        class_ids = [c.id for c in teacher_classes]
        assignment_ids = [a.id for a in Assignment.query.filter(Assignment.class_id.in_(class_ids)).all()]
        pending_makeup_count = MakeupRequest.query.filter(
            MakeupRequest.assignment_id.in_(assignment_ids),
            MakeupRequest.status == 'pending'
        ).count()
    
    return render_template('teacher_dashboard.html',
                         assignments=assignments,
                         my_students=my_students,
                         teacher_classes=teacher_classes,
                         selected_class_id=class_filter,
                         pending_makeup_count=pending_makeup_count)

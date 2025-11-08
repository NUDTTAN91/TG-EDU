"""学生相关路由"""
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.models import Assignment, Submission, UserRole, AssignmentGrade, MakeupRequest
from app.models.team import MajorAssignment
from app.utils import require_role
from app.services.log_service import LogService

bp = Blueprint('student', __name__, url_prefix='/student')


@bp.route('/')
@login_required
@require_role(UserRole.STUDENT)
def dashboard():
    """学生仪表板"""
    # 获取学生所在班级的作业
    student_classes = current_user.classes
    if student_classes:
        class_ids = [c.id for c in student_classes]
        # 获取所有相关作业（包括班级作业和公共作业）
        assignments = Assignment.query.filter(
            Assignment.is_active == True,
            or_(
                Assignment.class_id.in_(class_ids),
                Assignment.class_id.is_(None)
            )
        ).order_by(Assignment.created_at.desc()).limit(100).all()
        
        # 获取大作业
        major_assignments = MajorAssignment.query.filter(
            MajorAssignment.class_id.in_(class_ids),
            MajorAssignment.is_active == True
        ).order_by(MajorAssignment.created_at.desc()).all()
    else:
        # 如果学生没有分配到任何班级，只显示公共作业
        assignments = Assignment.query.filter(
            Assignment.class_id.is_(None),
            Assignment.is_active == True
        ).order_by(Assignment.created_at.desc()).limit(100).all()
        major_assignments = []
    
    # 获取用户的提交记录（限制最近50条）
    my_submissions = Submission.query.filter_by(
        student_id=current_user.id
    ).order_by(Submission.submitted_at.desc()).limit(50).all()
    
    # 获取补交评分记录（用于判断是否已经打了补交分）
    makeup_grades = AssignmentGrade.query.filter_by(
        student_id=current_user.id,
        is_makeup=True
    ).all()
    makeup_grade_dict = {g.assignment_id: g for g in makeup_grades}
    
    # 获取补交提交记录（is_makeup=True）
    makeup_submissions = Submission.query.filter_by(
        student_id=current_user.id,
        is_makeup=True
    ).all()
    makeup_submission_dict = {}
    for sub in makeup_submissions:
        # 只保留每个作业最新的补交提交
        if sub.assignment_id not in makeup_submission_dict:
            makeup_submission_dict[sub.assignment_id] = sub
    
    # 获取待处理的补交申请（用于显示按钮状态）
    pending_requests = MakeupRequest.query.filter_by(
        student_id=current_user.id,
        status='pending'
    ).all()
    pending_request_dict = {r.assignment_id: r for r in pending_requests}
    
    # 获取已批准的补交申请（用于显示“补交作业”按钮）
    approved_requests = MakeupRequest.query.filter_by(
        student_id=current_user.id,
        status='approved'
    ).order_by(MakeupRequest.id.desc()).all()  # 按ID降序，保证最新的在前
    # 只保留每个作业最新的补交申请
    approved_request_dict = {}
    for r in approved_requests:
        if r.assignment_id not in approved_request_dict:
            approved_request_dict[r.assignment_id] = r
    
    # 传递当前时间用于模板判断
    from datetime import datetime
    current_time = datetime.utcnow()
    
    # 记录查看日志
    LogService.log_operation(
        operation_type='view',
        operation_desc=f'查看学生中心（作业数：{len(assignments)}）',
        result='success'
    )
    
    return render_template('student_dashboard.html',
                         assignments=assignments,
                         major_assignments=major_assignments,
                         my_submissions=my_submissions,
                         makeup_grade_dict=makeup_grade_dict,
                         makeup_submission_dict=makeup_submission_dict,
                         pending_request_dict=pending_request_dict,
                         approved_request_dict=approved_request_dict,
                         current_time=current_time)

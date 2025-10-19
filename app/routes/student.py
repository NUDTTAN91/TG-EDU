"""学生相关路由"""
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.models import Assignment, Submission, UserRole
from app.utils import require_role

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
    else:
        # 如果学生没有分配到任何班级，只显示公共作业
        assignments = Assignment.query.filter(
            Assignment.class_id.is_(None),
            Assignment.is_active == True
        ).order_by(Assignment.created_at.desc()).limit(100).all()
    
    # 获取用户的提交记录（限制最近50条）
    my_submissions = Submission.query.filter_by(
        student_id=current_user.id
    ).order_by(Submission.submitted_at.desc()).limit(50).all()
    
    return render_template('student_dashboard.html',
                         assignments=assignments,
                         my_submissions=my_submissions)

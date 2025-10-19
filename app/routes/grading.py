"""评分相关路由"""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Assignment, Submission, User, Class, UserRole
from app.models.assignment import AssignmentGrade
from app.utils.decorators import require_teacher_or_admin
from app.services import NotificationService

bp = Blueprint('grading', __name__, url_prefix='/admin')


def can_manage_assignment(user, assignment):
    """检查用户是否可以管理此作业"""
    # 超级管理员可以管理所有作业
    if user.is_super_admin:
        return True
    
    # 教师可以管理自己创建的作业
    if assignment.teacher_id == user.id:
        return True
    
    # 教师可以管理分配给自己负责班级的作业
    if user.is_teacher and assignment.class_id:
        teacher_class_ids = [c.id for c in user.teaching_classes]
        if assignment.class_id in teacher_class_ids:
            return True
    
    return False


@bp.route('/assignment/<int:assignment_id>/student/<int:student_id>/grade_assignment', methods=['GET', 'POST'])
@login_required
@require_teacher_or_admin
def grade_assignment_overall(assignment_id, student_id):
    """教师给学生的整个作业进行评分（新的评分机制）"""
    assignment = Assignment.query.get_or_404(assignment_id)
    student = User.query.get_or_404(student_id)
    
    # 权限检查
    if not can_manage_assignment(current_user, assignment):
        flash('您没有权限评分此作业')
        return redirect(url_for('admin.teacher_dashboard' if current_user.is_teacher else 'admin.super_admin_dashboard'))
    
    # 获取该学生的所有提交记录
    submissions = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=student_id
    ).order_by(Submission.submitted_at.desc()).all()
    
    if not submissions:
        flash('该学生尚未提交此作业')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
    
    # 获取当前教师对此作业的评分记录
    existing_grade = AssignmentGrade.query.filter_by(
        assignment_id=assignment_id,
        student_id=student_id,
        teacher_id=current_user.id
    ).first()
    
    if request.method == 'POST':
        grade = request.form.get('grade')
        feedback = request.form.get('feedback', '')
        
        # 验证评分
        grade_float = None
        if grade:
            try:
                grade_float = float(grade)
                if grade_float < 0 or grade_float > 100:
                    flash('评分必须在0-100之间')
                    return render_template('grade_assignment_overall.html', 
                                         assignment=assignment, 
                                         student=student, 
                                         submissions=submissions,
                                         existing_grade=existing_grade)
            except ValueError:
                flash('评分必须是有效的数字')
                return render_template('grade_assignment_overall.html', 
                                     assignment=assignment, 
                                     student=student, 
                                     submissions=submissions,
                                     existing_grade=existing_grade)
        
        # 创建或更新评分记录
        if existing_grade:
            existing_grade.grade = grade_float
            existing_grade.feedback = feedback
            existing_grade.updated_at = datetime.utcnow()
        else:
            existing_grade = AssignmentGrade(
                assignment_id=assignment_id,
                student_id=student_id,
                teacher_id=current_user.id,
                grade=grade_float,
                feedback=feedback
            )
            db.session.add(existing_grade)
        
        db.session.commit()
        
        # 创建通知 - 通知学生作业已被评分
        if student.id:
            notification_title = f'作业「{assignment.title}」已被评分'
            notification_content = f'教师 {current_user.real_name} 已对您的作业进行了整体评分'
            if grade_float is not None:
                notification_content += f'，得分：{grade_float}分'
            if feedback:
                notification_content += f'\n\n评语：{feedback[:100]}...' if len(feedback) > 100 else f'\n\n评语：{feedback}'
            
            NotificationService.create_notification(
                sender_id=current_user.id,
                receiver_id=student.id,
                title=notification_title,
                content=notification_content,
                notification_type='grade',
                related_assignment_id=assignment_id
            )
        
        flash(f'已成功给 {student.real_name} 的作业评分')
        
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
    
    return render_template('grade_assignment_overall.html', 
                         assignment=assignment, 
                         student=student, 
                         submissions=submissions,
                         existing_grade=existing_grade)


@bp.route('/assignment/<int:assignment_id>/student/<int:student_id>/grade', methods=['GET', 'POST'])
@login_required
@require_teacher_or_admin
def grade_student_submissions(assignment_id, student_id):
    """教师给学生的作业进行评分（旧的评分机制 - 针对单次提交）"""
    assignment = Assignment.query.get_or_404(assignment_id)
    student = User.query.get_or_404(student_id)
    
    # 权限检查
    if not can_manage_assignment(current_user, assignment):
        flash('您没有权限评分此作业')
        return redirect(url_for('admin.teacher_dashboard' if current_user.is_teacher else 'admin.super_admin_dashboard'))
    
    # 获取该学生的所有提交记录
    submissions = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=student_id
    ).order_by(Submission.submitted_at.desc()).all()
    
    if not submissions:
        flash('该学生尚未提交此作业')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
    
    if request.method == 'POST':
        submission_id = request.form.get('submission_id')
        grade = request.form.get('grade')
        feedback = request.form.get('feedback', '')
        
        if not submission_id:
            flash('请选择要评分的提交记录')
            return render_template('grade_student_submissions.html', 
                                 assignment=assignment, 
                                 student=student, 
                                 submissions=submissions)
        
        submission = Submission.query.get_or_404(submission_id)
        
        # 验证评分
        if grade:
            try:
                grade_float = float(grade)
                if grade_float < 0 or grade_float > 100:
                    flash('评分必须在0-100之间')
                    return render_template('grade_student_submissions.html', 
                                         assignment=assignment, 
                                         student=student, 
                                         submissions=submissions)
                submission.grade = grade_float
            except ValueError:
                flash('评分必须是有效的数字')
                return render_template('grade_student_submissions.html', 
                                     assignment=assignment, 
                                     student=student, 
                                     submissions=submissions)
        else:
            submission.grade = None
        
        submission.feedback = feedback
        submission.graded_by = current_user.id
        submission.graded_at = datetime.utcnow()
        
        db.session.commit()
        
        # 创建通知 - 通知学生作业已被批改
        if student.id:  # 确保学生ID存在
            notification_title = f'作业「{assignment.title}」已被批改'
            notification_content = f'教师 {current_user.real_name} 已对您的作业进行了评分'
            if grade:
                notification_content += f'，得分：{grade_float}分'
            if feedback:
                notification_content += f'\n\n评语：{feedback[:100]}...' if len(feedback) > 100 else f'\n\n评语：{feedback}'
            
            NotificationService.create_notification(
                sender_id=current_user.id,
                receiver_id=student.id,
                title=notification_title,
                content=notification_content,
                notification_type='grade',
                related_assignment_id=assignment_id,
                related_submission_id=submission.id
            )
        
        flash(f'已成功评分 {student.real_name} 的作业')
        
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
    
    return render_template('grade_student_submissions.html', 
                         assignment=assignment, 
                         student=student, 
                         submissions=submissions)


def can_teacher_manage_student(teacher, student):
    """检查教师是否有权限管理某个学生"""
    # 只能管理学生角色
    if student.role != UserRole.STUDENT:
        return False
    
    # 超级管理员可以管理所有学生
    if teacher.is_super_admin:
        return True
    
    # 教师只能管理自己班级中的学生
    if teacher.is_teacher:
        # 获取教师负责的所有班级
        teacher_classes = teacher.teaching_classes
        
        # 检查学生是否在这些班级中
        for class_obj in teacher_classes:
            if student in class_obj.students:
                return True
    
    return False

"""作业管理路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from collections import defaultdict
from app.extensions import db
from app.models import Assignment, Class, User, UserRole, Submission, AssignmentGrade
from app.services import FileService, NotificationService
from app.utils import require_teacher_or_admin, to_beijing_time
from sqlalchemy import func

bp = Blueprint('assignment', __name__, url_prefix='/admin/assignment')


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_teacher_or_admin
def create_assignment():
    """创建作业"""
    # 普通教师权限检查：必须有班级或导入过学生才能创建作业
    if current_user.is_teacher and not current_user.is_super_admin:
        # 检查是否有负责的班级
        has_classes = len(current_user.teaching_classes) > 0
        # 检查是否导入过学生
        has_created_students = User.query.filter_by(
            role=UserRole.STUDENT, 
            created_by=current_user.id
        ).first() is not None
        
        if not has_classes and not has_created_students:
            flash('您还没有班级或学生，无法创建作业。请先在"学生管理"中导入学生，或联系管理员为您分配班级。')
            return redirect(url_for('admin.teacher_dashboard'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        due_date_str = request.form['due_date']
        allowed_file_types = request.form.get('allowed_file_types', '')
        max_file_size = request.form.get('max_file_size', '50')
        max_submissions = request.form.get('max_submissions', '0')
        class_id = request.form.get('class_id')
        
        # 处理附件上传
        attachment_filename = None
        attachment_original_filename = None
        attachment_file_path = None
        attachment_file_size = None
        
        if 'attachment' in request.files:
            attachment_file = request.files['attachment']
            if attachment_file and attachment_file.filename:
                attachment_filename, attachment_original_filename, attachment_file_path, attachment_file_size = \
                    FileService.save_assignment_attachment(attachment_file)
        
        # 验证班级权限
        if class_id:
            selected_class = Class.query.get(class_id)
            if not selected_class:
                flash('选择的班级不存在')
                return render_template('create_assignment.html', available_classes=get_available_classes())
            
            if not current_user.is_super_admin and current_user not in selected_class.teachers:
                flash('您没有权限为此班级创建作业')
                return render_template('create_assignment.html', available_classes=get_available_classes())
        
        # 处理截止时间
        due_date = None
        if due_date_str:
            try:
                local_time = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
                due_date = local_time - timedelta(hours=8)  # 转换为UTC
            except ValueError:
                flash('日期格式错误')
                return render_template('create_assignment.html', available_classes=get_available_classes())
        
        # 处理文件大小限制
        try:
            max_size_mb = float(max_file_size)
            if max_size_mb < 1:
                flash('文件大小不能小于1MB')
                return render_template('create_assignment.html', available_classes=get_available_classes())
            elif max_size_mb > 10240:
                flash('文件大小不能超过10GB (10240MB)')
                return render_template('create_assignment.html', available_classes=get_available_classes())
            max_size_bytes = int(max_size_mb * 1024 * 1024)
        except (ValueError, TypeError):
            max_size_bytes = 50 * 1024 * 1024
        
        # 处理提交次数限制
        try:
            max_submissions_count = int(max_submissions)
            if max_submissions_count < 0:
                max_submissions_count = 0
        except (ValueError, TypeError):
            max_submissions_count = 0
        
        # 处理文件类型
        if allowed_file_types:
            file_types = []
            for ext in allowed_file_types.split(','):
                ext = ext.strip().lower()
                if ext.startswith('.'):
                    ext = ext[1:]
                if ext:
                    file_types.append(ext)
            allowed_file_types = ','.join(file_types)
        
        assignment = Assignment(
            title=title,
            description=description,
            due_date=due_date,
            allowed_file_types=allowed_file_types,
            max_file_size=max_size_bytes,
            max_submissions=max_submissions_count,
            teacher_id=current_user.id,
            class_id=class_id if class_id else None,
            attachment_filename=attachment_filename,
            attachment_original_filename=attachment_original_filename,
            attachment_file_path=attachment_file_path,
            attachment_file_size=attachment_file_size
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        # 发送通知给学生
        if class_id:
            # 特定班级的作业，通知该班级的所有学生
            selected_class = Class.query.get(class_id)
            students = selected_class.students
            for student in students:
                NotificationService.create_notification(
                    sender_id=current_user.id,
                    receiver_id=student.id,
                    title=f'新作业：{title}',
                    content=f'{current_user.real_name} 老师布置了新作业「{title}」。' + 
                            (f'截止时间：{to_beijing_time(due_date).strftime("%Y-%m-%d %H:%M")}' if due_date else '无截止时间'),
                    notification_type='assignment'
                )
        else:
            # 公共作业，通知所有学生
            all_students = User.query.filter_by(role=UserRole.STUDENT).all()
            for student in all_students:
                NotificationService.create_notification(
                    sender_id=current_user.id,
                    receiver_id=student.id,
                    title=f'新作业：{title}',
                    content=f'{current_user.real_name} 老师布置了新作业「{title}」。' + 
                            (f'截止时间：{to_beijing_time(due_date).strftime("%Y-%m-%d %H:%M")}' if due_date else '无截止时间'),
                    notification_type='assignment'
                )
        
        flash('作业创建成功')
        
        if current_user.is_super_admin:
            return redirect(url_for('admin.super_admin_dashboard'))
        else:
            return redirect(url_for('admin.teacher_dashboard'))
    
    available_classes = get_available_classes()
    return render_template('create_assignment.html', available_classes=available_classes)


@bp.route('/<int:assignment_id>/submissions')
@login_required
@require_teacher_or_admin
def view_submissions(assignment_id):
    """查看作业提交"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 权限检查
    if not can_manage_assignment(current_user, assignment):
        flash('您没有权限查看此作业')
        return redirect(url_for('admin.teacher_dashboard' if current_user.is_teacher else 'admin.super_admin_dashboard'))
    
    # 获取所有提交记录（过滤掉补交提交）
    submissions = Submission.query.filter_by(
        assignment_id=assignment_id,
        is_makeup=False
    ).order_by(Submission.submitted_at.desc()).all()
    
    # 按学生分组统计
    student_submissions = defaultdict(list)
    for submission in submissions:
        if submission.student_id is None:
            continue
        student_key = (submission.student_id, submission.student_name, submission.student_number)
        student_submissions[student_key].append(submission)
    
    # 构建学生提交统计数据（只显示已提交的学生）
    student_stats = []
    for (student_id, student_name, student_number), student_subs in student_submissions.items():
        latest_submission = student_subs[0]
        submission_count = len(student_subs)
        
        # 获取最新评分
        latest_grade = get_student_assignment_average_grade(assignment_id, student_id)
        latest_feedback = None
        
        # 获取最近的反馈
        latest_grade_record = AssignmentGrade.query.filter(
            AssignmentGrade.assignment_id == assignment_id,
            AssignmentGrade.student_id == student_id,
            AssignmentGrade.feedback.isnot(None),
            AssignmentGrade.feedback != ''
        ).order_by(AssignmentGrade.updated_at.desc()).first()
        
        if latest_grade_record:
            latest_feedback = latest_grade_record.feedback
        
        # 如果新系统没有评分，尝试从旧系统获取
        if latest_grade is None:
            graded_submissions = [s for s in student_subs if s.grade is not None]
            if graded_submissions:
                latest_graded = graded_submissions[0]
                latest_grade = latest_graded.grade
                if not latest_feedback:
                    latest_feedback = latest_graded.feedback
        
        student_stats.append({
            'student_id': student_id,
            'student_name': student_name,
            'student_number': student_number,
            'submission_count': submission_count,
            'latest_submission': latest_submission,
            'latest_grade': latest_grade,
            'latest_feedback': latest_feedback,
            'all_submissions': student_subs
        })
    
    # 按学生姓名排序
    student_stats.sort(key=lambda x: x['student_name'])
    
    return render_template('submissions.html', assignment=assignment, student_stats=student_stats)


@bp.route('/<int:assignment_id>/makeup_grading')
@login_required
@require_teacher_or_admin
def makeup_grading(assignment_id):
    """补交评分页面 - 显示未提交作业的学生和已提交补交作业的学生"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 权限检查
    if not can_manage_assignment(current_user, assignment):
        flash('您没有权限查看此作业')
        return redirect(url_for('admin.teacher_dashboard' if current_user.is_teacher else 'admin.super_admin_dashboard'))
    
    # 如果没有班级，无法进行补交评分
    if not assignment.class_id:
        flash('此作业不属于任何班级，无法进行补交评分')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
    
    # 获取班级信息
    class_obj = Class.query.get(assignment.class_id)
    if not class_obj:
        flash('找不到相关班级')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
    
    # 获取所有已提交的学生ID（过滤掉补交提交）
    submitted_student_ids = set()
    submissions = Submission.query.filter_by(
        assignment_id=assignment_id,
        is_makeup=False
    ).all()
    for submission in submissions:
        if submission.student_id:
            submitted_student_ids.add(submission.student_id)
    
    # 获取已提交补交作业的学生（is_makeup=True）
    makeup_submissions = Submission.query.filter_by(
        assignment_id=assignment_id,
        is_makeup=True
    ).order_by(Submission.submitted_at.desc()).all()
    
    # 按学生分组
    makeup_student_submissions = defaultdict(list)
    makeup_submitted_student_ids = set()  # 记录已提交补交作业的学生ID
    for sub in makeup_submissions:
        if sub.student_id:
            makeup_student_submissions[sub.student_id].append(sub)
            makeup_submitted_student_ids.add(sub.student_id)  # 添加到集合中
    
    # 构建已提交补交作业的学生列表
    submitted_makeup_students = []
    for student_id, subs in makeup_student_submissions.items():
        latest_sub = subs[0]  # 最新的提交
        student = User.query.get(student_id)
        if student:
            # 获取评分
            grade_record = AssignmentGrade.query.filter_by(
                assignment_id=assignment_id,
                student_id=student_id
            ).first()
            
            submitted_makeup_students.append({
                'student_id': student.id,
                'student_name': student.real_name,
                'student_number': student.student_id or '未设置',
                'latest_submission': latest_sub,
                'submission_count': len(subs),
                'has_grade': grade_record is not None,
                'grade': grade_record.grade if grade_record else None,
                'feedback': grade_record.feedback if grade_record else None
            })
    
    # 按姓名排序
    submitted_makeup_students.sort(key=lambda x: x['student_name'])
    
    # 获取班级中所有学生
    all_students = User.query.filter(
        User.id.in_([s.id for s in class_obj.students]),
        User.role == UserRole.STUDENT
    ).all()
    
    # 筛选出未提交的学生（排除已提交补交作业的学生）
    unsubmitted_students = []
    for student in all_students:
        # 如果学生已提交正常作业或已提交补交作业，则跳过
        if student.id in submitted_student_ids or student.id in makeup_submitted_student_ids:
            continue
        
        # 检查是否已经有补交评分
        existing_grade = AssignmentGrade.query.filter_by(
            assignment_id=assignment_id,
            student_id=student.id
        ).first()
        
        unsubmitted_students.append({
            'student_id': student.id,
            'student_name': student.real_name,
            'student_number': student.student_id or '未设置',
            'has_grade': existing_grade is not None,
            'grade': existing_grade.grade if existing_grade else None,
            'is_makeup': existing_grade.is_makeup if existing_grade else False,
            'original_grade': existing_grade.original_grade if existing_grade and existing_grade.original_grade else None,
            'discount_rate': existing_grade.discount_rate if existing_grade and existing_grade.discount_rate else None
        })
    
    # 按姓名排序
    unsubmitted_students.sort(key=lambda x: x['student_name'])
    
    return render_template('makeup_grading.html', 
                         assignment=assignment, 
                         class_obj=class_obj,
                         unsubmitted_students=unsubmitted_students,
                         submitted_makeup_students=submitted_makeup_students)


@bp.route('/<int:assignment_id>/edit', methods=['GET', 'POST'])
@login_required
@require_teacher_or_admin
def edit_assignment(assignment_id):
    """编辑作业"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 权限检查
    if not can_manage_assignment(current_user, assignment):
        flash('您没有权限编辑此作业')
        return redirect(url_for('admin.teacher_dashboard' if current_user.is_teacher else 'admin.super_admin_dashboard'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '')
        due_date_str = request.form.get('due_date')
        file_types = request.form.get('file_types', '')
        max_size = request.form.get('max_size', '50')
        max_submissions = request.form.get('max_submissions', '0')
        class_id = request.form.get('class_id')
        
        # 处理附件上传
        if 'attachment' in request.files:
            attachment_file = request.files['attachment']
            if attachment_file and attachment_file.filename:
                # 删除旧附件
                if assignment.attachment_file_path:
                    FileService.delete_file(assignment.attachment_file_path)
                
                # 保存新附件
                attachment_filename, attachment_original_filename, attachment_file_path, attachment_file_size = \
                    FileService.save_assignment_attachment(attachment_file)
                
                assignment.attachment_filename = attachment_filename
                assignment.attachment_original_filename = attachment_original_filename
                assignment.attachment_file_path = attachment_file_path
                assignment.attachment_file_size = attachment_file_size
        
        # 检查是否需要删除附件
        if 'delete_attachment' in request.form and request.form['delete_attachment'] == 'on':
            if assignment.attachment_file_path:
                FileService.delete_file(assignment.attachment_file_path)
                assignment.attachment_filename = None
                assignment.attachment_original_filename = None
                assignment.attachment_file_path = None
                assignment.attachment_file_size = None
        
        # 验证班级权限
        if class_id:
            selected_class = Class.query.get(class_id)
            if not selected_class:
                flash('选择的班级不存在')
                return render_template('edit_assignment.html', assignment=assignment, available_classes=get_available_classes())
            
            if not current_user.is_super_admin and current_user not in selected_class.teachers:
                flash('您没有权限将作业分配到此班级')
                return render_template('edit_assignment.html', assignment=assignment, available_classes=get_available_classes())
        
        # 验证和处理数据
        try:
            max_size_mb = float(max_size)
            if max_size_mb < 1:
                flash('文件大小不能小于1MB')
                return render_template('edit_assignment.html', assignment=assignment, available_classes=get_available_classes())
            elif max_size_mb > 10240:
                flash('文件大小不能超过10GB (10240MB)')
                return render_template('edit_assignment.html', assignment=assignment, available_classes=get_available_classes())
            max_size_bytes = int(max_size_mb * 1024 * 1024)
        except (ValueError, TypeError):
            flash('文件大小限制必须是有效的数字')
            return render_template('edit_assignment.html', assignment=assignment, available_classes=get_available_classes())
        
        # 处理提交次数限制
        try:
            max_submissions_count = int(max_submissions)
            if max_submissions_count < 0:
                max_submissions_count = 0
        except (ValueError, TypeError):
            max_submissions_count = 0
        
        # 处理截止时间
        due_date = None
        if due_date_str:
            try:
                local_time = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
                due_date = local_time - timedelta(hours=8)
            except ValueError:
                flash('截止时间格式不正确')
                return render_template('edit_assignment.html', assignment=assignment, available_classes=get_available_classes())
        
        # 处理文件类型
        allowed_file_types = ''
        if file_types:
            file_types_list = []
            for ext in file_types.split(','):
                ext = ext.strip().lower()
                if ext.startswith('.'):
                    ext = ext[1:]
                if ext:
                    file_types_list.append(ext)
            allowed_file_types = ','.join(file_types_list)
        
        # 更新作业信息
        assignment.title = title
        assignment.description = description
        assignment.due_date = due_date
        assignment.allowed_file_types = allowed_file_types
        assignment.max_file_size = max_size_bytes
        assignment.max_submissions = max_submissions_count
        assignment.class_id = class_id if class_id else None
        
        db.session.commit()
        flash('作业信息已成功更新')
        
        if current_user.is_super_admin:
            return redirect(url_for('admin.super_admin_dashboard'))
        else:
            return redirect(url_for('admin.teacher_dashboard'))
    
    available_classes = get_available_classes()
    return render_template('edit_assignment.html', assignment=assignment, available_classes=available_classes)


@bp.route('/<int:assignment_id>/delete', methods=['POST'])
@login_required
@require_teacher_or_admin
def delete_assignment(assignment_id):
    """删除作业"""
    import os
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 权限检查
    if not can_manage_assignment(current_user, assignment):
        flash('您没有权限删除此作业')
        return redirect(url_for('admin.teacher_dashboard' if current_user.is_teacher else 'admin.super_admin_dashboard'))
    
    # 删除相关的提交文件
    for submission in assignment.submissions:
        try:
            if os.path.exists(submission.file_path):
                os.remove(submission.file_path)
        except Exception as e:
            print(f"删除文件失败: {e}")
    
    # 删除作业附件
    if assignment.attachment_file_path:
        FileService.delete_file(assignment.attachment_file_path)
    
    assignment_title = assignment.title
    db.session.delete(assignment)
    db.session.commit()
    
    flash(f'作业 "{assignment_title}" 及其所有提交已成功删除')
    
    if current_user.is_super_admin:
        return redirect(url_for('admin.super_admin_dashboard'))
    else:
        return redirect(url_for('admin.teacher_dashboard'))


def get_available_classes():
    """获取当前用户可用的班级列表"""
    if current_user.is_super_admin:
        return Class.query.filter_by(is_active=True).all()
    elif current_user.is_teacher:
        return current_user.teaching_classes
    else:
        return []


def can_manage_assignment(user, assignment):
    """检查用户是否能管理作业"""
    if user.is_super_admin:
        return True
    if user.is_teacher:
        # 教师可以管理自己创建的作业
        if assignment.teacher_id == user.id:
            return True
        # 教师可以管理自己负责班级的作业
        if assignment.class_id and assignment.class_info in user.teaching_classes:
            return True
    return False


def get_student_assignment_average_grade(assignment_id, student_id):
    """获取学生在某作业的平均分"""
    avg_grade = db.session.query(func.avg(AssignmentGrade.grade)).filter(
        AssignmentGrade.assignment_id == assignment_id,
        AssignmentGrade.student_id == student_id
    ).scalar()
    
    return round(avg_grade, 2) if avg_grade is not None else None

"""学生提交作业相关路由"""
import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Assignment, Submission, User, Class, UserRole
from app.utils import safe_chinese_filename, to_beijing_time, BEIJING_TZ
from app.utils.decorators import require_teacher_or_admin, require_role
from app.services import NotificationService
from app.services.log_service import LogService

bp = Blueprint('submission', __name__)


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


@bp.route('/submit/<int:assignment_id>', methods=['GET', 'POST'])
def submit_assignment(assignment_id):
    """学生提交作业（支持登录和非登录用户）"""
    from flask import current_app
    
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 如果用户已登录，优先使用登录用户信息
    logged_in_student = None
    has_valid_makeup = False
    current_app.logger.warning(f"[SUBMIT] 当前用户认证状态: {current_user.is_authenticated}")
    if current_user.is_authenticated:
        current_app.logger.warning(f"[SUBMIT] 用户角色: {current_user.role if hasattr(current_user, 'role') else 'unknown'}")
    
    if current_user.is_authenticated and current_user.is_student:
        logged_in_student = current_user
        current_app.logger.warning(f"[SUBMIT] 学生ID={logged_in_student.id} 开始检查补交申请")
        
        # 检查是否有已批准的补交申请，并且未过补交截止时间
        from app.models import MakeupRequest
        makeup_request = MakeupRequest.query.filter_by(
            student_id=logged_in_student.id,
            assignment_id=assignment_id,
            status='approved'
        ).order_by(MakeupRequest.id.desc()).first()  # 取最新的补交申请
        current_app.logger.warning(f"[SUBMIT] 查询补交申请结果: {makeup_request}")
        if makeup_request and makeup_request.deadline:
            current_app.logger.warning(f"[SUBMIT] 补交deadline={makeup_request.deadline} 当前={datetime.utcnow()}")
            # 检查补交截止时间是否过期
            if datetime.utcnow() <= makeup_request.deadline:
                has_valid_makeup = True
                current_app.logger.info(f"[SUBMIT] 学生ID={logged_in_student.id} 作业ID={assignment_id} 有有效补交申请")
            else:
                current_app.logger.info(f"[SUBMIT] 学生ID={logged_in_student.id} 作业ID={assignment_id} 补交申请已过期")
        else:
            current_app.logger.info(f"[SUBMIT] 没有找到有效的补交申请或deadline为空")
        
        # 检查学生是否有权限提交此作业
        if assignment.class_id:  # 如果作业指定了班级
            student_classes = [c.id for c in current_user.classes]
            if assignment.class_id not in student_classes:
                current_app.logger.warning(f"[SUBMIT] 学生ID={logged_in_student.id} 不在班级中")
                flash('很抱歉，您不在此作业的指定班级中，无法提交')
                return redirect(url_for('student.dashboard'))
    
    # 检查作业是否已过截止时间
    current_app.logger.info(f"[SUBMIT] 作业ID={assignment_id} is_overdue={assignment.is_overdue()} has_valid_makeup={has_valid_makeup}")
    if assignment.is_overdue():
        if has_valid_makeup:
            # 有有效的补交申请，可以继续提交
            current_app.logger.info(f"[SUBMIT] 作业已截止但有有效补交，允许提交")
            pass
        else:
            # 没有有效的补交申请
            current_app.logger.warning(f"[SUBMIT] 作业已截止且无有效补交，重定向")
            flash('未按规定提交，请重新申请补交')
            return redirect(url_for('student.dashboard') if logged_in_student else url_for('main.index'))
    
    if request.method == 'POST':
        # 再次检查作业是否已过截止时间（防止用户在提交过程中过期）
        if assignment.is_overdue() and not has_valid_makeup:
            if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                return jsonify({'success': False, 'message': '未按规定提交，请重新申请补交'}), 400
            flash('未按规定提交，请重新申请补交')
            return redirect(url_for('student.dashboard') if logged_in_student else url_for('main.index'))
        
        # 优先使用登录用户信息
        if logged_in_student:
            student_name = logged_in_student.real_name
            student_number = logged_in_student.student_id or logged_in_student.username
            student_user_id = logged_in_student.id
        else:
            student_name = request.form['student_name']
            student_number = request.form['student_id']
            student_user_id = None
        
        # 检查是否还能提交
        if logged_in_student and not assignment.can_student_submit(student_user_id):
            flash(f'您已达到该作业的最大提交次数限制 ({assignment.max_submissions}次)')
            return redirect(url_for('student.dashboard'))
        
        notes = request.form.get('notes', '')
        
        if 'file' not in request.files:
            if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                return jsonify({'success': False, 'message': '请选择文件'}), 400
            flash('请选择文件')
            return render_template('submit.html', assignment=assignment, logged_in_student=logged_in_student)
        
        file = request.files['file']
        if file.filename == '':
            if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                return jsonify({'success': False, 'message': '请选择文件'}), 400
            flash('请选择文件')
            return render_template('submit.html', assignment=assignment, logged_in_student=logged_in_student)
        
        # 检查文件类型（严格验证PDF、ZIP、DOC、DOCX、7Z、MD文件）
        if not assignment.is_file_allowed(file.filename):
            error_msg = '不允许的文件类型。系统仅支持PDF、ZIP、DOC、DOCX、7Z、MD文件。'
            if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                return jsonify({'success': False, 'message': error_msg}), 400
            flash(error_msg)
            return render_template('submit.html', assignment=assignment, logged_in_student=logged_in_student)
        
        # 额外的文件内容验证（确保文件确实是正确的格式）
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        if file_extension == 'pdf':
            # 检查PDF文件头
            file.seek(0)
            header = file.read(4)
            file.seek(0)
            if not header.startswith(b'%PDF'):
                error_msg = '文件不是有效的PDF格式。'
                if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                    return jsonify({'success': False, 'message': error_msg}), 400
                flash(error_msg)
                return render_template('submit.html', assignment=assignment, logged_in_student=logged_in_student)
        elif file_extension == 'zip':
            # 检查ZIP文件头
            file.seek(0)
            header = file.read(4)
            file.seek(0)
            if not header.startswith(b'PK\x03\x04'):
                error_msg = '文件不是有效的ZIP格式。'
                if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                    return jsonify({'success': False, 'message': error_msg}), 400
                flash(error_msg)
                return render_template('submit.html', assignment=assignment, logged_in_student=logged_in_student)
        elif file_extension in ['doc', 'docx']:
            # 检查DOC/DOCX文件头（Microsoft Office文档）
            file.seek(0)
            header = file.read(8)
            file.seek(0)
            # DOC格式 (OLE2): D0 CF 11 E0 A1 B1 1A E1
            # DOCX格式 (ZIP包装): PK\x03\x04
            if not (header.startswith(b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1') or header.startswith(b'PK\x03\x04')):
                error_msg = '文件不是有效的DOC/DOCX格式。'
                if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                    return jsonify({'success': False, 'message': error_msg}), 400
                flash(error_msg)
                return render_template('submit.html', assignment=assignment, logged_in_student=logged_in_student)
        elif file_extension == '7z':
            # 检查7Z文件头: 37 7A BC AF 27 1C
            file.seek(0)
            header = file.read(6)
            file.seek(0)
            if not header.startswith(b'7z\xBC\xAF\'\x1C'):
                error_msg = '文件不是有效的7Z格式。'
                if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                    return jsonify({'success': False, 'message': error_msg}), 400
                flash(error_msg)
                return render_template('submit.html', assignment=assignment, logged_in_student=logged_in_student)
        elif file_extension == 'md':
            # 检查MD文件（Markdown文本文件）- 验证是否为有效的UTF-8文本
            file.seek(0)
            try:
                content = file.read(1024)  # 读取前1KB内容
                file.seek(0)
                # 尝试解码为UTF-8
                content.decode('utf-8')
                # 可选：检查是否包含常见的Markdown语法标记
                # 这里只做基本的文本验证，不严格要求必须有Markdown语法
            except (UnicodeDecodeError, AttributeError):
                error_msg = '文件不是有效的Markdown文本格式。'
                if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                    return jsonify({'success': False, 'message': error_msg}), 400
                flash(error_msg)
                return render_template('submit.html', assignment=assignment, logged_in_student=logged_in_student)
        
        # 检查文件大小
        file.seek(0, 2)  # 移动到文件末尾
        file_size = file.tell()
        file.seek(0)  # 重置文件指针
        
        if file_size > assignment.max_file_size:
            max_size_mb = assignment.max_file_size / (1024 * 1024)
            error_msg = f'文件大小超出限制。最大允许：{max_size_mb:.1f}MB'
            if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                return jsonify({'success': False, 'message': error_msg}), 400
            flash(error_msg)
            return render_template('submit.html', assignment=assignment, logged_in_student=logged_in_student)
        
        if file:
            try:
                # 生成安全的文件名 - 学生作业提交重命名格式：姓名-提交时间（年月日时分秒）-uuid
                original_filename = file.filename
                # 使用北京时间生成时间戳
                beijing_now = datetime.now(BEIJING_TZ)
                timestamp = beijing_now.strftime("%Y%m%d%H%M%S")
                filename_uuid = str(uuid.uuid4())[:8]  # 使用较短的UUID
                
                # 处理学生姓名，确保文件名安全
                safe_student_name = safe_chinese_filename(student_name)
                filename = f"{safe_student_name}-{timestamp}-{filename_uuid}{os.path.splitext(original_filename)[1]}"
                
                # 创建特定格式的文件夹 - 作业序号-作业名称-作业创建时间
                class_name = "无班级"  # 默认值
                if assignment.class_info:
                    class_name = assignment.class_info.name
                
                # 清理文件名中的非法字符（保留中文）
                safe_assignment_title = safe_chinese_filename(assignment.title)
                # 使用北京时间格式化日期
                assignment_beijing_time = to_beijing_time(assignment.created_at)
                assignment_date = assignment_beijing_time.strftime("%Y%m%d")
                
                # 作业序号-作业名称-作业创建时间
                folder_name = f"{assignment.id}-{safe_assignment_title}-{assignment_date}"
                folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)
                os.makedirs(folder_path, exist_ok=True)
                
                # 保存文件到指定文件夹
                file_path = os.path.join(folder_path, filename)
                file.save(file_path)
                
                # 检查是否为补交作业（已批准的补交申请）
                is_makeup_submission = False
                if logged_in_student:
                    from app.models import MakeupRequest
                    makeup_request = MakeupRequest.query.filter_by(
                        student_id=logged_in_student.id,
                        assignment_id=assignment_id,
                        status='approved'
                    ).order_by(MakeupRequest.id.desc()).first()  # 取最新的补交申请
                    if makeup_request:
                        is_makeup_submission = True
                
                submission = Submission(
                    assignment_id=assignment_id,
                    student_id=student_user_id,
                    student_name=student_name,
                    student_number=student_number,
                    filename=filename,
                    original_filename=original_filename,
                    file_path=file_path,
                    file_size=file_size,
                    notes=notes,
                    is_makeup=is_makeup_submission
                )
                
                db.session.add(submission)
                db.session.commit()
                
                # 记录提交日志
                LogService.log_operation(
                    operation_type='submit',
                    operation_desc=f'学生 {student_name} ({student_number}) 提交作业「{assignment.title}」{"（补交）" if is_makeup_submission else ""}',
                    result='success'
                )
                
                # 根据请求类型返回不同响应
                if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                    # Ajax请求，返回JSON
                    return jsonify({
                        'success': True, 
                        'message': '作业提交成功',
                        'redirect_url': url_for('student.dashboard') if logged_in_student else url_for('main.index')
                    })
                else:
                    # 普通表单提交
                    flash('作业提交成功')
                    
                    # 根据用户状态重定向
                    if logged_in_student:
                        return redirect(url_for('student.dashboard'))
                    else:
                        return redirect(url_for('main.index'))
                        
            except Exception as e:
                db.session.rollback()
                error_msg = f'文件上传失败: {str(e)}'
                if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                    return jsonify({'success': False, 'message': error_msg}), 500
                flash(error_msg)
                return render_template('submit.html', assignment=assignment, logged_in_student=logged_in_student)
    
    # GET请求：显示提交页面和历史记录
    submission_history = []
    if logged_in_student:
        submission_history = Submission.query.filter_by(
            assignment_id=assignment_id, 
            student_id=logged_in_student.id
        ).order_by(Submission.submitted_at.desc()).all()
        
        # 为每个提交记录添加评分教师信息
        for submission in submission_history:
            if submission.graded_by:
                submission.grader = User.query.get(submission.graded_by)
            else:
                submission.grader = None
    
    return render_template('submit.html', 
                         assignment=assignment, 
                         logged_in_student=logged_in_student,
                         submission_history=submission_history)


@bp.route('/student/assignment/<int:assignment_id>/submissions')
@login_required
@require_role(UserRole.STUDENT)
def student_submission_history(assignment_id):
    """学生查看自己对某个作业的提交记录（无截止时间限制）"""
    from app.models.assignment import AssignmentGrade
    
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 检查学生是否有权限查看此作业
    if assignment.class_id:
        # 如果作业绑定了班级，检查学生是否在该班级中
        class_obj = Class.query.get(assignment.class_id)
        if current_user not in class_obj.students:
            flash('您没有权限查看此作业')
            return redirect(url_for('student.dashboard'))
    
    # 获取学生的所有提交记录，按提交时间降序排列
    submission_history = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=current_user.id
    ).order_by(Submission.submitted_at.desc()).all()
    
    # 为每个提交记录添加评分教师信息
    for submission in submission_history:
        if submission.graded_by:
            submission.grader = User.query.get(submission.graded_by)
        else:
            submission.grader = None
    
    # 获取教师评分情况（新的评分系统）
    teacher_grades = get_student_assignment_teacher_grades(assignment_id, current_user.id)
    
    # 计算平均分
    average_grade = get_student_assignment_average_grade(assignment_id, current_user.id)
    
    return render_template('student_submission_history.html', 
                         assignment=assignment, 
                         submission_history=submission_history,
                         teacher_grades=teacher_grades,
                         average_grade=average_grade)


@bp.route('/student/assignment/<int:assignment_id>/student/<int:student_id>/submissions')
@login_required
def student_submission_history_with_student_id(assignment_id, student_id):
    """通过学生 ID 查看提交记录（供教师使用）"""
    from app.models.assignment import AssignmentGrade
    
    assignment = Assignment.query.get_or_404(assignment_id)
    student = User.query.get_or_404(student_id)
    
    # 权限检查
    if current_user.is_student:
        # 学生只能查看自己的记录
        if current_user.id != student_id:
            flash('您没有权限查看其他学生的提交记录')
            return redirect(url_for('student.dashboard'))
    elif not (current_user.is_super_admin or current_user.is_teacher):
        flash('您没有权限查看此内容')
        return redirect(url_for('main.index'))
    
    # 获取学生的所有提交记录
    submission_history = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=student_id
    ).order_by(Submission.submitted_at.desc()).all()
    
    # 为每个提交记录添加评分教师信息
    for submission in submission_history:
        if submission.graded_by:
            submission.grader = User.query.get(submission.graded_by)
        else:
            submission.grader = None
    
    # 获取教师评分情况（新的评分系统）
    teacher_grades = get_student_assignment_teacher_grades(assignment_id, student_id)
    
    # 计算平均分
    average_grade = get_student_assignment_average_grade(assignment_id, student_id)
    
    return render_template('student_submission_history.html', 
                         assignment=assignment, 
                         submission_history=submission_history,
                         viewed_student=student,
                         teacher_grades=teacher_grades,
                         average_grade=average_grade)


@bp.route('/download/<int:submission_id>')
@login_required
def download_file(submission_id):
    """下载学生提交的作业文件"""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"download_file called: submission_id={submission_id}, user={current_user.username if current_user.is_authenticated else 'anonymous'}")
    
    submission = Submission.query.get_or_404(submission_id)
    assignment = Assignment.query.get(submission.assignment_id)
    
    logger.warning(f"Submission found: id={submission.id}, assignment_id={assignment.id}")
    logger.warning(f"Current user: username={current_user.username}, is_super_admin={current_user.is_super_admin}, is_teacher={current_user.is_teacher}")
    
    # 权限检查：教师/管理员可以下载所有文件，学生只能下载自己的文件
    can_download = False
    
    # 检查是否是教师或管理员
    if can_manage_assignment(current_user, assignment):
        can_download = True
        logger.warning("User can manage assignment - download allowed")
    # 检查是否是提交文件的学生本人
    elif current_user.is_student and submission.student_id == current_user.id:
        can_download = True
        logger.warning("User is the student who submitted - download allowed")
    else:
        logger.warning(f"Download NOT allowed: is_student={current_user.is_student}, submission.student_id={submission.student_id}, current_user.id={current_user.id}")
    
    if not can_download:
        logger.warning("Access denied - redirecting")
        flash('您没有权限下载此文件')
        if current_user.is_teacher:
            return redirect(url_for('admin.teacher_dashboard'))
        elif current_user.is_super_admin:
            return redirect(url_for('admin.super_admin_dashboard'))
        else:
            return redirect(url_for('student.dashboard'))
    
    logger.warning(f"Checking file existence: {submission.file_path}")
    # 路径处理：数据库中可能是相对路径(uploads/...)或绝对路径
    raw_path = submission.file_path or ''
    
    # 如果是相对路径且以uploads/开头，添加storage/前缀
    if not os.path.isabs(raw_path):
        if raw_path.startswith('uploads/'):
            file_path = os.path.join('storage', raw_path)
        else:
            file_path = raw_path
        file_path = os.path.abspath(file_path)
    else:
        # 绝对路径：宿主机路径需要映射为容器路径
        if raw_path.startswith('/root/TG-EDU-20251021/'):
            file_path = raw_path.replace('/root/TG-EDU-20251021/', '/app/', 1)
        else:
            file_path = raw_path
    
    if not os.path.exists(file_path):
        logger.warning(f"File NOT found: {file_path}")
        flash('文件不存在或已被删除')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment.id))
    
    logger.warning(f"File exists at: {file_path}")
    # 获取文件的目录和文件名（使用绝对路径）
    file_directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    logger.warning(f"File directory: {file_directory}, filename: {filename}")
    
    # 安全处理下载文件名，确保HTTP头兼容性
    try:
        # 尝试URL编码处理中文文件名
        from urllib.parse import quote
        safe_download_name = quote(submission.original_filename.encode('utf-8'))
        # 如果文件名过长或包含特殊字符，使用备用方案
        if len(safe_download_name) > 200:
            # 使用安全的文件名作为下载名
            file_ext = os.path.splitext(submission.original_filename)[1]
            safe_download_name = f"submission_{submission.id}{file_ext}"
        else:
            safe_download_name = submission.original_filename
    except Exception as e:
        logger.warning(f"Error encoding filename: {e}")
        # 出现任何编码问题时，使用备用文件名
        file_ext = os.path.splitext(submission.original_filename)[1]
        safe_download_name = f"submission_{submission.id}{file_ext}"
    
    logger.warning(f"Sending file: download_name={safe_download_name}")
    try:
        response = send_from_directory(
            file_directory,
            filename,
            as_attachment=True,
            download_name=safe_download_name
        )
        logger.warning(f"File sent successfully")
        
        # 记录下载日志
        LogService.log_operation(
            operation_type='download',
            operation_desc=f'下载作业提交文件：{submission.student_name} - {assignment.title}',
            result='success'
        )
        
        return response
    except Exception as e:
        logger.error(f"Error sending file: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash(f'文件下载失败: {str(e)}')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment.id))


@bp.route('/preview/<int:submission_id>')
@login_required
def preview_file(submission_id):
    """预览文件（主要用于PDF）"""
    import logging
    logger = logging.getLogger(__name__)
    
    submission = Submission.query.get_or_404(submission_id)
    assignment = Assignment.query.get(submission.assignment_id)
    
    # 权限检查：教师/管理员可以预览所有文件，学生只能预览自己的文件
    can_preview = False
    
    # 检查是否是教师或管理员
    if can_manage_assignment(current_user, assignment):
        can_preview = True
    # 检查是否是提交文件的学生本人
    elif current_user.is_student and submission.student_id == current_user.id:
        can_preview = True
    
    if not can_preview:
        flash('您没有权限预览此文件')
        if current_user.is_teacher:
            return redirect(url_for('admin.teacher_dashboard'))
        elif current_user.is_super_admin:
            return redirect(url_for('admin.super_admin_dashboard'))
        else:
            return redirect(url_for('student.dashboard'))
    
    # 路径处理：数据库中可能是相对路径(uploads/...)或绝对路径
    raw_path = submission.file_path or ''
    logger.warning(f"[PREVIEW] submission_id={submission_id}, raw_path={raw_path}")
    
    # 如果是相对路径且以uploads/开头，添加storage/前缀
    if not os.path.isabs(raw_path):
        if raw_path.startswith('uploads/'):
            file_path = os.path.join('storage', raw_path)
        else:
            file_path = raw_path
        file_path = os.path.abspath(file_path)
    else:
        # 绝对路径：宿主机路径需要映射为容器路径
        if raw_path.startswith('/root/TG-EDU-20251021/'):
            file_path = raw_path.replace('/root/TG-EDU-20251021/', '/app/', 1)
        else:
            file_path = raw_path
    
    logger.warning(f"[PREVIEW] processed file_path={file_path}, exists={os.path.exists(file_path)}")
    
    if not os.path.exists(file_path):
        logger.error(f"[PREVIEW] File NOT found: {file_path}")
        flash('文件不存在或已被删除')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment.id))
    
    # 获取文件的目录和文件名（使用绝对路径）
    file_directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    
    logger.warning(f"[PREVIEW] Sending file: dir={file_directory}, filename={filename}")
    
    # 如果是PDF文件，返回适合浏览器预览的格式
    if submission.is_pdf():
        try:
            response = send_from_directory(
                file_directory,
                filename,
                as_attachment=False,  # 不作为附件下载
                mimetype='application/pdf'
            )
            # 使用URL编码处理中文文件名，避免HTTP头编码错误
            from urllib.parse import quote
            try:
                safe_filename = quote(submission.original_filename.encode('utf-8'))
            except:
                safe_filename = quote(filename.encode('utf-8'))
            
            # 设置Content-Disposition为inline，确保浏览器预览
            response.headers['Content-Disposition'] = f'inline; filename="{safe_filename}"'
            logger.warning(f"[PREVIEW] PDF preview success")
            return response
        except Exception as e:
            logger.error(f"[PREVIEW] Error: {str(e)}")
            flash(f'预览失败: {str(e)}')
            return redirect(url_for('submission.download_file', submission_id=submission_id))
    else:
        # 非PDF文件仍然作为下载
        return redirect(url_for('submission.download_file', submission_id=submission_id))


@bp.route('/api/assignment/<int:assignment_id>/info')
def get_assignment_info(assignment_id):
    """获取作业的最新信息（用于实时更新截止时间）"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 统一时间格式，确保与前端完全一致
    due_date_utc = assignment.due_date.strftime('%Y-%m-%d %H:%M:%S') if assignment.due_date else None
    due_date_beijing = to_beijing_time(assignment.due_date).strftime('%Y-%m-%d %H:%M:%S') if assignment.due_date else None
    
    response_data = {
        'id': assignment.id,
        'title': assignment.title,
        'due_date': due_date_utc,  # UTC时间格式
        'due_date_beijing': due_date_beijing,  # 北京时间格式
        'is_overdue': assignment.is_overdue(),
        'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')  # 添加最后更新时间
    }
    
    return jsonify(response_data)


@bp.route('/admin/submission/<int:submission_id>/delete', methods=['POST'])
@login_required
@require_teacher_or_admin
def delete_submission(submission_id):
    """删除学生提交的作业（教师/管理员功能）"""
    submission = Submission.query.get_or_404(submission_id)
    assignment = Assignment.query.get(submission.assignment_id)
    
    # 权限检查
    if not can_manage_assignment(current_user, assignment):
        flash('您没有权限删除此提交')
        return redirect(url_for('admin.teacher_dashboard' if current_user.is_teacher else 'admin.super_admin_dashboard'))
    
    # 删除文件
    if os.path.exists(submission.file_path):
        try:
            os.remove(submission.file_path)
        except Exception as e:
            flash(f'删除文件失败: {str(e)}')
    
    # 删除数据库记录
    db.session.delete(submission)
    db.session.commit()
    
    flash('提交记录已成功删除')
    return redirect(url_for('assignment.view_submissions', assignment_id=assignment.id))


# 辅助函数

def get_student_assignment_average_grade(assignment_id, student_id):
    """获取学生作业的平均分（所有评分教师包括超级管理员的平均分）"""
    from app.models.assignment import AssignmentGrade
    
    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        return None
    
    # 获取该作业的所有评分教师（包括超级管理员）
    teacher_ids = []
    
    if assignment.class_id:
        class_obj = Class.query.get(assignment.class_id)
        if class_obj:
            # 班级的所有授课教师
            teacher_ids.extend([t.id for t in class_obj.teachers])
    
    # 添加作业创建者（如果不在授课教师列表中）
    if assignment.teacher_id not in teacher_ids:
        teacher_ids.append(assignment.teacher_id)
    
    # 添加所有超级管理员
    super_admins = User.query.filter_by(role=UserRole.SUPER_ADMIN).all()
    for admin in super_admins:
        if admin.id not in teacher_ids:
            teacher_ids.append(admin.id)
    
    # 获取所有评分教师（包括超级管理员）的评分
    grades = AssignmentGrade.query.filter(
        AssignmentGrade.assignment_id == assignment_id,
        AssignmentGrade.student_id == student_id,
        AssignmentGrade.teacher_id.in_(teacher_ids),
        AssignmentGrade.grade.isnot(None)
    ).all()
    
    if not grades:
        return None
    
    # 计算平均分：所有评分教师的分数总和除以教师数量
    total_grade = sum(grade.grade for grade in grades)
    return round(total_grade / len(grades), 2)


def get_student_assignment_teacher_grades(assignment_id, student_id):
    """获取学生作业的所有教师评分记录"""
    from app.models.assignment import AssignmentGrade
    
    return AssignmentGrade.query.filter(
        AssignmentGrade.assignment_id == assignment_id,
        AssignmentGrade.student_id == student_id
    ).join(User, AssignmentGrade.teacher_id == User.id).all()

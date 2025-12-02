"""批量下载相关路由"""
import os
import time
import zipfile
from io import BytesIO
from flask import Blueprint, request, redirect, url_for, flash, send_file, jsonify, session
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Assignment, Submission, Class
from app.utils import safe_chinese_filename, to_beijing_time
from app.utils.decorators import require_teacher_or_admin
from app.utils.progress_tracker import progress_tracker  # 导入进度跟踪器

bp = Blueprint('download', __name__, url_prefix='/admin')


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


@bp.route('/assignment/<int:assignment_id>/download_status')
@login_required
@require_teacher_or_admin
def download_assignment_status(assignment_id):
    """获取下载进度"""
    import logging
    logger = logging.getLogger(__name__)
    
    # 使用进度跟踪器获取进度（支持多worker环境）
    progress_key = f'assignment_{assignment_id}'
    progress = progress_tracker.get_progress(current_user.id, progress_key)
    
    logger.warning(f"[单个作业下载] 查询进度: 作业ID={assignment_id}, 用户ID={current_user.id}, 进度={progress.get('progress')}%, 状态={progress.get('status')}")
    
    return jsonify(progress)


@bp.route('/assignment/<int:assignment_id>/download')
@login_required
@require_teacher_or_admin
def download_assignment(assignment_id):
    """下载指定作业的所有提交文件"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 权限检查
    if not can_manage_assignment(current_user, assignment):
        flash('您没有权限下载此作业')
        return redirect(url_for('admin.teacher_dashboard' if current_user.is_teacher else 'admin.super_admin_dashboard'))
    
    # 获取作业的所有提交记录
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
    
    if not submissions:
        flash('该作业没有任何提交记录')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
    
    import logging
    logger = logging.getLogger(__name__)
    
    logger.warning(f"[单个作业下载] ===== 开始下载单个作业 =====")
    logger.warning(f"[单个作业下载] 用户ID: {current_user.id}, 用户名: {current_user.username}")
    logger.warning(f"[单个作业下载] 作业ID: {assignment_id}, 作业标题: {assignment.title}")
    logger.warning(f"[单个作业下载] 提交数: {len(submissions)}")
    
    # 进度跟踪键
    progress_key = f'assignment_{assignment_id}'
    
    # 初始化进度（使用进度跟踪器）
    progress_tracker.set_progress(current_user.id, {
        'status': 'processing',
        'progress': 0,
        'message': '正在检查文件...',
        'total_files': len(submissions)
    }, progress_key)
    
    # 创建内存ZIP文件
    memory_file = BytesIO()
    
    try:
        # 使用最高压缩级别
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            processed_files = 0
            # 统计存在的文件数
            existing_files = []
            for s in submissions:
                if os.path.isabs(s.file_path):
                    # 已经是绝对路径，直接使用
                    file_path = s.file_path
                else:
                    # 相对路径，需要转换为绝对路径
                    # 检查是否已经包含storage前缀
                    if s.file_path.startswith('storage/'):
                        # 已包含storage前缀，直接加/app前缀
                        file_path = os.path.join('/app', s.file_path)
                    else:
                        # 不包含storage前缀，加/app/storage前缀
                        file_path = os.path.join('/app/storage', s.file_path)
                
                logger.warning(f"[单个作业下载] 检查文件: {s.student_name} - {s.original_filename}")
                logger.warning(f"[单个作业下载] 原始路径: {s.file_path}")
                logger.warning(f"[单个作业下载] 转换路径: {file_path}")
                logger.warning(f"[单个作业下载] 文件存在: {os.path.exists(file_path)}")
                
                if os.path.exists(file_path):
                    existing_files.append((s, file_path))
                else:
                    logger.warning(f"[单个作业下载] 文件不存在，跳过: {file_path}")
            
            total_files = len(existing_files)
            logger.warning(f"[单个作业下载] 实际存在的文件数: {total_files}/{len(submissions)}")
            
            for i, (submission, file_path) in enumerate(existing_files):
                    # 更新进度（使用进度跟踪器）
                    progress_percent = int((processed_files / total_files) * 100) if total_files > 0 else 0
                    progress_tracker.set_progress(current_user.id, {
                        'status': 'processing',
                        'progress': progress_percent,
                        'message': f'正在压缩文件: {submission.original_filename}',
                        'current_file': processed_files + 1,
                        'total_files': total_files
                    }, progress_key)
                    
                    logger.warning(f"[单个作业下载] 处理文件 {processed_files + 1}/{total_files}: {submission.original_filename}")
                    
                    # 创建文件在ZIP中的路径：学生姓名_学号_提交时间_原文件名
                    beijing_time = to_beijing_time(submission.submitted_at)
                    time_str = beijing_time.strftime('%Y%m%d_%H%M%S') if beijing_time else 'unknown'
                    
                    safe_student_name = safe_chinese_filename(submission.student_name)
                    safe_original_name = safe_chinese_filename(submission.original_filename)
                    
                    zip_filename = f"{safe_student_name}_{submission.student_number}_{time_str}_{safe_original_name}"
                    
                    # 添加文件到ZIP（使用完整路径）
                    zf.write(file_path, zip_filename)
                    processed_files += 1
                    
                    # 模拟小延迟，让进度条更可见（仅在文件少时）
                    if total_files < 10:
                        time.sleep(0.1)
        
        # 完成压缩
        logger.warning(f"[单个作业下载] 压缩完成，共处理 {total_files} 个文件")
        
        progress_tracker.set_progress(current_user.id, {
            'status': 'completed',
            'progress': 100,
            'message': '压缩完成，准备下载...',
            'total_files': total_files
        }, progress_key)
        
        memory_file.seek(0)
        
        # 生成ZIP文件名：班级-作业标题-作业创建时间.zip
        beijing_created = to_beijing_time(assignment.created_at)
        created_time_str = beijing_created.strftime('%Y%m%d%H%M%S') if beijing_created else 'unknown'
        
        if assignment.class_info:
            class_name = safe_chinese_filename(assignment.class_info.name)
        else:
            class_name = '公共作业'
        
        safe_title = safe_chinese_filename(assignment.title)
        zip_filename = f"{class_name}-{safe_title}-{created_time_str}.zip"
        
        # 不立即清理进度记录，让前端有时间读取到completed状态
        logger.warning(f"[单个作业下载] 开始下载文件: {zip_filename}")
        # progress_tracker.clear_progress(current_user.id, progress_key)  # 不在这里清理，由超时机制自动清理
        
        return send_file(
            memory_file,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        # 错误处理
        logger.error(f"[单个作业下载] 下载失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        progress_tracker.set_progress(current_user.id, {
            'status': 'error',
            'progress': 0,
            'message': f'压缩失败: {str(e)}'
        }, progress_key)
        
        flash(f'下载失败: {str(e)}')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))


@bp.route('/assignment/<int:assignment_id>/attachment')
@login_required
def download_assignment_attachment(assignment_id):
    """下载作业附件（教师和学生都可以访问）"""
    from flask import send_from_directory
    import logging
    
    logger = logging.getLogger(__name__)
    assignment = Assignment.query.get_or_404(assignment_id)
    
    logger.warning(f"download_assignment_attachment called: assignment_id={assignment_id}, user={current_user.username}")
    logger.warning(f"attachment_file_path: {assignment.attachment_file_path}")
    logger.warning(f"attachment_filename: {assignment.attachment_filename}")
    logger.warning(f"attachment_original_filename: {assignment.attachment_original_filename}")
    
    # 权限检查：教师可以下载所有作业附件，学生只能下载自己班级的作业附件
    can_download = False
    
    if can_manage_assignment(current_user, assignment):
        # 教师或管理员可以下载
        can_download = True
    elif current_user.is_student:
        # 学生权限检查：如果作业指定了班级，检查学生是否在该班级中
        if assignment.class_id:
            class_obj = Class.query.get(assignment.class_id)
            if class_obj and current_user in class_obj.students:
                can_download = True
        else:
            # 公共作业，所有学生都可以下载
            can_download = True
    
    if not can_download:
        logger.warning("Permission denied")
        flash('您没有权限下载此作业附件')
        if current_user.is_teacher:
            return redirect(url_for('admin.teacher_dashboard'))
        elif current_user.is_super_admin:
            return redirect(url_for('admin.super_admin_dashboard'))
        else:
            return redirect(url_for('student.dashboard'))
    
    # 检查是否有附件
    if not assignment.attachment_file_path:
        logger.warning("No attachment_file_path set")
        flash('附件不存在')
        if current_user.is_student:
            return redirect(url_for('student.dashboard'))
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
    
    # 转换为绝对路径（如果是相对路径）
    file_path = os.path.abspath(assignment.attachment_file_path) if not os.path.isabs(assignment.attachment_file_path) else assignment.attachment_file_path
    logger.warning(f"Absolute path: {file_path}")
    
    # 兼容旧路径：如果文件不存在，尝试修正路径（/app/appendix/ -> /app/storage/appendix/）
    if not os.path.exists(file_path):
        logger.warning(f"File NOT found at: {file_path}")
        
        # 尝试路径修正：/app/appendix/ -> /app/storage/appendix/
        if '/app/appendix/' in file_path:
            corrected_path = file_path.replace('/app/appendix/', '/app/storage/appendix/')
            logger.warning(f"Trying corrected path: {corrected_path}")
            
            if os.path.exists(corrected_path):
                logger.warning(f"File found at corrected path!")
                file_path = corrected_path
            else:
                logger.warning(f"File NOT found at corrected path either")
                # 列出目录内容帮助调试
                appendix_dir = '/app/storage/appendix'
                if os.path.exists(appendix_dir):
                    files = os.listdir(appendix_dir)
                    logger.warning(f"Files in {appendix_dir}: {files[:10]}")
                flash('附件不存在')
                if current_user.is_student:
                    return redirect(url_for('student.dashboard'))
                return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
        else:
            logger.warning(f"Path does not contain '/app/appendix/', cannot auto-correct")
            flash('附件不存在')
            if current_user.is_student:
                return redirect(url_for('student.dashboard'))
            return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
    else:
        logger.warning(f"File exists at: {file_path}")
    
    # 获取文件的目录和文件名（使用绝对路径）
    file_directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    
    logger.warning(f"Sending attachment: directory={file_directory}, filename={filename}, download_name={assignment.attachment_original_filename}")
    
    try:
        response = send_from_directory(
            file_directory,
            filename,
            as_attachment=True,
            download_name=assignment.attachment_original_filename
        )
        logger.warning("Attachment sent successfully")
        return response
    except Exception as e:
        logger.error(f"Error sending attachment: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash(f'附件下载失败: {str(e)}')
        if current_user.is_student:
            return redirect(url_for('student.dashboard'))
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))


@bp.route('/assignments/batch_download_status')
@login_required
@require_teacher_or_admin
def batch_download_status():
    """获取批量下载进度"""
    import logging
    logger = logging.getLogger(__name__)
    
    # 使用进度跟踪器从文件系统读取进度
    progress = progress_tracker.get_progress(current_user.id)
    
    logger.warning(f"[批量下载进度] 用户ID: {current_user.id}, 状态: {progress.get('status')}, 进度: {progress.get('progress')}%, 消息: {progress.get('message')}")
    
    return jsonify(progress)


@bp.route('/assignments/batch_download_clear', methods=['POST'])
@login_required
@require_teacher_or_admin
def clear_batch_download_progress():
    """清理批量下载进度记录"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.warning(f"[批量下载] 用户 {current_user.id} 请求清理进度记录")
    
    # 清理进度文件
    progress_tracker.clear_progress(current_user.id)
    
    # 同时清理ZIP数据（仍然存储在session中）
    zip_key = f'batch_download_zip_{current_user.id}'
    filename_key = f'batch_download_filename_{current_user.id}'
    if zip_key in session:
        session.pop(zip_key)
    if filename_key in session:
        session.pop(filename_key)
    
    return jsonify({'success': True, 'message': '进度记录已清理'})


@bp.route('/assignments/batch_download_file')
@login_required
@require_teacher_or_admin
def download_batch_file():
    """下载批量打包的ZIP文件"""
    zip_key = f'batch_download_zip_{current_user.id}'
    filename_key = f'batch_download_filename_{current_user.id}'
    
    if zip_key not in session or filename_key not in session:
        flash('批量下载文件不存在或已过期')
        return redirect(url_for('download.batch_download_assignments'))
    
    # 从 session 中获取 ZIP 数据
    import base64
    zip_data_b64 = session[zip_key]
    zip_filename = session[filename_key]
    
    # 解码
    zip_data = base64.b64decode(zip_data_b64)
    
    # 创建 BytesIO 对象
    from io import BytesIO
    memory_file = BytesIO(zip_data)
    memory_file.seek(0)
    
    # 清理 session 中的数据
    session.pop(zip_key)
    session.pop(filename_key)
    
    return send_file(
        memory_file,
        as_attachment=True,
        download_name=zip_filename,
        mimetype='application/zip'
    )


@bp.route('/assignment/<int:assignment_id>/download_makeup_submissions')
@login_required
@require_teacher_or_admin
def download_makeup_submissions(assignment_id):
    """下载指定作业的所有补交提交文件"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 权限检查
    if not can_manage_assignment(current_user, assignment):
        flash('您没有权限下载此作业的补交提交')
        return redirect(url_for('admin.teacher_dashboard' if current_user.is_teacher else 'admin.super_admin_dashboard'))
    
    # 获取作业的所有补交提交记录（is_makeup=True）
    makeup_submissions = Submission.query.filter_by(
        assignment_id=assignment_id,
        is_makeup=True
    ).order_by(Submission.submitted_at.desc()).all()
    
    if not makeup_submissions:
        flash('该作业没有任何补交提交记录')
        return redirect(url_for('assignment.makeup_grading', assignment_id=assignment_id))
    
    import logging
    logger = logging.getLogger(__name__)
    
    logger.warning(f"[补交下载] ===== 开始下载补交作业 =====")
    logger.warning(f"[补交下载] 用户ID: {current_user.id}, 用户名: {current_user.username}")
    logger.warning(f"[补交下载] 作业ID: {assignment_id}, 作业标题: {assignment.title}")
    logger.warning(f"[补交下载] 补交提交数: {len(makeup_submissions)}")
    
    # 创建内存ZIP文件
    memory_file = BytesIO()
    
    try:
        # 使用最高压缩级别
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            processed_files = 0
            # 统计存在的文件数
            existing_files = []
            for s in makeup_submissions:
                if os.path.isabs(s.file_path):
                    file_path = s.file_path
                else:
                    if s.file_path.startswith('storage/'):
                        file_path = os.path.join('/app', s.file_path)
                    else:
                        file_path = os.path.join('/app/storage', s.file_path)
                
                logger.warning(f"[补交下载] 检查文件: {s.student_name} - {s.original_filename}")
                logger.warning(f"[补交下载] 原始路径: {s.file_path}")
                logger.warning(f"[补交下载] 转换路径: {file_path}")
                logger.warning(f"[补交下载] 文件存在: {os.path.exists(file_path)}")
                
                if os.path.exists(file_path):
                    existing_files.append((s, file_path))
                else:
                    logger.warning(f"[补交下载] 文件不存在，跳过: {file_path}")
            
            total_files = len(existing_files)
            logger.warning(f"[补交下载] 实际存在的文件数: {total_files}/{len(makeup_submissions)}")
            
            for i, (submission, file_path) in enumerate(existing_files):
                logger.warning(f"[补交下载] 处理文件 {processed_files + 1}/{total_files}: {submission.original_filename}")
                
                # 创建文件在ZIP中的路径：学生姓名_学号_提交时间_原文件名
                beijing_time = to_beijing_time(submission.submitted_at)
                time_str = beijing_time.strftime('%Y%m%d_%H%M%S') if beijing_time else 'unknown'
                
                safe_student_name = safe_chinese_filename(submission.student_name)
                safe_original_name = safe_chinese_filename(submission.original_filename)
                
                zip_filename = f"{safe_student_name}_{submission.student_number}_{time_str}_{safe_original_name}"
                
                # 添加文件到ZIP（使用完整路径）
                zf.write(file_path, zip_filename)
                processed_files += 1
        
        # 完成压缩
        logger.warning(f"[补交下载] 压缩完成，共处理 {total_files} 个文件")
        
        memory_file.seek(0)
        
        # 生成ZIP文件名：班级-作业标题-补交作业-时间.zip
        beijing_created = to_beijing_time(assignment.created_at)
        created_time_str = beijing_created.strftime('%Y%m%d%H%M%S') if beijing_created else 'unknown'
        
        if assignment.class_info:
            class_name = safe_chinese_filename(assignment.class_info.name)
        else:
            class_name = '公共作业'
        
        safe_title = safe_chinese_filename(assignment.title)
        zip_filename = f"{class_name}-{safe_title}-补交作业-{created_time_str}.zip"
        
        logger.warning(f"[补交下载] 开始下载文件: {zip_filename}")
        
        return send_file(
            memory_file,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        # 错误处理
        logger.error(f"[补交下载] 下载失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        flash(f'下载失败: {str(e)}')
        return redirect(url_for('assignment.makeup_grading', assignment_id=assignment_id))


@bp.route('/assignments/batch_download', methods=['GET', 'POST'])
@login_required
@require_teacher_or_admin
def batch_download_assignments():
    """批量下载作业"""
    from datetime import datetime
    from flask import render_template
    
    if request.method == 'GET':
        # 显示批量下载选择页面
        if current_user.is_super_admin:
            classes = Class.query.order_by(Class.name).all()
            assignments = Assignment.query.order_by(Assignment.created_at.desc()).all()
        else:
            # 教师只能看到自己的班级和作业
            classes = current_user.teaching_classes
            own_assignments = Assignment.query.filter_by(teacher_id=current_user.id).all()
            class_assignments = []
            if classes:
                class_ids = [c.id for c in classes]
                class_assignments = Assignment.query.filter(
                    Assignment.class_id.in_(class_ids),
                    Assignment.teacher_id != current_user.id
                ).all()
            assignments = own_assignments + class_assignments
        
        return render_template('batch_download.html', classes=classes, assignments=assignments)
    
    # POST请求：执行批量下载
    download_type = request.form.get('download_type')
    
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"[批量下载] ===== 开始批量下载 =====")
    logger.warning(f"[批量下载] 用户ID: {current_user.id}, 用户名: {current_user.username}")
    logger.warning(f"[批量下载] 下载类型: {download_type}")
    
    # 初始化进度（使用进度跟踪器）
    logger.warning(f"[批量下载] 初始化进度为 10%")
    progress_tracker.set_progress(current_user.id, {
        'status': 'processing',
        'progress': 10,
        'message': '正在检查作业...',
        'total_assignments': 0,
        'current_assignment': 0
    })
    
    if download_type == 'all':
        # 下载所有作业
        if current_user.is_super_admin:
            assignments = Assignment.query.all()
        else:
            # 教师只能下载自己的作业
            own_assignments = Assignment.query.filter_by(teacher_id=current_user.id).all()
            class_assignments = []
            teacher_classes = current_user.teaching_classes
            if teacher_classes:
                class_ids = [c.id for c in teacher_classes]
                class_assignments = Assignment.query.filter(
                    Assignment.class_id.in_(class_ids),
                    Assignment.teacher_id != current_user.id
                ).all()
            assignments = own_assignments + class_assignments
        
        zip_filename = f'所有作业-{datetime.now().strftime("%Y%m%d%H%M%S")}.zip'
        
    elif download_type == 'class':
        # 下载指定班级的所有作业
        class_id = request.form.get('class_id')
        if not class_id:
            flash('请选择班级')
            return redirect(url_for('download.batch_download_assignments'))
        
        class_obj = Class.query.get_or_404(class_id)
        
        # 权限检查
        if not current_user.is_super_admin and current_user not in class_obj.teachers:
            flash('您没有权限下载此班级的作业')
            return redirect(url_for('download.batch_download_assignments'))
        
        assignments = Assignment.query.filter_by(class_id=class_id).all()
        safe_class_name = safe_chinese_filename(class_obj.name)
        zip_filename = f'{safe_class_name}-所有作业-{datetime.now().strftime("%Y%m%d%H%M%S")}.zip'
        
    else:
        flash('无效的下载类型')
        return redirect(url_for('download.batch_download_assignments'))
    
    if not assignments:
        logger.warning(f"[批量下载] 错误：没有找到任何作业")
        progress_tracker.set_progress(current_user.id, {
            'status': 'error',
            'progress': 0,
            'message': '没有找到任何作业'
        })
        flash('没有找到任何作业')
        return redirect(url_for('download.batch_download_assignments'))
    
    logger.warning(f"[批量下载] 找到 {len(assignments)} 个作业")
    
    # 创建内存ZIP文件
    memory_file = BytesIO()
    
    try:
        logger.warning(f"[批量下载] 开始创建ZIP文件")
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for assignment_index, assignment in enumerate(assignments):
                # 更新当前作业进度
                assignment_progress = int((assignment_index / len(assignments)) * 100)
                logger.warning(f"[批量下载] 处理作业 {assignment_index + 1}/{len(assignments)}: {assignment.title}, 进度: {assignment_progress}%")
                
                progress_tracker.set_progress(current_user.id, {
                    'status': 'processing',
                    'progress': assignment_progress,
                    'message': f'正在处理作业: {assignment.title}',
                    'current_assignment': assignment_index + 1,
                    'total_assignments': len(assignments)
                })
                
                submissions = Submission.query.filter_by(assignment_id=assignment.id).all()
                logger.warning(f"[批量下载] 作业 '{assignment.title}' 有 {len(submissions)} 个提交")
                
                if submissions:
                    # 为每个作业创建文件夹
                    beijing_created = to_beijing_time(assignment.created_at)
                    created_time_str = beijing_created.strftime('%Y%m%d%H%M%S') if beijing_created else 'unknown'
                    
                    if assignment.class_info:
                        class_name = safe_chinese_filename(assignment.class_info.name)
                    else:
                        class_name = '公共作业'
                    
                    safe_title = safe_chinese_filename(assignment.title)
                    assignment_folder = f"{class_name}-{safe_title}-{created_time_str}"
                    
                    for submission_index, submission in enumerate(submissions):
                        # 构建完整的文件路径
                        if os.path.isabs(submission.file_path):
                            file_path = submission.file_path
                        else:
                            # 相对路径，需要拼接storage前缀
                            file_path = os.path.join('/app/storage', submission.file_path)
                        
                        if os.path.exists(file_path):
                            # 更新文件进度
                            file_progress = int(((assignment_index + (submission_index / len(submissions))) / len(assignments)) * 100)
                            
                            if submission_index == 0:  # 只记录每个作业的第一个文件
                                logger.warning(f"[批量下载] 开始压缩作业 '{assignment.title}' 的文件, 进度: {file_progress}%")
                            
                            progress_tracker.set_progress(current_user.id, {
                                'status': 'processing',
                                'progress': file_progress,
                                'message': f'正在压缩: {submission.original_filename}',
                                'current_assignment': assignment_index + 1,
                                'total_assignments': len(assignments),
                                'current_file': submission_index + 1,
                                'total_files': len(submissions)
                            })
                            
                            # 创建文件在ZIP中的路径
                            beijing_time = to_beijing_time(submission.submitted_at)
                            time_str = beijing_time.strftime('%Y%m%d_%H%M%S') if beijing_time else 'unknown'
                            
                            safe_student_name = safe_chinese_filename(submission.student_name)
                            safe_original_name = safe_chinese_filename(submission.original_filename)
                            
                            zip_filename_in_folder = f"{assignment_folder}/{safe_student_name}_{submission.student_number}_{time_str}_{safe_original_name}"
                            
                            # 添加文件到ZIP（使用完整路径）
                            zf.write(file_path, zip_filename_in_folder)
                            
                            # 小延迟，让进度更可见
                            time.sleep(0.01)
        
        # 完成压缩
        memory_file.seek(0)
        zip_data = memory_file.read()
        
        logger.warning(f"[批量下载] ZIP文件创建完成，大小: {len(zip_data) / 1024 / 1024:.2f} MB")
        
        # 将ZIP数据保存到session中（用base64编码）
        import base64
        logger.warning(f"[批量下载] 将ZIP数据保存到session")
        session[f'batch_download_zip_{current_user.id}'] = base64.b64encode(zip_data).decode('utf-8')
        session[f'batch_download_filename_{current_user.id}'] = zip_filename
        
        logger.warning(f"[批量下载] 设置进度为完成状态 (100%)")
        progress_tracker.set_progress(current_user.id, {
            'status': 'completed',
            'progress': 100,
            'message': '所有作业压缩完成，准备下载...',
            'total_assignments': len(assignments),
            'download_ready': True
        })
        
        logger.warning(f"[批量下载] ===== 批量下载处理完成 =====")
        # 返回成功响应而不是文件
        return jsonify({'success': True, 'message': '批量下载准备完成'})
        
    except Exception as e:
        # 错误处理
        import traceback
        error_detail = traceback.format_exc()
        
        logger.error(f"[批量下载] ===== 发生错误 =====")
        logger.error(f"[批量下载] 错误信息: {str(e)}")
        logger.error(f"[批量下载] 详细堆栈:\n{error_detail}")
        
        progress_tracker.set_progress(current_user.id, {
            'status': 'error',
            'progress': 0,
            'message': f'批量下载失败: {str(e)}'
        })
        flash(f'批量下载失败: {str(e)}')
        # 记录详细错误到日志
        import logging
        logging.error(f"批量下载失败: {error_detail}")
        return redirect(url_for('download.batch_download_assignments'))

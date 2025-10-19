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
    progress_key = f'download_progress_{assignment_id}_{current_user.id}'
    progress = session.get(progress_key, {'status': 'pending', 'progress': 0, 'message': '准备中...'})
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
    
    # 进度跟踪键
    progress_key = f'download_progress_{assignment_id}_{current_user.id}'
    
    # 初始化进度
    session[progress_key] = {
        'status': 'processing',
        'progress': 0,
        'message': '正在检查文件...',
        'total_files': len(submissions)
    }
    session.permanent = True
    
    # 创建内存ZIP文件
    memory_file = BytesIO()
    
    try:
        # 使用最高压缩级别
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            processed_files = 0
            total_files = len([s for s in submissions if os.path.exists(s.file_path)])
            
            for i, submission in enumerate(submissions):
                if os.path.exists(submission.file_path):
                    # 更新进度
                    progress_percent = int((processed_files / total_files) * 100) if total_files > 0 else 0
                    session[progress_key] = {
                        'status': 'processing',
                        'progress': progress_percent,
                        'message': f'正在压缩文件: {submission.original_filename}',
                        'current_file': processed_files + 1,
                        'total_files': total_files
                    }
                    
                    # 创建文件在ZIP中的路径：学生姓名_学号_提交时间_原文件名
                    beijing_time = to_beijing_time(submission.submitted_at)
                    time_str = beijing_time.strftime('%Y%m%d_%H%M%S') if beijing_time else 'unknown'
                    
                    safe_student_name = safe_chinese_filename(submission.student_name)
                    safe_original_name = safe_chinese_filename(submission.original_filename)
                    
                    zip_filename = f"{safe_student_name}_{submission.student_number}_{time_str}_{safe_original_name}"
                    
                    # 添加文件到ZIP
                    zf.write(submission.file_path, zip_filename)
                    processed_files += 1
                    
                    # 模拟小延迟，让进度条更可见（仅在文件少时）
                    if total_files < 10:
                        time.sleep(0.1)
        
        # 完成压缩
        session[progress_key] = {
            'status': 'completed',
            'progress': 100,
            'message': '压缩完成，准备下载...',
            'total_files': total_files
        }
        
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
        
        # 清理进度记录
        if progress_key in session:
            session.pop(progress_key)
        
        return send_file(
            memory_file,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        # 错误处理
        session[progress_key] = {
            'status': 'error',
            'progress': 0,
            'message': f'压缩失败: {str(e)}'
        }
        flash(f'下载失败: {str(e)}')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))


@bp.route('/assignment/<int:assignment_id>/attachment')
@login_required
@require_teacher_or_admin
def download_assignment_attachment(assignment_id):
    """下载作业附件"""
    from flask import send_from_directory
    
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 权限检查
    if not can_manage_assignment(current_user, assignment):
        flash('您没有权限下载此作业附件')
        return redirect(url_for('admin.teacher_dashboard' if current_user.is_teacher else 'admin.super_admin_dashboard'))
    
    # 检查是否有附件
    if not assignment.attachment_file_path or not os.path.exists(assignment.attachment_file_path):
        flash('附件不存在')
        return redirect(url_for('assignment.view_submissions', assignment_id=assignment_id))
    
    # 获取文件的目录和文件名
    file_directory = os.path.dirname(assignment.attachment_file_path)
    filename = os.path.basename(assignment.attachment_file_path)
    
    return send_from_directory(
        file_directory,
        filename,
        as_attachment=True,
        download_name=assignment.attachment_original_filename
    )


@bp.route('/assignments/batch_download_status')
@login_required
@require_teacher_or_admin
def batch_download_status():
    """获取批量下载进度"""
    progress_key = f'batch_download_progress_{current_user.id}'
    progress = session.get(progress_key, {'status': 'pending', 'progress': 0, 'message': '准备中...'})
    
    # 检查是否有启动时间，用于超时检测
    if 'start_time' in progress:
        elapsed_time = time.time() - progress['start_time']
        # 如果超过5分钟没有进度更新，认为下载已完成或失败
        if elapsed_time > 300 and progress.get('status') not in ['completed', 'error']:
            progress = {
                'status': 'completed',
                'progress': 100,
                'message': '下载已完成（检测到超时，可能已自动下载）',
                'timeout': True
            }
    
    return jsonify(progress)


@bp.route('/assignments/batch_download_start', methods=['POST'])
@login_required
@require_teacher_or_admin
def start_batch_download():
    """启动批量下载进程"""
    download_type = request.form.get('download_type')
    class_id = request.form.get('class_id')
    
    # 进度跟踪键
    progress_key = f'batch_download_progress_{current_user.id}'
    
    # 初始化进度
    session[progress_key] = {
        'status': 'started',
        'progress': 5,
        'message': '正在检查作业...',
        'download_type': download_type,
        'class_id': class_id,
        'start_time': time.time()  # 记录启动时间
    }
    session.permanent = True
    
    return jsonify({'success': True, 'message': '批量下载已启动'})


@bp.route('/assignments/batch_download_clear', methods=['POST'])
@login_required
@require_teacher_or_admin
def clear_batch_download_progress():
    """清理批量下载进度记录"""
    progress_key = f'batch_download_progress_{current_user.id}'
    
    if progress_key in session:
        session.pop(progress_key)
    
    return jsonify({'success': True, 'message': '进度记录已清理'})

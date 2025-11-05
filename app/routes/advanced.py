"""高级功能路由（系统重置等）"""
import os
import shutil
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user, logout_user, login_user

from app.extensions import db
from app.models import User, Class, Assignment, Submission, UserRole
from app.models.assignment import AssignmentGrade

bp = Blueprint('advanced', __name__, url_prefix='/admin')


@bp.route('/reset-system', methods=['GET', 'POST'])
@login_required
def reset_system():
    """系统重置功能（仅超级管理员）"""
    # 只有超级管理员可以重置系统
    if not current_user.is_super_admin:
        flash('您没有权限访问此功能')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        reset_type = request.form.get('reset_type')
        confirm_password = request.form.get('confirm_password')
        
        # 验证管理员密码
        if not current_user.check_password(confirm_password):
            flash('密码验证失败，重置操作已取消')
            return render_template('reset_system.html')
        
        try:
            if reset_type == 'assignments':
                # 清除作业数据
                try:
                    # 清空上传文件夹中的所有文件，但不删除文件夹本身
                    if os.path.exists(current_app.config['UPLOAD_FOLDER']):
                        for filename in os.listdir(current_app.config['UPLOAD_FOLDER']):
                            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                            try:
                                if os.path.isfile(file_path) or os.path.islink(file_path):
                                    os.unlink(file_path)
                                elif os.path.isdir(file_path):
                                    shutil.rmtree(file_path)
                            except Exception as e:
                                current_app.logger.error(f'删除文件失败 {file_path}: {str(e)}')
                    
                    # 删除数据库中的相关记录（按正确顺序删除以避免外键约束问题）
                    # 1. 先删除作业评分记录
                    AssignmentGrade.query.delete()
                    db.session.commit()
                    
                    # 2. 再删除提交记录
                    Submission.query.delete()
                    db.session.commit()
                    
                    # 3. 最后删除作业
                    Assignment.query.delete()
                    db.session.commit()
                    
                    flash('作业数据已清除完成，所有作业、提交记录和评分记录已删除')
                except Exception as e:
                    db.session.rollback()
                    flash(f'清除作业数据失败: {str(e)}')
                    current_app.logger.error(f'清除作业数据失败: {str(e)}')
                
            elif reset_type == 'users':
                # 清除人员数据（保留超级管理员）
                admin_id = current_user.id
                
                # 删除非超级管理员用户相关的数据（按正确顺序删除以避免外键约束问题）
                
                # 1. 先删除作业评分记录（删除所有非超级管理员相关的评分）
                AssignmentGrade.query.filter(
                    AssignmentGrade.student_id != admin_id
                ).delete()
                AssignmentGrade.query.filter(
                    AssignmentGrade.teacher_id != admin_id
                ).delete()
                db.session.commit()
                
                # 2. 删除非超级管理员用户创建的提交记录
                submissions_to_delete = Submission.query.filter(
                    Submission.student_id != admin_id
                ).all()
                
                # 删除对应的文件
                for submission in submissions_to_delete:
                    try:
                        if os.path.exists(submission.file_path):
                            os.remove(submission.file_path)
                    except Exception as e:
                        current_app.logger.error(f"删除文件失败: {e}")
                
                # 删除提交记录
                for submission in submissions_to_delete:
                    db.session.delete(submission)
                db.session.commit()
                
                # 3. 删除非超级管理员的作业
                Assignment.query.filter(Assignment.teacher_id != admin_id).delete()
                db.session.commit()
                
                # 4. 删除班级（清除班级关联表）
                Class.query.delete()
                db.session.commit()
                
                # 5. 删除非超级管理员用户
                User.query.filter(
                    User.id != admin_id,
                    User.role != UserRole.SUPER_ADMIN
                ).delete()
                db.session.commit()
                
                flash('人员数据已清除完成，所有非超级管理员用户及其相关数据已删除')
                
            elif reset_type == 'all':
                # 重置所有数据
                # 清空上传文件夹中的所有文件，但不删除文件夹本身
                if os.path.exists(current_app.config['UPLOAD_FOLDER']):
                    for filename in os.listdir(current_app.config['UPLOAD_FOLDER']):
                        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                        try:
                            if os.path.isfile(file_path) or os.path.islink(file_path):
                                os.unlink(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                        except Exception as e:
                            current_app.logger.error(f'删除文件失败 {file_path}: {str(e)}')
                
                # 保存当前超级管理员信息
                admin_username = current_user.username
                admin_real_name = current_user.real_name
                admin_password_hash = current_user.password_hash
                
                # 按正确顺序删除所有数据以避免外键约束问题
                # 1. 先删除作业评分记录
                AssignmentGrade.query.delete()
                db.session.commit()
                
                # 2. 再删除提交记录
                Submission.query.delete()
                db.session.commit()
                
                # 3. 删除作业
                Assignment.query.delete()
                db.session.commit()
                
                # 4. 删除班级（包括班级关联表class_student和class_teacher）
                Class.query.delete()
                db.session.commit()
                
                # 5. 删除通知
                from app.models import Notification
                Notification.query.delete()
                db.session.commit()
                
                # 6. 最后删除用户
                User.query.delete()
                db.session.commit()
                
                # 重新创建超级管理员
                admin = User(
                    username=admin_username,
                    real_name=admin_real_name,
                    role=UserRole.SUPER_ADMIN
                )
                admin.password_hash = admin_password_hash
                db.session.add(admin)
                
                db.session.commit()
                
                # 重新登录
                logout_user()
                login_user(admin)
                
                flash('系统已完全重置，所有数据已清除并重新初始化')
            
            else:
                flash('无效的重置类型')
                
        except Exception as e:
            db.session.rollback()
            flash(f'重置操作失败: {str(e)}')
            current_app.logger.error(f'重置操作失败: {str(e)}')
        
        return redirect(url_for('admin.super_admin_dashboard'))
    
    return render_template('reset_system.html')

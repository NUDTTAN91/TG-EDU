"""通知相关路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Notification, User, Class, UserRole
from app.utils.decorators import require_teacher_or_admin
from app.services import NotificationService

bp = Blueprint('notification', __name__)


@bp.route('/notifications')
@login_required
def notifications():
    """通知列表页面"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # 获取用户的所有通知，按时间降序
    pagination = Notification.query.filter_by(receiver_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    notifications_list = pagination.items
    
    return render_template('notifications.html', 
                         notifications=notifications_list,
                         pagination=pagination)


@bp.route('/notifications/unread')
@login_required
def unread_notifications():
    """未读通知列表"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    pagination = Notification.query.filter_by(
        receiver_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    notifications_list = pagination.items
    
    return render_template('notifications.html', 
                         notifications=notifications_list,
                         pagination=pagination,
                         show_unread_only=True)


@bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """标记通知为已读"""
    notification = Notification.query.get_or_404(notification_id)
    
    # 权限检查
    if notification.receiver_id != current_user.id:
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    NotificationService.mark_as_read(notification_id)
    
    return jsonify({
        'success': True, 
        'unread_count': NotificationService.get_unread_count(current_user.id)
    })


@bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """标记所有通知为已读"""
    NotificationService.mark_all_as_read(current_user.id)
    flash('所有通知已标记为已读')
    return redirect(url_for('notification.notifications'))


@bp.route('/notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_notification(notification_id):
    """删除通知"""
    notification = Notification.query.get_or_404(notification_id)
    
    # 权限检查
    if notification.receiver_id != current_user.id:
        flash('无权删除此通知')
        return redirect(url_for('notification.notifications'))
    
    db.session.delete(notification)
    db.session.commit()
    
    flash('通知已删除')
    return redirect(url_for('notification.notifications'))


@bp.route('/notifications/create', methods=['GET', 'POST'])
@login_required
@require_teacher_or_admin
def create_notification_page():
    """创建通知页面"""
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        notification_type = request.form.get('notification_type', 'system')
        target_type = request.form.get('target_type')  # all/role/class/individual
        
        receivers = []
        
        if current_user.is_super_admin:
            # 超级管理员可以选择不同的目标
            if target_type == 'all':
                # 通知所有用户
                receivers = User.query.filter_by(is_active=True).all()
            elif target_type == 'role':
                # 通知指定角色
                role = request.form.get('target_role')
                receivers = User.query.filter_by(role=role, is_active=True).all()
            elif target_type == 'individual':
                # 通知指定个人
                user_id = request.form.get('target_user_id')
                user = User.query.get(user_id)
                if user and user.is_active:
                    receivers = [user]
        else:
            # 教师只能通知自己管理的班级
            if target_type == 'class':
                class_id = request.form.get('target_class_id')
                class_obj = Class.query.get(class_id)
                
                # 权限检查
                if class_obj and current_user in class_obj.teachers:
                    receivers = class_obj.students
                else:
                    flash('您没有权限向此班级发送通知')
                    return redirect(url_for('notification.create_notification_page'))
        
        # 创建通知
        if receivers:
            for receiver in receivers:
                NotificationService.create_notification(
                    sender_id=current_user.id,
                    receiver_id=receiver.id,
                    title=title,
                    content=content,
                    notification_type=notification_type
                )
            
            flash(f'通知已发送给 {len(receivers)} 个用户')
            return redirect(url_for('notification.notifications'))
        else:
            flash('没有找到目标用户')
    
    # GET请求：显示创建表单
    available_classes = []
    all_users = []
    
    if current_user.is_super_admin:
        all_users = User.query.filter_by(is_active=True).order_by(User.real_name).all()
    else:
        # 教师只能看到自己的班级
        available_classes = current_user.teaching_classes
    
    return render_template('create_notification.html', 
                         available_classes=available_classes,
                         all_users=all_users)


@bp.route('/api/notifications/count')
@login_required
def get_notification_count():
    """获取未读通知数量（API）"""
    unread_count = NotificationService.get_unread_count(current_user.id)
    return jsonify({'unread_count': unread_count})

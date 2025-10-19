"""通知服务"""
from app.extensions import db
from app.models import Notification


class NotificationService:
    """通知服务类"""
    
    @staticmethod
    def create_notification(sender_id, receiver_id, title, content,
                          notification_type='system',
                          related_assignment_id=None,
                          related_submission_id=None):
        """创建通知"""
        notification = Notification(
            title=title,
            content=content,
            notification_type=notification_type,
            sender_id=sender_id,
            receiver_id=receiver_id,
            related_assignment_id=related_assignment_id,
            related_submission_id=related_submission_id
        )
        db.session.add(notification)
        db.session.commit()
        return notification
    
    @staticmethod
    def get_unread_count(user_id):
        """获取用户未读通知数量"""
        return Notification.query.filter_by(
            receiver_id=user_id,
            is_read=False
        ).count()
    
    @staticmethod
    def mark_as_read(notification_id):
        """标记通知为已读"""
        notification = Notification.query.get(notification_id)
        if notification:
            notification.is_read = True
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def mark_all_as_read(user_id):
        """标记用户所有通知为已读"""
        Notification.query.filter_by(
            receiver_id=user_id,
            is_read=False
        ).update({'is_read': True})
        db.session.commit()

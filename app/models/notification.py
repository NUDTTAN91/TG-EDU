"""通知相关模型"""
from datetime import datetime
from app.extensions import db


class Notification(db.Model):
    """系统通知模型"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    related_assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'))
    related_submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'))
    
    # 关系
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_notifications')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_notifications')
    related_assignment = db.relationship('Assignment', foreign_keys=[related_assignment_id])
    related_submission = db.relationship('Submission', foreign_keys=[related_submission_id])
    
    def get_team_invitation(self):
        """获取关联的团队邀请（通过发送者和接收者匹配）"""
        if self.notification_type != 'team_invitation':
            return None
        
        from app.models.team import TeamInvitation
        # 查找发送者是sender、接收者是receiver的邀请
        invitation = TeamInvitation.query.filter_by(
            inviter_id=self.sender_id,
            invitee_id=self.receiver_id
        ).order_by(TeamInvitation.created_at.desc()).first()
        
        return invitation
    
    def __repr__(self):
        return f'<Notification {self.title}>'

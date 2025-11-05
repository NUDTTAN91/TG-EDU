"""
补交申请模型
"""
from app import db
from datetime import datetime


class MakeupRequest(db.Model):
    """补交申请表"""
    __tablename__ = 'makeup_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)  # 申请理由
    status = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    deadline = db.Column(db.DateTime)  # 补交截止时间
    reject_reason = db.Column(db.Text)  # 拒绝理由
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # 审批人
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 使用property方法获取关联对象（避免relationship定义问题）
    @property
    def student(self):
        """获取学生对象"""
        from app.models.user import User
        return db.session.get(User, self.student_id)
    
    @property
    def assignment(self):
        """获取作业对象"""
        from app.models.assignment import Assignment
        return db.session.get(Assignment, self.assignment_id)
    
    @property
    def approver(self):
        """获取审批人对象"""
        if self.approved_by:
            from app.models.user import User
            return db.session.get(User, self.approved_by)
        return None

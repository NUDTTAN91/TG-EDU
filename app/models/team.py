"""团队相关模型"""
from datetime import datetime
from app.extensions import db


class MajorAssignment(db.Model):
    """大作业模型"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    requirement_file_path = db.Column(db.String(500))
    requirement_file_name = db.Column(db.String(255))
    requirement_url = db.Column(db.String(500))
    due_date = db.Column(db.DateTime)
    min_team_size = db.Column(db.Integer, default=2)
    max_team_size = db.Column(db.Integer, default=5)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # 关系
    teacher = db.relationship('User', backref='major_assignments')
    class_info = db.relationship('Class', backref='major_assignments')
    
    def __repr__(self):
        return f'<MajorAssignment {self.title}>'


class Team(db.Model):
    """团队模型"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    major_assignment_id = db.Column(db.Integer, db.ForeignKey('major_assignment.id'), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(50), default='pending')
    size_exception_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # 关系
    leader = db.relationship('User', foreign_keys=[leader_id], backref='led_teams')
    confirmer = db.relationship('User', foreign_keys=[confirmed_by])
    major_assignment = db.relationship('MajorAssignment', backref='teams')
    
    def get_member_count(self):
        """获取团队成员数量（包括组长）"""
        return len(self.members) + 1
    
    def is_size_valid(self):
        """检查团队人数是否符合要求"""
        count = self.get_member_count()
        assignment = self.major_assignment
        return assignment.min_team_size <= count <= assignment.max_team_size
    
    def __repr__(self):
        return f'<Team {self.name}>'


class TeamMember(db.Model):
    """团队成员模型"""
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关系
    user = db.relationship('User', backref='team_memberships')
    team = db.relationship('Team', backref='members')
    
    __table_args__ = (db.UniqueConstraint('team_id', 'user_id', name='unique_team_member'),)
    
    def __repr__(self):
        return f'<TeamMember User{self.user_id} in Team{self.team_id}>'


class TeamInvitation(db.Model):
    """团队邀请模型"""
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    inviter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    invitee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)
    
    # 关系
    team = db.relationship('Team', backref='invitations')
    inviter = db.relationship('User', foreign_keys=[inviter_id], backref='sent_team_invitations')
    invitee = db.relationship('User', foreign_keys=[invitee_id], backref='received_team_invitations')
    
    def __repr__(self):
        return f'<TeamInvitation Team{self.team_id}>'


class LeaveTeamRequest(db.Model):
    """退组请求模型"""
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='pending_leader')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    leader_responded_at = db.Column(db.DateTime)
    teacher_responded_at = db.Column(db.DateTime)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    review_comment = db.Column(db.Text)
    
    # 关系
    team = db.relationship('Team', backref='leave_requests')
    member = db.relationship('User', foreign_keys=[member_id], backref='leave_requests')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])
    
    def __repr__(self):
        return f'<LeaveTeamRequest Team{self.team_id}>'

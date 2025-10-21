"""团队相关模型"""
from datetime import datetime
from app.extensions import db


# 大作业-教师关联表（多对多）
major_assignment_teachers = db.Table('major_assignment_teachers',
    db.Column('major_assignment_id', db.Integer, db.ForeignKey('major_assignment.id'), primary_key=True),
    db.Column('teacher_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)


class MajorAssignment(db.Model):
    """大作业模型"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    requirement_file_path = db.Column(db.String(500))  # 保留旧字段兼容
    requirement_file_name = db.Column(db.String(255))  # 保留旧字段兼容
    requirement_url = db.Column(db.String(500))  # 保留旧字段兼容
    start_date = db.Column(db.DateTime)  # 开始日期
    end_date = db.Column(db.DateTime)    # 结束日期
    min_team_size = db.Column(db.Integer, default=2)
    max_team_size = db.Column(db.Integer, default=5)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 创建者
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # 关系
    creator = db.relationship('User', foreign_keys=[creator_id], backref='created_major_assignments')
    teachers = db.relationship('User', secondary=major_assignment_teachers, 
                              backref=db.backref('managed_major_assignments', lazy='dynamic'))
    class_info = db.relationship('Class', backref='major_assignments')
    
    def can_manage(self, user):
        """检查用户是否可以管理此大作业"""
        if user.is_super_admin:
            return True
        if user.id == self.creator_id:
            return True
        if user in self.teachers:
            return True
        return False
    
    def get_all_attachments(self):
        """获取所有附件（包括新旧系统）"""
        attachments = list(self.attachments)  # 新系统的附件
        # 兼容旧系统：如果有旧的单个附件，也加入列表
        if self.requirement_file_path and self.requirement_file_name:
            # 检查是否已经在新系统中
            old_file_exists = any(att.file_path == self.requirement_file_path for att in attachments)
            if not old_file_exists:
                # 创建一个临时对象来表示旧附件
                class OldAttachment:
                    def __init__(self, file_path, file_name):
                        self.file_path = file_path
                        self.original_filename = file_name
                        self.file_type = 'file'
                        self.is_old = True
                attachments.insert(0, OldAttachment(self.requirement_file_path, self.requirement_file_name))
        return attachments
    
    def get_all_links(self):
        """获取所有链接（包括新旧系统）"""
        links = list(self.links)  # 新系统的链接
        # 兼容旧系统：如果有旧的单个链接，也加入列表
        if self.requirement_url:
            # 检查是否已经在新系统中
            old_link_exists = any(link.url == self.requirement_url for link in links)
            if not old_link_exists:
                # 创建一个临时对象来表示旧链接
                class OldLink:
                    def __init__(self, url):
                        self.url = url
                        self.title = '要求链接'
                        self.is_old = True
                links.insert(0, OldLink(self.requirement_url))
        return links
    
    def __repr__(self):
        return f'<MajorAssignment {self.title}>'


class Team(db.Model):
    """团队模型"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    major_assignment_id = db.Column(db.Integer, db.ForeignKey('major_assignment.id'), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending/confirmed/rejected
    size_exception_reason = db.Column(db.Text)
    confirmation_request_reason = db.Column(db.Text)  # 请求确认时的理由（人数不符合时必填）
    reject_reason = db.Column(db.Text)  # 拒绝理由
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime)  # 老师确认时间
    confirmed_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # 确认人
    confirmation_requested_at = db.Column(db.DateTime)  # 新增：组长请求确认时间
    is_locked = db.Column(db.Boolean, default=False)  # 新增：是否锁定（确认后锁定）
    
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


class DissolveTeamRequest(db.Model):
    """解散团队请求模型"""
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    review_comment = db.Column(db.Text)
    
    # 关系
    team = db.relationship('Team', backref='dissolve_requests')
    leader = db.relationship('User', foreign_keys=[leader_id], backref='dissolve_requests')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])
    
    def __repr__(self):
        return f'<DissolveTeamRequest Team{self.team_id}>'


class Stage(db.Model):
    """阶段模型"""
    id = db.Column(db.Integer, primary_key=True)
    major_assignment_id = db.Column(db.Integer, db.ForeignKey('major_assignment.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    stage_type = db.Column(db.String(50), nullable=False)  # team_formation/division/custom
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    order = db.Column(db.Integer, default=0)  # 阶段顺序
    status = db.Column(db.String(50), default='pending')  # pending/active/completed
    is_locked = db.Column(db.Boolean, default=False)  # 是否锁定
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关系
    major_assignment = db.relationship('MajorAssignment', backref='stages')
    
    def get_team_divisions(self, team_id):
        """获取某个团队在该阶段的所有分工（支持自由定义格式）"""
        from app.models.team import TeamDivision
        from sqlalchemy import func
        
        # 查询该团队在该阶段的分工，按角色名称分组
        divisions_query = db.session.query(
            TeamDivision.role_name,
            TeamDivision.role_description,
            func.group_concat(TeamDivision.member_id).label('member_ids')
        ).filter_by(
            team_id=team_id,
            stage_id=self.id
        ).group_by(
            TeamDivision.role_name,
            TeamDivision.role_description
        ).all()
        
        # 构建返回数据
        divisions = []
        for div in divisions_query:
            # 解析成员ID列表
            member_ids = [int(mid) for mid in div.member_ids.split(',')] if div.member_ids else []
            
            # 获取成员对象
            from app.models import User
            members = User.query.filter(User.id.in_(member_ids)).all() if member_ids else []
            
            divisions.append({
                'role_name': div.role_name,
                'role_description': div.role_description,
                'members': members,
                'member_count': len(members)
            })
        
        return divisions
    
    def __repr__(self):
        return f'<Stage {self.name}>'


class DivisionRole(db.Model):
    """分工角色模型"""
    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey('stage.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_required = db.Column(db.Boolean, default=True)  # 是否必须
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关系
    stage = db.relationship('Stage', backref='division_roles')
    
    def __repr__(self):
        return f'<DivisionRole {self.name}>'


class TeamDivision(db.Model):
    """团队分工模型（支持自由定义角色）"""
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    stage_id = db.Column(db.Integer, db.ForeignKey('stage.id'))  # 关联阶段
    division_role_id = db.Column(db.Integer, db.ForeignKey('division_role.id'))  # 旧方式，可选
    role_name = db.Column(db.String(100))  # 自由定义的角色名称
    role_description = db.Column(db.Text)  # 自由定义的角色描述
    member_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # 可以为空（未分配）
    assigned_at = db.Column(db.DateTime)
    assigned_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # 分配人
    
    # 关系
    team = db.relationship('Team', backref='divisions')
    stage = db.relationship('Stage', backref='team_divisions')
    division_role = db.relationship('DivisionRole', backref='team_divisions')
    member = db.relationship('User', foreign_keys=[member_id], backref='division_assignments')
    assigner = db.relationship('User', foreign_keys=[assigned_by])
    
    def __repr__(self):
        return f'<TeamDivision Team{self.team_id} Role{self.role_name or self.division_role_id}>'


class TeamTask(db.Model):
    """团队任务模型"""
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    stage_id = db.Column(db.Integer, db.ForeignKey('stage.id'), nullable=True)  # 可为空，不再依赖阶段
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))  # 分配给谁（可选，可分配给多人）
    priority = db.Column(db.String(20), default='medium')  # low/medium/high
    status = db.Column(db.String(50), default='pending')  # pending/in_progress/completed
    progress = db.Column(db.Integer, default=0)  # 进度百分比 0-100
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # 关系
    team = db.relationship('Team', backref='tasks')
    stage = db.relationship('Stage', backref='tasks')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_tasks')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_tasks')
    
    def __repr__(self):
        return f'<TeamTask {self.title}>'


class TaskProgress(db.Model):
    """任务进度记录模型"""
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('team_task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    progress = db.Column(db.Integer, nullable=False)  # 进度百分比 0-100
    status = db.Column(db.String(50))  # pending/in_progress/completed
    comment = db.Column(db.Text)  # 进度说明
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关系
    task = db.relationship('TeamTask', backref='progress_records')
    user = db.relationship('User', backref='task_progress_records')
    
    def __repr__(self):
        return f'<TaskProgress Task{self.task_id} {self.progress}%>'


class MajorAssignmentAttachment(db.Model):
    """大作业附件模型（支持多个附件）"""
    id = db.Column(db.Integer, primary_key=True)
    major_assignment_id = db.Column(db.Integer, db.ForeignKey('major_assignment.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(50), default='file')  # file 类型
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # 关系
    major_assignment = db.relationship('MajorAssignment', backref='attachments')
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    
    def __repr__(self):
        return f'<MajorAssignmentAttachment {self.original_filename}>'


class MajorAssignmentLink(db.Model):
    """大作业链接模型（支持多个链接）"""
    id = db.Column(db.Integer, primary_key=True)
    major_assignment_id = db.Column(db.Integer, db.ForeignKey('major_assignment.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(200))  # 链接标题
    description = db.Column(db.Text)  # 链接描述
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # 关系
    major_assignment = db.relationship('MajorAssignment', backref='links')
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<MajorAssignmentLink {self.title or self.url}>'

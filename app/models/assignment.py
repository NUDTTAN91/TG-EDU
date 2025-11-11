"""作业相关模型"""
from datetime import datetime
from app.extensions import db


class Assignment(db.Model):
    """作业模型"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    allowed_file_types = db.Column(db.Text)
    max_file_size = db.Column(db.Integer, default=50*1024*1024)
    max_submissions = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'))
    is_active = db.Column(db.Boolean, default=True)
    
    # 附件相关字段
    attachment_filename = db.Column(db.String(255))
    attachment_original_filename = db.Column(db.String(255))
    attachment_file_path = db.Column(db.String(500))
    attachment_file_size = db.Column(db.Integer)
    
    # 关系
    teacher = db.relationship('User', backref='assignments')
    class_info = db.relationship('Class', backref='assignments')
    
    def get_allowed_extensions(self):
        """获取允许的文件扩展名列表"""
        if self.allowed_file_types:
            return [ext.strip().lower() for ext in self.allowed_file_types.split(',')]
        return ['pdf', 'doc', 'docx', 'txt', 'zip', 'rar']
    
    def is_file_allowed(self, filename):
        """检查文件类型是否允许"""
        if '.' not in filename:
            return False
        ext = filename.rsplit('.', 1)[1].lower()
        return ext in self.get_allowed_extensions()
    
    def is_overdue(self):
        """检查是否已过截止时间"""
        if not self.due_date:
            return False
        return datetime.utcnow() > self.due_date
    
    def get_student_submission_count(self, student_id):
        """获取学生提交次数"""
        from app.models.submission import Submission
        return Submission.query.filter_by(assignment_id=self.id, student_id=student_id).count()
    
    def can_student_submit(self, student_id):
        """检查学生是否还能提交作业"""
        if self.max_submissions <= 0:
            return True
        return self.get_student_submission_count(student_id) < self.max_submissions
    
    def __repr__(self):
        return f'<Assignment {self.title}>'


class AssignmentGrade(db.Model):
    """作业评分模型"""
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    grade = db.Column(db.Float)
    feedback = db.Column(db.Text)
    graded_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 补交相关字段
    is_makeup = db.Column(db.Boolean, default=False)  # 是否补交
    discount_rate = db.Column(db.Float)  # 折扣百分比（0-100）
    original_grade = db.Column(db.Float)  # 原始分数（折扣前）
    
    # 作弊标记
    is_cheating = db.Column(db.Boolean, default=False)  # 是否作弊/抄袭
    
    # 关系
    assignment = db.relationship('Assignment', backref='assignment_grades')
    student = db.relationship('User', foreign_keys=[student_id], backref='received_grades')
    teacher = db.relationship('User', foreign_keys=[teacher_id], backref='given_grades')
    
    __table_args__ = (
        db.UniqueConstraint('assignment_id', 'student_id', 'teacher_id', 
                          name='unique_assignment_student_teacher_grade'),
    )

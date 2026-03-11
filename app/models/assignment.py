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
    max_file_size = db.Column(db.Integer, default=5*1024*1024)  # 默认5MB
    max_submissions = db.Column(db.Integer, default=3)  # 默认3次
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'))
    is_active = db.Column(db.Boolean, default=True)
    
    # 附件相关字段
    attachment_filename = db.Column(db.String(255))
    attachment_original_filename = db.Column(db.String(255))
    attachment_file_path = db.Column(db.String(500))
    attachment_file_size = db.Column(db.Integer)
    
    # AI 评分相关字段
    grading_criteria = db.Column(db.Text)  # 评分标准（用于 AI 自动评分）
    
    # AI 自动改卷模式
    # 0 = 不启用 AI 自动改卷
    # 1 = 学生提交立刻自动改卷（需要立刻上传参考答案）
    # 2 = 学生提交自动改卷（稍后上传参考答案再自动进行批改）
    # 3 = 自动改卷自动判分，不需要参考答案
    ai_grading_mode = db.Column(db.Integer, default=0)
    
    # 参考答案相关字段
    reference_answer = db.Column(db.Text)  # 参考答案文本内容
    reference_answer_filename = db.Column(db.String(255))  # 参考答案文件名
    reference_answer_original_filename = db.Column(db.String(255))  # 参考答案原始文件名
    reference_answer_file_path = db.Column(db.String(500))  # 参考答案文件路径
    reference_answer_file_size = db.Column(db.Integer)  # 参考答案文件大小
    
    # 关系
    teacher = db.relationship('User', backref='assignments')
    class_info = db.relationship('Class', backref='assignments')
    
    def get_allowed_extensions(self):
        """获取允许的文件扩展名列表"""
        if self.allowed_file_types:
            # 允许pdf、zip、doc、docx、7z、md文件类型
            allowed_types = [ext.strip().lower() for ext in self.allowed_file_types.split(',')]
            # 过滤只保留支持的类型
            return [ext for ext in allowed_types if ext in ['pdf', 'zip', 'doc', 'docx', '7z', 'md']]
        return ['pdf', 'zip', 'doc', 'docx', '7z', 'md']
    
    def is_file_allowed(self, filename):
        """检查文件类型是否允许（严格验证PDF、ZIP、DOC、DOCX、7Z、MD文件）"""
        if '.' not in filename:
            return False
        ext = filename.rsplit('.', 1)[1].lower()
        
        # 获取允许的扩展名
        allowed_extensions = self.get_allowed_extensions()
        
        # 严格验证：只允许支持的文件类型
        if ext not in ['pdf', 'zip', 'doc', 'docx', '7z', 'md']:
            return False
            
        # 检查是否在允许的扩展名列表中
        return ext in allowed_extensions
    
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

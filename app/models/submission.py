"""提交相关模型"""
from datetime import datetime
from flask import url_for
from app.extensions import db


class Submission(db.Model):
    """作业提交模型"""
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    student_name = db.Column(db.String(100), nullable=False)
    student_number = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    grade = db.Column(db.Float)
    feedback = db.Column(db.Text)
    graded_at = db.Column(db.DateTime)
    graded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # 补交相关字段
    is_makeup = db.Column(db.Boolean, default=False)  # 是否补交
    discount_rate = db.Column(db.Float)  # 折扣百分比（0-100）
    original_grade = db.Column(db.Float)  # 原始分数（折扣前）
    
    # 关系
    assignment = db.relationship('Assignment', backref='submissions', cascade='all, delete-orphan', single_parent=True)
    student_user = db.relationship('User', foreign_keys=[student_id], backref='submissions_made')
    grader = db.relationship('User', foreign_keys=[graded_by], backref='graded_submissions')
    
    def is_pdf(self):
        """检查文件是否为PDF格式"""
        return self.original_filename.lower().endswith('.pdf')
    
    def get_file_url(self):
        """获取文件访问URL"""
        return url_for('submission.download_file', submission_id=self.id)
    
    def __repr__(self):
        return f'<Submission {self.student_name} - Assignment {self.assignment_id}>'

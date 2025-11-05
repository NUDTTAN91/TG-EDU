"""班级相关模型"""
from datetime import datetime
from app.extensions import db

# 班级-学生关联表
class_student = db.Table('class_student',
    db.Column('class_id', db.Integer, db.ForeignKey('class.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

# 班级-教师关联表
class_teacher = db.Table('class_teacher',
    db.Column('class_id', db.Integer, db.ForeignKey('class.id'), primary_key=True),
    db.Column('teacher_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)


class Class(db.Model):
    """班级模型"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    grade = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # 关系
    creator = db.relationship('User', backref='created_classes', foreign_keys=[created_by])
    students = db.relationship('User', secondary=class_student, backref='classes')
    teachers = db.relationship('User', secondary=class_teacher, backref='teaching_classes')
    
    def __repr__(self):
        return f'<Class {self.name}>'

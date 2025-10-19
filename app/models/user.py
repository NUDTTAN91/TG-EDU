"""用户相关模型"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db


class UserRole:
    """用户角色枚举"""
    SUPER_ADMIN = 'super_admin'
    TEACHER = 'teacher'
    STUDENT = 'student'


class User(UserMixin, db.Model):
    """用户模型"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    real_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=UserRole.STUDENT)
    student_id = db.Column(db.String(50), unique=True)
    is_active = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # 关系
    created_users = db.relationship('User', backref=db.backref('creator', remote_side=[id]))
    
    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_super_admin(self):
        return self.role == UserRole.SUPER_ADMIN
    
    @property
    def is_teacher(self):
        return self.role == UserRole.TEACHER
    
    @property
    def is_student(self):
        return self.role == UserRole.STUDENT
    
    def can_manage_users(self):
        return self.role in [UserRole.SUPER_ADMIN, UserRole.TEACHER]
    
    def can_create_assignments(self):
        return self.role in [UserRole.SUPER_ADMIN, UserRole.TEACHER]
    
    def can_reset_system(self):
        return self.role == UserRole.SUPER_ADMIN
    
    def __repr__(self):
        return f'<User {self.real_name}>'

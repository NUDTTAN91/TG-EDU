"""操作日志模型"""
from datetime import datetime
from app.extensions import db


class OperationLog(db.Model):
    """操作日志表"""
    __tablename__ = 'operation_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # 可能是未登录用户
    username = db.Column(db.String(50))  # 冗余存储，方便查询
    user_role = db.Column(db.String(20))  # 用户角色
    
    operation_type = db.Column(db.String(50), nullable=False)  # 操作类型：login, submit, view, apply等
    operation_desc = db.Column(db.String(500))  # 操作描述
    
    ip_address = db.Column(db.String(50))  # IP地址
    ip_location = db.Column(db.String(200))  # IP地理位置
    user_agent = db.Column(db.String(500))  # 浏览器信息
    
    request_method = db.Column(db.String(10))  # GET, POST等
    request_path = db.Column(db.String(500))  # 请求路径
    request_params = db.Column(db.Text)  # 请求参数（JSON格式）
    
    result = db.Column(db.String(20))  # success, failed
    error_msg = db.Column(db.Text)  # 错误信息
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # 关联用户
    user = db.relationship('User', backref='operation_logs', lazy='joined')
    
    def __repr__(self):
        return f'<OperationLog {self.id}: {self.username} - {self.operation_type}>'

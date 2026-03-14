"""AI 批改任务队列模型"""
from datetime import datetime
from app.extensions import db


class AIGradingTask(db.Model):
    """AI 批改任务队列"""
    __tablename__ = 'ai_grading_task'
    
    # 状态常量
    STATUS_PENDING = 0      # 等待中
    STATUS_PROCESSING = 1   # 批改中
    STATUS_COMPLETED = 2    # 完成
    STATUS_FAILED = 3       # 失败
    
    STATUS_TEXT = {
        0: '等待中',
        1: '批改中',
        2: '完成',
        3: '失败'
    }
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 关联信息
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # 状态和结果
    status = db.Column(db.Integer, default=STATUS_PENDING)  # 0=等待中, 1=批改中, 2=完成, 3=失败
    score = db.Column(db.Float, nullable=True)              # AI 评分
    feedback = db.Column(db.Text, nullable=True)            # AI 反馈
    error_message = db.Column(db.Text, nullable=True)       # 错误信息
    
    # 详细对话记录（存储 JSON 格式的 API 请求和响应）
    conversation_log = db.Column(db.Text, nullable=True)
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)      # 开始处理时间
    completed_at = db.Column(db.DateTime, nullable=True)    # 完成时间
    
    # 关联关系
    submission = db.relationship('Submission', backref=db.backref('ai_grading_tasks', lazy='dynamic'))
    assignment = db.relationship('Assignment', backref=db.backref('ai_grading_tasks', lazy='dynamic'))
    student = db.relationship('User', backref=db.backref('ai_grading_tasks', lazy='dynamic'))
    
    @property
    def status_text(self):
        """获取状态文本"""
        return self.STATUS_TEXT.get(self.status, '未知')
    
    @property
    def class_name(self):
        """获取班级名称"""
        if self.assignment and self.assignment.class_info:
            return self.assignment.class_info.name
        return '未知'
    
    @property
    def teacher_name(self):
        """获取所属教师名称"""
        if self.assignment and self.assignment.class_info and self.assignment.class_info.teachers:
            # 班级可能有多个教师，取第一个
            return self.assignment.class_info.teachers[0].real_name
        return '未知'
    
    def __repr__(self):
        return f'<AIGradingTask {self.id} - {self.status_text}>'


class AIGradingConfig(db.Model):
    """AI 批改配置（单例模式）"""
    __tablename__ = 'ai_grading_config'
    
    id = db.Column(db.Integer, primary_key=True)
    max_concurrent = db.Column(db.Integer, default=1)  # 最大并发数
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_config():
        """获取配置（单例）"""
        config = AIGradingConfig.query.first()
        if not config:
            config = AIGradingConfig(max_concurrent=1)
            db.session.add(config)
            db.session.commit()
        return config
    
    @staticmethod
    def set_max_concurrent(value):
        """设置最大并发数"""
        config = AIGradingConfig.get_config()
        config.max_concurrent = value
        db.session.commit()
        return config

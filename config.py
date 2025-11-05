"""应用配置"""
import os
from datetime import timedelta, timezone


class Config:
    """基础配置"""
    # 应用基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # 数据库配置
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    STORAGE_DIR = os.environ.get('STORAGE_DIR', os.path.join(BASE_DIR, 'storage'))
    
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(STORAGE_DIR, "data", "homework.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 10,
        'connect_args': {
            'timeout': 30,
            'check_same_thread': False,
            'isolation_level': None  # 启用autocommit模式
        },
        'poolclass': None,  # 禁用连接池，避免SQLite锁问题
        'echo': False
    }
    
    # 文件上传配置
    UPLOAD_FOLDER = 'storage/uploads'
    APPENDIX_FOLDER = '/app/storage/appendix'
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024 * 1024  # 10GB
    
    # 时区配置
    BEIJING_TZ = timezone(timedelta(hours=8))
    
    # 分页配置
    PER_PAGE_OPTIONS = [10, 20, 50, 100]
    DEFAULT_PER_PAGE = 10


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    TESTING = False
    
    def __init__(self):
        # 生产环境必须设置SECRET_KEY
        if Config.SECRET_KEY == 'dev-secret-key-change-in-production':
            import warnings
            warnings.warn(
                '警告：生产环境下使用默认SECRET_KEY是不安全的！'
                '请通过环境变量SECRET_KEY设置安全密钥。',
                UserWarning
            )


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

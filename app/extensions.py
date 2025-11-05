"""Flask扩展初始化"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# 初始化扩展（不绑定app）
db = SQLAlchemy()
login_manager = LoginManager()


def init_extensions(app):
    """初始化所有扩展"""
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # 请求结束后自动关闭数据库会话
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

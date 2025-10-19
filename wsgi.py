"""WSGI入口文件 - 用于Gunicorn等WSGI服务器"""
import os
import sys

# 确保项目根目录在Python路径中
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

# 创建应用实例
config_name = os.getenv('FLASK_ENV', 'production')
app = create_app(config_name)

if __name__ == '__main__':
    app.run()

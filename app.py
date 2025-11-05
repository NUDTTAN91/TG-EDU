"""TG-EDU 教育管理系统 - 应用入口

重构说明:
- 原4628行的app.py已被拆分为模块化结构
- 模型: app/models/
- 路由: app/routes/
- 服务: app/services/
- 工具: app/utils/

使用说明:
- 直接运行: python app.py
- Gunicorn运行: gunicorn app:app
"""
import os
from app import create_app

# 创建应用实例
config_name = os.getenv('FLASK_ENV', 'production')
app = create_app(config_name)

if __name__ == '__main__':
    # 仅用于开发测试
    app.run(host='0.0.0.0', port=5000, debug=True)

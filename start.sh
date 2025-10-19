#!/bin/bash

# 启动脚本 - 用于初始化数据库并启动应用

echo "正在初始化数据库..."

# 设置环境变量
export ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
export ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}
export SECRET_KEY=${SECRET_KEY:-dev-secret-key-change-in-production}

# 初始化数据库
cd /app
python3 -c "
import os
from app import create_app
from app.extensions import db
from app.models import User, UserRole, Notification, MajorAssignment, Team, TeamMember, TeamInvitation, LeaveTeamRequest

app = create_app('production')
with app.app_context():
    try:
        db.create_all()
        print('数据库表创建完成（包括通知表）')
        
        # 检查并添加缺失的列
        try:
            # 先尝试查询现有用户，如果出错说明字段不存在
            User.query.first()
        except Exception as e:
            if 'no such column: user.must_change_password' in str(e):
                print('检测到缺少must_change_password字段，正在添加...')
                # 使用SQLAlchemy的底层连接添加字段
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE user ADD COLUMN must_change_password BOOLEAN DEFAULT 1'))
                    conn.commit()
                print('已添加must_change_password字段到user表')
        
        # 更新现有用户的must_change_password字段
        users_to_update = User.query.all()
        for user in users_to_update:
            if user.role == UserRole.SUPER_ADMIN:
                user.must_change_password = False
            else:
                user.must_change_password = True
        
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
        admin = User.query.filter_by(username=admin_username).first()
        if not admin:
            admin = User(
                username=admin_username, 
                real_name='超级管理员',
                role=UserRole.SUPER_ADMIN
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            print(f'创建默认超级管理员用户: {admin_username}')
        else:
            # 更新旧用户的角色为超级管理员
            updated = False
            if not hasattr(admin, 'role') or admin.role != UserRole.SUPER_ADMIN:
                admin.role = UserRole.SUPER_ADMIN
                updated = True
            if not hasattr(admin, 'real_name') or not admin.real_name:
                admin.real_name = '超级管理员'
                updated = True
            if updated:
                db.session.commit()
            print(f'超级管理员用户 {admin_username} 已存在')
    except Exception as e:
        print(f'数据库初始化错误: {e}')
        import traceback
        traceback.print_exc()
"

echo "启动Web服务器..."
# 优化配置：
# - workers: 根据CPU核心数设置 (2 * CPU核心数 + 1)
# - worker-class: 使用gevent异步worker提高并发能力
# - timeout: 降低超时时间，避免长时间占用worker
# - max-requests: 定期重启worker，防止内存泄漏
# - max-requests-jitter: 添加随机抖动，避免所有worker同时重启
exec gunicorn --bind 0.0.0.0:5000 \
    --workers 8 \
    --worker-class gevent \
    --worker-connections 1000 \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile - \
    wsgi:app
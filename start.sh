#!/bin/bash

# 启动脚本 - 用于初始化数据库并启动应用

echo "正在初始化数据库..."

# 设置环境变量
export ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
export ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}
export SECRET_KEY=${SECRET_KEY:-dev-secret-key-change-in-production}

# 初始化数据库
cd /app

# 先运行数据库迁移
python3 migrations/migrate_db.py

# 运行阶段系统迁移
python3 migrations/migrate_stage_system.py

# 运行任务阶段迁移
python3 migrations/migrate_task_stage.py

# 运行任务阶段stage_id可空迁移
python3 migrations/migrate_task_stage_nullable.py

# 运行大作业附件系统迁移
python3 migrations/migrate_major_assignment_attachments.py

# 运行团队确认理由字段迁移
python3 migrations/migrate_team_confirmation_reason.py

# 运行删除due_date字段迁移
python3 migrations/migrate_remove_due_date.py

# 运行解散团队请求表迁移
python3 migrations/migrate_dissolve_team_request.py

# 运行操作日志表迁移
python3 migrations/migrate_operation_log.py

# 运行IP地理位置字段迁移
python3 migrations/add_ip_location.py

# 然后初始化管理员账户
python3 -c "
import os
from app import create_app
from app.extensions import db
from app.models import User, UserRole, Notification, MajorAssignment, Team, TeamMember, TeamInvitation, LeaveTeamRequest, DissolveTeamRequest
import sqlite3

app = create_app('production')
with app.app_context():
    try:
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
        
        # 移除 major_assignment 表的 teacher_id 字段
        try:
            # 检查 teacher_id 字段是否存在
            with db.engine.connect() as conn:
                result = conn.execute(db.text('PRAGMA table_info(major_assignment)'))
                columns = result.fetchall()
                column_names = [col[1] for col in columns]
                
                if 'teacher_id' in column_names:
                    print('发现 teacher_id 字段，正在移除...')
                    
                    # SQLite 不支持 DROP COLUMN，需要重建表
                    conn.execute(db.text('''CREATE TABLE major_assignment_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        requirement_file_path VARCHAR(500),
                        requirement_file_name VARCHAR(255),
                        requirement_url VARCHAR(500),
                        start_date DATETIME,
                        end_date DATETIME,
                        due_date DATETIME,
                        min_team_size INTEGER DEFAULT 2,
                        max_team_size INTEGER DEFAULT 5,
                        class_id INTEGER NOT NULL,
                        creator_id INTEGER NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1,
                        FOREIGN KEY(class_id) REFERENCES class(id),
                        FOREIGN KEY(creator_id) REFERENCES user(id)
                    )'''))
                    
                    conn.execute(db.text('''INSERT INTO major_assignment_new 
                        (id, title, description, requirement_file_path, requirement_file_name, 
                         requirement_url, start_date, end_date, due_date, min_team_size, 
                         max_team_size, class_id, creator_id, created_at, is_active)
                        SELECT 
                            id, title, description, requirement_file_path, requirement_file_name,
                            requirement_url, start_date, end_date, due_date, min_team_size,
                            max_team_size, class_id, creator_id, created_at, is_active
                        FROM major_assignment
                    '''))
                    
                    conn.execute(db.text('DROP TABLE major_assignment'))
                    conn.execute(db.text('ALTER TABLE major_assignment_new RENAME TO major_assignment'))
                    conn.commit()
                    print('✅ teacher_id 字段已成功移除')
                else:
                    print('teacher_id 字段不存在，无需移除')
        except Exception as e:
            print(f'移除 teacher_id 字段时出错: {e}')
        
        # 迁移TeamDivision表以支持自由定义角色
        try:
            from app.models.team import TeamDivision
            # 检查字段是否已存在
            with db.engine.connect() as conn:
                result = conn.execute(db.text('PRAGMA table_info(team_division)'))
                columns = result.fetchall()
                column_names = [col[1] for col in columns]
                
                needs_migration = False
                if 'stage_id' not in column_names:
                    needs_migration = True
                if 'role_name' not in column_names:
                    needs_migration = True
                if 'role_description' not in column_names:
                    needs_migration = True
                
                if needs_migration:
                    print('开始迁移TeamDivision表...')
                    
                    # 创建新表
                    conn.execute(db.text('''CREATE TABLE team_division_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        team_id INTEGER NOT NULL,
                        stage_id INTEGER,
                        division_role_id INTEGER,
                        role_name VARCHAR(100),
                        role_description TEXT,
                        member_id INTEGER,
                        assigned_at DATETIME,
                        assigned_by INTEGER,
                        FOREIGN KEY(team_id) REFERENCES team(id),
                        FOREIGN KEY(stage_id) REFERENCES stage(id),
                        FOREIGN KEY(division_role_id) REFERENCES division_role(id),
                        FOREIGN KEY(member_id) REFERENCES user(id),
                        FOREIGN KEY(assigned_by) REFERENCES user(id)
                    )'''))
                    
                    # 复制现有数据
                    conn.execute(db.text('''INSERT INTO team_division_new 
                        (id, team_id, division_role_id, member_id, assigned_at, assigned_by)
                        SELECT id, team_id, division_role_id, member_id, assigned_at, assigned_by
                        FROM team_division
                    '''))
                    
                    # 删除旧表
                    conn.execute(db.text('DROP TABLE team_division'))
                    
                    # 重命名新表
                    conn.execute(db.text('ALTER TABLE team_division_new RENAME TO team_division'))
                    
                    conn.commit()
                    print('✅ TeamDivision表迁移成功')
                else:
                    print('TeamDivision表已是最新版本，无需迁移')
        except Exception as e:
            print(f'迁移TeamDivision表时出错: {e}')
            import traceback
            traceback.print_exc()
        
        # 迁移Notification表，将sender_id改为可空（支持系统通知）
        try:
            # 检查notification表的sender_id字段约束
            with db.engine.connect() as conn:
                result = conn.execute(db.text('PRAGMA table_info(notification)'))
                columns = result.fetchall()
                
                # 检查sender_id的NOT NULL约束
                needs_migration = False
                for col in columns:
                    if col[1] == 'sender_id' and col[3] == 1:  # col[3] == 1 表示NOT NULL
                        needs_migration = True
                        break
                
                if needs_migration:
                    print('开始迁移Notification表，将sender_id改为可空...')
                    
                    # 创建新表
                    conn.execute(db.text('''CREATE TABLE notification_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title VARCHAR(200) NOT NULL,
                        content TEXT NOT NULL,
                        notification_type VARCHAR(50) NOT NULL,
                        sender_id INTEGER,
                        receiver_id INTEGER NOT NULL,
                        is_read BOOLEAN DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        related_assignment_id INTEGER,
                        related_submission_id INTEGER,
                        FOREIGN KEY(sender_id) REFERENCES user(id),
                        FOREIGN KEY(receiver_id) REFERENCES user(id),
                        FOREIGN KEY(related_assignment_id) REFERENCES assignment(id),
                        FOREIGN KEY(related_submission_id) REFERENCES submission(id)
                    )'''))
                    
                    # 复制现有数据
                    conn.execute(db.text('''INSERT INTO notification_new 
                        (id, title, content, notification_type, sender_id, receiver_id, 
                         is_read, created_at, related_assignment_id, related_submission_id)
                        SELECT id, title, content, notification_type, sender_id, receiver_id,
                               is_read, created_at, related_assignment_id, related_submission_id
                        FROM notification
                    '''))
                    
                    # 删除旧表
                    conn.execute(db.text('DROP TABLE notification'))
                    
                    # 重命名新表
                    conn.execute(db.text('ALTER TABLE notification_new RENAME TO notification'))
                    
                    conn.commit()
                    print('✅ Notification表迁移成功，sender_id现在可以为空')
                else:
                    print('Notification表已是最新版本，无需迁移')
        except Exception as e:
            print(f'迁移Notification表时出错: {e}')
            import traceback
            traceback.print_exc()
        
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
# 清理旧的调度器锁文件
rm -f /tmp/tg_edu_scheduler_flask.lock
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
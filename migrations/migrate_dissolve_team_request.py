#!/usr/bin/env python3
"""数据库迁移脚本 - 添加解散团队请求表"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db

def migrate_database():
    """迁移数据库到新架构"""
    app = create_app('production')
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                # 检查dissolve_team_request表是否存在
                result = conn.execute(db.text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='dissolve_team_request'"
                ))
                if not result.fetchone():
                    print('创建dissolve_team_request表...')
                    conn.execute(db.text('''
                        CREATE TABLE dissolve_team_request (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            team_id INTEGER NOT NULL,
                            leader_id INTEGER NOT NULL,
                            reason TEXT NOT NULL,
                            status VARCHAR(50) DEFAULT 'pending',
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            responded_at DATETIME,
                            reviewer_id INTEGER,
                            review_comment TEXT,
                            FOREIGN KEY(team_id) REFERENCES team (id),
                            FOREIGN KEY(leader_id) REFERENCES user (id),
                            FOREIGN KEY(reviewer_id) REFERENCES user (id)
                        )
                    '''))
                    conn.commit()
                    print('✅ dissolve_team_request表创建完成')
                else:
                    print('dissolve_team_request表已存在，无需创建')
            
            print('数据库迁移完成！')
            
        except Exception as e:
            print(f'数据库迁移错误: {e}')
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    migrate_database()

#!/usr/bin/env python3
"""数据库迁移脚本 - 添加多教师管理支持"""
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
            # 先创建所有表（包括关联表）
            db.create_all()
            print('数据库表创建完成')
            
            with db.engine.connect() as conn:
                # 检查major_assignment_teachers表是否存在
                result = conn.execute(db.text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='major_assignment_teachers'"
                ))
                if not result.fetchone():
                    print('创建major_assignment_teachers关联表...')
                    conn.execute(db.text('''
                        CREATE TABLE major_assignment_teachers (
                            major_assignment_id INTEGER NOT NULL,
                            teacher_id INTEGER NOT NULL,
                            created_at DATETIME,
                            PRIMARY KEY (major_assignment_id, teacher_id),
                            FOREIGN KEY(major_assignment_id) REFERENCES major_assignment (id),
                            FOREIGN KEY(teacher_id) REFERENCES user (id)
                        )
                    '''))
                    conn.commit()
                    print('major_assignment_teachers关联表创建完成')
                
                # 检查major_assignment表结构
                result = conn.execute(db.text("PRAGMA table_info(major_assignment)"))
                columns = [row[1] for row in result.fetchall()]
                
                # 添加creator_id字段
                if 'creator_id' not in columns:
                    print('添加creator_id字段到major_assignment表...')
                    conn.execute(db.text('ALTER TABLE major_assignment ADD COLUMN creator_id INTEGER'))
                    conn.commit()
                    
                    # 如果存在teacher_id，迁移数据
                    if 'teacher_id' in columns:
                        # 将teacher_id数据复制到creator_id
                        conn.execute(db.text(
                            'UPDATE major_assignment SET creator_id = teacher_id WHERE creator_id IS NULL'
                        ))
                        conn.commit()
                        print('已将teacher_id数据迁移到creator_id')
                        
                        # 将教师关系迁移到关联表
                        conn.execute(db.text('''
                            INSERT INTO major_assignment_teachers (major_assignment_id, teacher_id, created_at)
                            SELECT id, teacher_id, created_at FROM major_assignment WHERE teacher_id IS NOT NULL
                        '''))
                        conn.commit()
                        print('已将教师关系迁移到major_assignment_teachers表')
                else:
                    print('creator_id字段已存在')
            
            print('数据库迁移完成！')
            
        except Exception as e:
            print(f'数据库迁移错误: {e}')
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    migrate_database()

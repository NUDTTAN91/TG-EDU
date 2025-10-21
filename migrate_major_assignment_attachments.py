#!/usr/bin/env python3
"""
大作业附件系统数据库迁移脚本
添加 major_assignment_attachment 和 major_assignment_link 表
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db

def migrate_database():
    """执行数据库迁移"""
    app = create_app('production')
    with app.app_context():
        # 创建新表
        from app.models import MajorAssignmentAttachment, MajorAssignmentLink
        
        # 检查表是否已存在
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'major_assignment_attachment' not in existing_tables:
            # 创建 major_assignment_attachment 表
            db.session.execute("""
                CREATE TABLE IF NOT EXISTS major_assignment_attachment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    major_assignment_id INTEGER NOT NULL,
                    file_path VARCHAR(500) NOT NULL,
                    original_filename VARCHAR(255) NOT NULL,
                    file_size INTEGER,
                    file_type VARCHAR(50) DEFAULT 'file',
                    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    uploaded_by INTEGER,
                    FOREIGN KEY (major_assignment_id) REFERENCES major_assignment (id),
                    FOREIGN KEY (uploaded_by) REFERENCES user (id)
                )
            """)
            print("✓ 已创建 major_assignment_attachment 表")
        else:
            print("- major_assignment_attachment 表已存在，跳过创建")
        
        if 'major_assignment_link' not in existing_tables:
            # 创建 major_assignment_link 表
            db.session.execute("""
                CREATE TABLE IF NOT EXISTS major_assignment_link (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    major_assignment_id INTEGER NOT NULL,
                    url VARCHAR(500) NOT NULL,
                    title VARCHAR(200),
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER,
                    FOREIGN KEY (major_assignment_id) REFERENCES major_assignment (id),
                    FOREIGN KEY (created_by) REFERENCES user (id)
                )
            """)
            print("✓ 已创建 major_assignment_link 表")
        else:
            print("- major_assignment_link 表已存在，跳过创建")
        
        db.session.commit()
        print("\n数据库迁移完成！")
        print("现在大作业支持多个附件和链接。")

if __name__ == '__main__':
    migrate_database()

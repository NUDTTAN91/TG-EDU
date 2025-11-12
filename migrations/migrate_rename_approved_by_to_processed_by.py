#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移：将 makeup_requests 表的 approved_by 字段重命名为 processed_by
"""
import sqlite3
import os
import sys

# 获取项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def migrate():
    """执行数据库迁移"""
    db_path = os.path.join(project_root, 'storage/data/homework.db')
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 检查 makeup_requests 表结构
        cursor.execute("PRAGMA table_info(makeup_requests)")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"当前表字段: {columns}")
        
        # 2. 如果已经是 processed_by，跳过迁移
        if 'processed_by' in columns:
            print("✅ processed_by 字段已存在，无需迁移")
            conn.close()
            return True
        
        # 3. 如果没有 approved_by 字段，跳过
        if 'approved_by' not in columns:
            print("⚠️  approved_by 字段不存在，无法迁移")
            conn.close()
            return False
        
        # 4. SQLite 不支持直接重命名列，需要重建表
        print("正在重命名字段：approved_by -> processed_by...")
        
        # 4.1 创建新表
        cursor.execute("""
            CREATE TABLE makeup_requests_new (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                deadline DATETIME,
                reject_reason TEXT,
                processed_by INTEGER,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (student_id) REFERENCES user (id),
                FOREIGN KEY (assignment_id) REFERENCES assignment (id),
                FOREIGN KEY (processed_by) REFERENCES user (id)
            )
        """)
        
        # 4.2 复制数据（将 approved_by 映射到 processed_by）
        cursor.execute("""
            INSERT INTO makeup_requests_new 
            (id, student_id, assignment_id, reason, status, deadline, reject_reason, 
             processed_by, created_at, updated_at)
            SELECT id, student_id, assignment_id, reason, status, deadline, reject_reason,
                   approved_by, created_at, updated_at
            FROM makeup_requests
        """)
        
        # 4.3 删除旧表
        cursor.execute("DROP TABLE makeup_requests")
        
        # 4.4 重命名新表
        cursor.execute("ALTER TABLE makeup_requests_new RENAME TO makeup_requests")
        
        conn.commit()
        print("✅ 字段重命名成功：approved_by -> processed_by")
        
        # 5. 验证新表结构
        cursor.execute("PRAGMA table_info(makeup_requests)")
        new_columns = [column[1] for column in cursor.fetchall()]
        print(f"新表字段: {new_columns}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {str(e)}")
        conn.rollback()
        conn.close()
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("数据库迁移：重命名 approved_by -> processed_by")
    print("=" * 60)
    
    success = migrate()
    
    if success:
        print("\n✅ 迁移完成！")
        sys.exit(0)
    else:
        print("\n❌ 迁移失败！")
        sys.exit(1)

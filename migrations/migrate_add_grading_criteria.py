#!/usr/bin/env python3
"""为 assignment 表添加 grading_criteria 字段的数据库迁移脚本"""
import os
import sys
import sqlite3

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate_database():
    """为 assignment 表添加 grading_criteria 字段"""
    # 数据库路径
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                          'storage', 'data', 'homework.db')
    
    # 如果在 Docker 容器内，使用容器内的路径
    if os.path.exists('/app/storage/data/homework.db'):
        db_path = '/app/storage/data/homework.db'
    
    if not os.path.exists(db_path):
        print(f'数据库文件不存在: {db_path}')
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(assignment)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'grading_criteria' not in column_names:
            print('正在为 assignment 表添加 grading_criteria 字段...')
            cursor.execute('ALTER TABLE assignment ADD COLUMN grading_criteria TEXT')
            conn.commit()
            print('✅ grading_criteria 字段添加成功')
        else:
            print('grading_criteria 字段已存在，无需迁移')
        
        conn.close()
        
    except Exception as e:
        print(f'❌ 迁移失败: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    migrate_database()

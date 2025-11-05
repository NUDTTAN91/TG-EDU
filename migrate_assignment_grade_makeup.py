"""
添加补交相关字段到assignment_grade表
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('storage/data/homework.db')
    cursor = conn.cursor()
    
    # 检查字段是否已存在
    cursor.execute("PRAGMA table_info(assignment_grade)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # 添加 is_makeup 字段
    if 'is_makeup' not in columns:
        cursor.execute('ALTER TABLE assignment_grade ADD COLUMN is_makeup INTEGER DEFAULT 0')
        print('✓ 添加 is_makeup 字段到 assignment_grade')
    else:
        print('- is_makeup 字段已存在')
    
    # 添加 discount_rate 字段
    if 'discount_rate' not in columns:
        cursor.execute('ALTER TABLE assignment_grade ADD COLUMN discount_rate REAL')
        print('✓ 添加 discount_rate 字段到 assignment_grade')
    else:
        print('- discount_rate 字段已存在')
    
    # 添加 original_grade 字段
    if 'original_grade' not in columns:
        cursor.execute('ALTER TABLE assignment_grade ADD COLUMN original_grade REAL')
        print('✓ 添加 original_grade 字段到 assignment_grade')
    else:
        print('- original_grade 字段已存在')
    
    conn.commit()
    conn.close()
    print('数据库迁移完成！')

if __name__ == '__main__':
    migrate()

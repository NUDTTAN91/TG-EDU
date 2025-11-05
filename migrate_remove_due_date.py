"""删除 MajorAssignment 表的 due_date 字段"""
import sqlite3
import os

def migrate():
    db_path = 'storage/data/tg_edu.db'
    
    if not os.path.exists(db_path):
        print(f'数据库文件不存在: {db_path}')
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查 due_date 列是否存在
        cursor.execute("PRAGMA table_info(major_assignment)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'due_date' not in column_names:
            print('due_date 列不存在，无需迁移')
            conn.close()
            return
        
        print('开始删除 due_date 列...')
        
        # SQLite 不支持直接 DROP COLUMN，需要重建表
        # 1. 创建新表（不包含 due_date）
        cursor.execute('''
            CREATE TABLE major_assignment_new (
                id INTEGER PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                requirement_file_path VARCHAR(500),
                requirement_file_name VARCHAR(255),
                requirement_url VARCHAR(500),
                start_date DATETIME,
                end_date DATETIME,
                min_team_size INTEGER DEFAULT 2,
                max_team_size INTEGER DEFAULT 5,
                class_id INTEGER NOT NULL,
                creator_id INTEGER NOT NULL,
                created_at DATETIME,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (class_id) REFERENCES class(id),
                FOREIGN KEY (creator_id) REFERENCES user(id)
            )
        ''')
        
        # 2. 复制数据（不包含 due_date）
        cursor.execute('''
            INSERT INTO major_assignment_new (
                id, title, description, requirement_file_path, requirement_file_name,
                requirement_url, start_date, end_date, min_team_size, max_team_size,
                class_id, creator_id, created_at, is_active
            )
            SELECT 
                id, title, description, requirement_file_path, requirement_file_name,
                requirement_url, start_date, end_date, min_team_size, max_team_size,
                class_id, creator_id, created_at, is_active
            FROM major_assignment
        ''')
        
        # 3. 删除旧表
        cursor.execute('DROP TABLE major_assignment')
        
        # 4. 重命名新表
        cursor.execute('ALTER TABLE major_assignment_new RENAME TO major_assignment')
        
        conn.commit()
        print('✓ due_date 列删除成功')
        
    except Exception as e:
        print(f'迁移失败: {str(e)}')
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

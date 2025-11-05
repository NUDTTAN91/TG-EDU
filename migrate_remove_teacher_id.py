"""移除 major_assignment 表中的 teacher_id 字段

该字段已经被 major_assignment_teachers 多对多关系表替代
"""
import sqlite3
import os

def migrate_remove_teacher_id():
    """移除 teacher_id 字段"""
    # 尝试多个可能的数据库路径
    possible_paths = [
        '/app/storage/data/tg_edu.db',
        'storage/data/tg_edu.db',
        'tg_edu.db'
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    # 如果数据库文件不存在，跳过迁移
    if not db_path:
        print("数据库文件不存在，跳过迁移")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查 teacher_id 字段是否存在
        cursor.execute("PRAGMA table_info(major_assignment)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'teacher_id' not in column_names:
            print("teacher_id 字段不存在，无需迁移")
            conn.close()
            return
        
        print("发现 teacher_id 字段，开始迁移...")
        
        # SQLite 不支持 DROP COLUMN，需要重建表
        # 步骤1：创建新表（不含 teacher_id）
        cursor.execute("""
            CREATE TABLE major_assignment_new (
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
            )
        """)
        
        # 步骤2：复制数据（不包括 teacher_id）
        cursor.execute("""
            INSERT INTO major_assignment_new 
            (id, title, description, requirement_file_path, requirement_file_name, 
             requirement_url, start_date, end_date, due_date, min_team_size, 
             max_team_size, class_id, creator_id, created_at, is_active)
            SELECT 
                id, title, description, requirement_file_path, requirement_file_name,
                requirement_url, start_date, end_date, due_date, min_team_size,
                max_team_size, class_id, creator_id, created_at, is_active
            FROM major_assignment
        """)
        
        # 步骤3：删除旧表
        cursor.execute("DROP TABLE major_assignment")
        
        # 步骤4：重命名新表
        cursor.execute("ALTER TABLE major_assignment_new RENAME TO major_assignment")
        
        conn.commit()
        print("✅ teacher_id 字段已成功移除")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 迁移失败: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_remove_teacher_id()

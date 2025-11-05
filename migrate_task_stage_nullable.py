"""迁移脚本：将team_task表的stage_id字段改为可空

任务阶段不再依赖教师创建的Stage，而是每个团队的必备功能
"""
import sqlite3
import os


def migrate_task_stage_nullable():
    """将team_task表的stage_id改为可空"""
    db_path = '/app/storage/data/homework.db'
    
    # 如果数据库文件不存在，跳过迁移
    if not os.path.exists(db_path):
        print("数据库文件不存在，跳过迁移")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查team_task表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='team_task'")
        if not cursor.fetchone():
            print("team_task表不存在，跳过迁移")
            conn.close()
            return
        
        print("开始迁移team_task表，将stage_id改为可空...")
        
        # 检查stage_id是否已经是可空的
        cursor.execute("PRAGMA table_info(team_task)")
        columns = cursor.fetchall()
        
        needs_migration = False
        for col in columns:
            if col[1] == 'stage_id' and col[3] == 1:  # col[3] == 1 表示NOT NULL
                needs_migration = True
                break
        
        if not needs_migration:
            print("✅ stage_id已经是可空的，无需迁移")
            conn.close()
            return
        
        # SQLite不支持ALTER COLUMN，需要重建表
        print("  创建新表team_task_new...")
        cursor.execute('''
            CREATE TABLE team_task_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                stage_id INTEGER,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                assigned_to INTEGER,
                priority VARCHAR(20) DEFAULT 'medium',
                status VARCHAR(50) DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                created_by INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                FOREIGN KEY(team_id) REFERENCES team(id),
                FOREIGN KEY(stage_id) REFERENCES stage(id),
                FOREIGN KEY(assigned_to) REFERENCES user(id),
                FOREIGN KEY(created_by) REFERENCES user(id)
            )
        ''')
        
        # 复制数据
        print("  复制现有数据...")
        cursor.execute('''
            INSERT INTO team_task_new 
            (id, team_id, stage_id, title, description, assigned_to, priority, 
             status, progress, created_by, created_at, updated_at, completed_at)
            SELECT 
                id, team_id, stage_id, title, description, assigned_to, priority,
                status, progress, created_by, created_at, updated_at, completed_at
            FROM team_task
        ''')
        
        # 删除旧表
        print("  删除旧表...")
        cursor.execute('DROP TABLE team_task')
        
        # 重命名新表
        print("  重命名新表...")
        cursor.execute('ALTER TABLE team_task_new RENAME TO team_task')
        
        conn.commit()
        print("✅ team_task表迁移成功，stage_id现在可以为空")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 迁移失败: {str(e)}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    migrate_task_stage_nullable()

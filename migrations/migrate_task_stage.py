"""迁移脚本：添加任务阶段相关表

新增表：
- team_task: 团队任务表
- task_progress: 任务进度记录表
"""
import sqlite3
import os


def migrate_task_stage():
    """迁移任务阶段相关表"""
    db_path = '/app/storage/data/homework.db'
    
    # 如果数据库文件不存在，跳过迁移
    if not os.path.exists(db_path):
        print("数据库文件不存在，跳过迁移")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("开始迁移任务阶段相关表...")
        
        # 1. 检查team_task表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='team_task'")
        if not cursor.fetchone():
            print("  创建team_task表...")
            cursor.execute('''
                CREATE TABLE team_task (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER NOT NULL,
                    stage_id INTEGER NOT NULL,
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
            print("  ✅ team_task表创建成功")
        else:
            print("  team_task表已存在")
        
        # 2. 检查task_progress表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_progress'")
        if not cursor.fetchone():
            print("  创建task_progress表...")
            cursor.execute('''
                CREATE TABLE task_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    progress INTEGER NOT NULL,
                    status VARCHAR(50),
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(task_id) REFERENCES team_task(id),
                    FOREIGN KEY(user_id) REFERENCES user(id)
                )
            ''')
            print("  ✅ task_progress表创建成功")
        else:
            print("  task_progress表已存在")
        
        conn.commit()
        print("✅ 任务阶段相关表迁移完成！")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 迁移失败: {str(e)}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    migrate_task_stage()

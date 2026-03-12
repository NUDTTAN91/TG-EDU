"""AI 批改队列表迁移脚本"""
import os
import sqlite3


def migrate():
    """执行迁移"""
    # 支持多个可能的数据库路径
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage', 'data', 'homework.db'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage', 'data', 'app.db'),
        '/app/storage/data/homework.db',
        '/app/storage/data/app.db',
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print(f"数据库文件不存在，尝试过: {possible_paths}")
        return False
    
    print(f"使用数据库: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查 ai_grading_task 表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_grading_task'")
        if not cursor.fetchone():
            # 创建 AI 批改任务队列表
            cursor.execute('''
                CREATE TABLE ai_grading_task (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    assignment_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    status INTEGER DEFAULT 0,
                    score REAL,
                    feedback TEXT,
                    error_message TEXT,
                    conversation_log TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (submission_id) REFERENCES submission (id),
                    FOREIGN KEY (assignment_id) REFERENCES assignment (id),
                    FOREIGN KEY (student_id) REFERENCES user (id)
                )
            ''')
            print("已创建 ai_grading_task 表")
            
            # 创建索引
            cursor.execute('CREATE INDEX idx_ai_grading_task_status ON ai_grading_task (status)')
            cursor.execute('CREATE INDEX idx_ai_grading_task_created_at ON ai_grading_task (created_at)')
            print("已创建索引")
        else:
            print("ai_grading_task 表已存在，跳过创建")
        
        # 检查 ai_grading_config 表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_grading_config'")
        if not cursor.fetchone():
            # 创建 AI 批改配置表
            cursor.execute('''
                CREATE TABLE ai_grading_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    max_concurrent INTEGER DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 插入默认配置
            cursor.execute('INSERT INTO ai_grading_config (max_concurrent) VALUES (1)')
            print("已创建 ai_grading_config 表并插入默认配置")
        else:
            print("ai_grading_config 表已存在，跳过创建")
        
        conn.commit()
        print("AI 批改队列表迁移完成")
        return True
        
    except Exception as e:
        print(f"迁移失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    migrate()

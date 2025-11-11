"""添加作弊标记字段"""
import sqlite3
import os

def migrate():
    """添加作弊标记字段到AssignmentGrade表"""
    db_path = 'storage/data/homework.db'
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(assignment_grade)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_cheating' not in columns:
            print("正在添加 is_cheating 字段...")
            cursor.execute("""
                ALTER TABLE assignment_grade 
                ADD COLUMN is_cheating BOOLEAN DEFAULT 0
            """)
            print("✓ is_cheating 字段添加成功")
        else:
            print("is_cheating 字段已存在，跳过")
        
        conn.commit()
        print("数据库迁移完成！")
        
    except Exception as e:
        conn.rollback()
        print(f"迁移失败: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

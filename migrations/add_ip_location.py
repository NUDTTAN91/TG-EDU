"""添加IP地理位置字段到操作日志表"""
import sqlite3
import os

def migrate():
    """执行数据库迁移"""
    db_path = os.getenv('DATABASE_PATH', '/app/data/tg_edu.db')
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(operation_log)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'ip_location' not in columns:
            print("添加 ip_location 字段到 operation_log 表...")
            cursor.execute("""
                ALTER TABLE operation_log 
                ADD COLUMN ip_location VARCHAR(200)
            """)
            conn.commit()
            print("ip_location 字段添加成功！")
        else:
            print("ip_location 字段已存在，跳过迁移")
        
        conn.close()
        
    except Exception as e:
        print(f"迁移失败: {e}")
        raise

if __name__ == '__main__':
    migrate()

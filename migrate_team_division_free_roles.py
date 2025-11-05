"""迁移TeamDivision表以支持自由定义角色

添加字段：
- stage_id: 关联到阶段
- role_name: 角色名称（自由输入）
- role_description: 角色描述（自由输入）

修改字段：
- division_role_id: 改为可选（nullable=True）
"""
import sqlite3
import os

def migrate_team_division_free_roles():
    """迁移TeamDivision表"""
    db_path = '/app/storage/data/tg_edu.db'
    
    # 如果数据库文件不存在，跳过迁移
    if not os.path.exists(db_path):
        print("数据库文件不存在，跳过迁移")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(team_division)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print("开始迁移TeamDivision表...")
        
        # 检查是否需要添加新字段
        needs_migration = False
        if 'stage_id' not in column_names:
            needs_migration = True
            print("  - 需要添加 stage_id 字段")
        if 'role_name' not in column_names:
            needs_migration = True
            print("  - 需要添加 role_name 字段")
        if 'role_description' not in column_names:
            needs_migration = True
            print("  - 需要添加 role_description 字段")
        
        if not needs_migration:
            print("✅ TeamDivision表已是最新版本，无需迁移")
            conn.close()
            return
        
        # SQLite不支持修改列，需要重建表
        print("  重建表...")
        
        # 1. 创建新表
        cursor.execute("""
            CREATE TABLE team_division_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                stage_id INTEGER,
                division_role_id INTEGER,
                role_name VARCHAR(100),
                role_description TEXT,
                member_id INTEGER,
                assigned_at DATETIME,
                assigned_by INTEGER,
                FOREIGN KEY(team_id) REFERENCES team(id),
                FOREIGN KEY(stage_id) REFERENCES stage(id),
                FOREIGN KEY(division_role_id) REFERENCES division_role(id),
                FOREIGN KEY(member_id) REFERENCES user(id),
                FOREIGN KEY(assigned_by) REFERENCES user(id)
            )
        """)
        
        # 2. 复制现有数据
        cursor.execute("""
            INSERT INTO team_division_new 
            (id, team_id, division_role_id, member_id, assigned_at, assigned_by)
            SELECT id, team_id, division_role_id, member_id, assigned_at, assigned_by
            FROM team_division
        """)
        
        # 3. 删除旧表
        cursor.execute("DROP TABLE team_division")
        
        # 4. 重命名新表
        cursor.execute("ALTER TABLE team_division_new RENAME TO team_division")
        
        conn.commit()
        print("✅ TeamDivision表迁移成功")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 迁移失败: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_team_division_free_roles()

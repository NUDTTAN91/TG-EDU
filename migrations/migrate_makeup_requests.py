"""
数据库迁移脚本：添加补交申请表和相关字段
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # 创建补交申请表
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS makeup_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            assignment_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            deadline DATETIME,
            reject_reason TEXT,
            approved_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users (id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (approved_by) REFERENCES users (id)
        )
    """))
    
    # 为submissions表添加补交相关字段（如果不存在）
    try:
        db.session.execute(text("""
            ALTER TABLE submissions ADD COLUMN is_makeup BOOLEAN DEFAULT 0
        """))
    except:
        print("is_makeup字段已存在")
    
    try:
        db.session.execute(text("""
            ALTER TABLE submissions ADD COLUMN discount_rate FLOAT
        """))
    except:
        print("discount_rate字段已存在")
    
    try:
        db.session.execute(text("""
            ALTER TABLE submissions ADD COLUMN original_grade FLOAT
        """))
    except:
        print("original_grade字段已存在")
    
    # 为assignment_grades表添加补交相关字段（如果不存在）
    try:
        db.session.execute(text("""
            ALTER TABLE assignment_grades ADD COLUMN is_makeup BOOLEAN DEFAULT 0
        """))
    except:
        print("assignment_grades的is_makeup字段已存在")
    
    try:
        db.session.execute(text("""
            ALTER TABLE assignment_grades ADD COLUMN discount_rate FLOAT
        """))
    except:
        print("assignment_grades的discount_rate字段已存在")
    
    try:
        db.session.execute(text("""
            ALTER TABLE assignment_grades ADD COLUMN original_grade FLOAT
        """))
    except:
        print("assignment_grades的original_grade字段已存在")
    
    db.session.commit()
    print("数据库迁移完成！")

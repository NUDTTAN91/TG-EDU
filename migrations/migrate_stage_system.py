"""数据库迁移脚本 - 添加阶段管理系统"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.extensions import db
from app import create_app
from sqlalchemy import text

def migrate_database():
    """执行数据库迁移"""
    app = create_app()
    
    with app.app_context():
        print("开始数据库迁移...")
        
        try:
            # 1. 为MajorAssignment表添加新字段
            print("\n1. 为MajorAssignment表添加新字段...")
            
            # 检查start_date字段是否存在
            result = db.session.execute(text("PRAGMA table_info(major_assignment)")).fetchall()
            columns = [col[1] for col in result]
            
            if 'start_date' not in columns:
                db.session.execute(text("ALTER TABLE major_assignment ADD COLUMN start_date DATETIME"))
                print("  ✓ 添加start_date字段")
            else:
                print("  - start_date字段已存在")
            
            if 'end_date' not in columns:
                db.session.execute(text("ALTER TABLE major_assignment ADD COLUMN end_date DATETIME"))
                print("  ✓ 添加end_date字段")
            else:
                print("  - end_date字段已存在")
            
            db.session.commit()
            
            # 2. 为Team表添加新字段
            print("\n2. 为Team表添加新字段...")
            
            result = db.session.execute(text("PRAGMA table_info(team)")).fetchall()
            columns = [col[1] for col in result]
            
            if 'confirmation_requested_at' not in columns:
                db.session.execute(text("ALTER TABLE team ADD COLUMN confirmation_requested_at DATETIME"))
                print("  ✓ 添加confirmation_requested_at字段")
            else:
                print("  - confirmation_requested_at字段已存在")
            
            if 'is_locked' not in columns:
                db.session.execute(text("ALTER TABLE team ADD COLUMN is_locked BOOLEAN DEFAULT 0"))
                print("  ✓ 添加is_locked字段")
            else:
                print("  - is_locked字段已存在")
            
            db.session.commit()
            
            # 3. 创建Stage表
            print("\n3. 创建Stage表...")
            
            result = db.session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='stage'"
            )).fetchone()
            
            if not result:
                db.session.execute(text("""
                    CREATE TABLE stage (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        major_assignment_id INTEGER NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        description TEXT,
                        stage_type VARCHAR(50) NOT NULL,
                        start_date DATETIME,
                        end_date DATETIME,
                        "order" INTEGER DEFAULT 0,
                        status VARCHAR(50) DEFAULT 'pending',
                        is_locked BOOLEAN DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(major_assignment_id) REFERENCES major_assignment (id)
                    )
                """))
                print("  ✓ Stage表创建成功")
            else:
                print("  - Stage表已存在")
            
            db.session.commit()
            
            # 3.1 为Stage表添加提交模式列
            print("\n3.1. 为Stage表添加提交模式(submission_mode)列...")
            result = db.session.execute(text("PRAGMA table_info(stage)")).fetchall()
            stage_columns = [col[1] for col in result]
            if 'submission_mode' not in stage_columns:
                db.session.execute(text("ALTER TABLE stage ADD COLUMN submission_mode VARCHAR(20)"))
                print("  ✓ 添加submission_mode字段")
            else:
                print("  - submission_mode字段已存在")
            db.session.commit()
            
            # 3.2 创建StageSubmission表
            print("\n3.2. 创建StageSubmission表...")
            result = db.session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='stage_submission'"
            )).fetchone()
            if not result:
                db.session.execute(text("""
                    CREATE TABLE stage_submission (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        stage_id INTEGER NOT NULL,
                        team_id INTEGER NOT NULL,
                        submit_type VARCHAR(20) NOT NULL,
                        file_path TEXT,
                        original_filename TEXT,
                        file_size INTEGER,
                        url TEXT,
                        submitted_by INTEGER,
                        submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(stage_id) REFERENCES stage (id),
                        FOREIGN KEY(team_id) REFERENCES team (id),
                        FOREIGN KEY(submitted_by) REFERENCES user (id)
                    )
                """))
                print("  ✓ StageSubmission表创建成功")
            else:
                print("  - StageSubmission表已存在")
            db.session.commit()
            
            # 4. 创建DivisionRole表
            print("\n4. 创建DivisionRole表...")
            
            result = db.session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='division_role'"
            )).fetchone()
            
            if not result:
                db.session.execute(text("""
                    CREATE TABLE division_role (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        stage_id INTEGER NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        description TEXT,
                        is_required BOOLEAN DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(stage_id) REFERENCES stage (id)
                    )
                """))
                print("  ✓ DivisionRole表创建成功")
            else:
                print("  - DivisionRole表已存在")
            
            db.session.commit()
            
            # 5. 创建TeamDivision表
            print("\n5. 创建TeamDivision表...")
            
            result = db.session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='team_division'"
            )).fetchone()
            
            if not result:
                db.session.execute(text("""
                    CREATE TABLE team_division (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        team_id INTEGER NOT NULL,
                        division_role_id INTEGER NOT NULL,
                        member_id INTEGER,
                        assigned_at DATETIME,
                        assigned_by INTEGER,
                        FOREIGN KEY(team_id) REFERENCES team (id),
                        FOREIGN KEY(division_role_id) REFERENCES division_role (id),
                        FOREIGN KEY(member_id) REFERENCES user (id),
                        FOREIGN KEY(assigned_by) REFERENCES user (id),
                        UNIQUE(team_id, division_role_id)
                    )
                """))
                print("  ✓ TeamDivision表创建成功")
            else:
                print("  - TeamDivision表已存在")
            
            db.session.commit()
            
            print("\n✅ 数据库迁移完成！")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ 迁移失败: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_database()

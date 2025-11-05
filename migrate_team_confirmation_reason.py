#!/usr/bin/env python3
"""
团队确认理由字段迁移脚本
添加 confirmation_request_reason 和 reject_reason 字段到 team 表
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from sqlalchemy import text

def migrate_database():
    """执行数据库迁移"""
    app = create_app('production')
    with app.app_context():
        print("开始迁移团队确认理由相关字段...")
        
        try:
            # 检查team表的字段
            result = db.session.execute(text("PRAGMA table_info(team)")).fetchall()
            columns = [col[1] for col in result]
            
            # 添加 confirmation_request_reason 字段
            if 'confirmation_request_reason' not in columns:
                db.session.execute(text("ALTER TABLE team ADD COLUMN confirmation_request_reason TEXT"))
                print("  ✓ 添加 confirmation_request_reason 字段")
            else:
                print("  - confirmation_request_reason 字段已存在")
            
            # 添加 reject_reason 字段
            if 'reject_reason' not in columns:
                db.session.execute(text("ALTER TABLE team ADD COLUMN reject_reason TEXT"))
                print("  ✓ 添加 reject_reason 字段")
            else:
                print("  - reject_reason 字段已存在")
            
            db.session.commit()
            print("\n✅ 团队确认理由字段迁移完成！")
            
        except Exception as e:
            print(f"迁移失败: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False
        
        return True

if __name__ == '__main__':
    migrate_database()

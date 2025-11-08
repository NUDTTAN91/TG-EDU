#!/usr/bin/env python3
"""添加操作日志表的数据库迁移脚本"""
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import OperationLog

def migrate_database():
    """创建操作日志表"""
    app = create_app('production')
    
    with app.app_context():
        try:
            # 检查表是否已存在
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            
            if 'operation_log' not in inspector.get_table_names():
                print('正在创建operation_log表...')
                
                # 创建表
                OperationLog.__table__.create(db.engine)
                
                print('✅ operation_log表创建成功')
            else:
                print('operation_log表已存在，无需迁移')
                
        except Exception as e:
            print(f'❌ 迁移失败: {e}')
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    migrate_database()

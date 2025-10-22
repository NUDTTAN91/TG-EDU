#!/usr/bin/env python3
"""
数据库初始化脚本
用于创建数据库表和默认管理员用户
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import User, Assignment, Notification, MajorAssignment, Team, TeamMember, TeamInvitation, LeaveTeamRequest, DissolveTeamRequest

def init_database():
    """初始化数据库"""
    app = create_app('production')
    with app.app_context():
        # 创建所有表
        db.create_all()
        print("数据库表创建完成")
        
        # 检查并添加缺失的列
        check_and_update_schema()
        
        # 创建默认管理员用户
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
        # 检查管理员是否已存在
        existing_admin = User.query.filter_by(username=admin_username).first()
        if not existing_admin:
            admin = User(username=admin_username, is_teacher=True)
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            print(f"创建默认管理员用户: {admin_username}")
        else:
            print(f"管理员用户 {admin_username} 已存在")

def check_and_update_schema():
    """检查并更新数据库表结构"""
    import sqlite3
    conn = sqlite3.connect('/app/storage/data/homework.db')
    cursor = conn.cursor()
    
    # 检查assignment表的列
    cursor.execute("PRAGMA table_info(assignment)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # 检查并添加max_submissions列
    if 'max_submissions' not in columns:
        try:
            cursor.execute("ALTER TABLE assignment ADD COLUMN max_submissions INTEGER DEFAULT 1")
            conn.commit()
            print("已添加max_submissions列到assignment表")
        except Exception as e:
            print(f"添加max_submissions列时出错: {e}")
    
    # 检查并添加附件相关列
    attachment_columns = [
        ('attachment_filename', 'TEXT'),
        ('attachment_original_filename', 'TEXT'),
        ('attachment_file_path', 'TEXT'),
        ('attachment_file_size', 'INTEGER')
    ]
    
    for column_name, column_type in attachment_columns:
        if column_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE assignment ADD COLUMN {column_name} {column_type}")
                conn.commit()
                print(f"已添加{column_name}列到assignment表")
            except Exception as e:
                print(f"添加{column_name}列时出错: {e}")
    
    conn.close()

if __name__ == '__main__':
    init_database()
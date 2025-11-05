#!/usr/bin/env python3
"""
演示脚本：修改作业截止时间来测试实时更新功能
"""

import sys
import os
sys.path.append('/app')

from app import *
from datetime import datetime, timedelta

def update_deadline():
    """修改作业截止时间"""
    with app.app_context():
        assignment = Assignment.query.first()
        if not assignment:
            print("没有找到作业")
            return
        
        old_deadline = assignment.due_date
        print(f"原截止时间: {old_deadline}")
        
        # 将截止时间延长2小时
        new_deadline = assignment.due_date + timedelta(hours=2)
        assignment.due_date = new_deadline
        
        db.session.commit()
        print(f"新截止时间: {new_deadline}")
        print("截止时间已更新！学生页面应该在2-5分钟内自动刷新。")

if __name__ == "__main__":
    update_deadline()
#!/usr/bin/env python3
"""
通知功能测试脚本
用于测试通知系统的各项功能
"""

import sys
import os
sys.path.append('/app')

from app import *

def test_notification_system():
    """测试通知系统"""
    with app.app_context():
        print("=" * 60)
        print("通知功能测试")
        print("=" * 60)
        
        # 1. 检查数据库表是否存在
        print("\n1. 检查通知表是否存在...")
        try:
            count = Notification.query.count()
            print(f"✅ 通知表存在，当前有 {count} 条通知")
        except Exception as e:
            print(f"❌ 通知表不存在或有错误: {e}")
            return
        
        # 2. 获取测试用户
        print("\n2. 获取测试用户...")
        admin = User.query.filter_by(role=UserRole.SUPER_ADMIN).first()
        teacher = User.query.filter_by(role=UserRole.TEACHER).first()
        student = User.query.filter_by(role=UserRole.STUDENT).first()
        
        if admin:
            print(f"✅ 找到超级管理员: {admin.real_name}")
        if teacher:
            print(f"✅ 找到教师: {teacher.real_name}")
        if student:
            print(f"✅ 找到学生: {student.real_name}")
        
        if not (admin or teacher):
            print("❌ 没有找到管理员或教师，无法测试发送通知")
            return
        
        # 3. 测试创建通知
        print("\n3. 测试创建通知...")
        sender = admin if admin else teacher
        
        # 创建一个测试通知
        if student:
            test_notification = create_notification(
                sender_id=sender.id,
                receiver_id=student.id,
                title="测试通知",
                content="这是一条测试通知，用于验证通知系统是否正常工作。",
                notification_type='system'
            )
            print(f"✅ 成功创建通知 ID: {test_notification.id}")
        else:
            print("⚠️  没有学生用户，跳过创建通知测试")
        
        # 4. 测试获取未读通知数量
        print("\n4. 测试获取未读通知数量...")
        if student:
            unread_count = get_unread_notification_count(student.id)
            print(f"✅ 学生 {student.real_name} 的未读通知数量: {unread_count}")
        
        # 5. 测试标记已读
        print("\n5. 测试标记通知为已读...")
        if student:
            notifications = Notification.query.filter_by(
                receiver_id=student.id, 
                is_read=False
            ).limit(1).all()
            
            if notifications:
                result = mark_notification_as_read(notifications[0].id)
                if result:
                    print(f"✅ 成功标记通知 ID {notifications[0].id} 为已读")
                    new_count = get_unread_notification_count(student.id)
                    print(f"   未读数量变为: {new_count}")
                else:
                    print("❌ 标记已读失败")
            else:
                print("⚠️  没有未读通知可以标记")
        
        # 6. 测试全部标记已读
        print("\n6. 测试全部标记已读...")
        if student:
            before_count = get_unread_notification_count(student.id)
            mark_all_notifications_as_read(student.id)
            after_count = get_unread_notification_count(student.id)
            print(f"✅ 标记前未读数量: {before_count}")
            print(f"   标记后未读数量: {after_count}")
        
        # 7. 显示统计信息
        print("\n7. 通知系统统计...")
        total_notifications = Notification.query.count()
        unread_notifications = Notification.query.filter_by(is_read=False).count()
        system_notifications = Notification.query.filter_by(notification_type='system').count()
        grade_notifications = Notification.query.filter_by(notification_type='grade').count()
        
        print(f"   总通知数: {total_notifications}")
        print(f"   未读通知: {unread_notifications}")
        print(f"   系统通知: {system_notifications}")
        print(f"   评分通知: {grade_notifications}")
        
        print("\n" + "=" * 60)
        print("✅ 通知功能测试完成！")
        print("=" * 60)

if __name__ == '__main__':
    test_notification_system()

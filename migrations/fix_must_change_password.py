#!/usr/bin/env python3
"""
修复must_change_password字段
将所有密码不是默认密码123456的用户的must_change_password设置为False
"""
from app import create_app
from app.extensions import db
from app.models import User

def fix_must_change_password():
    """修复must_change_password字段"""
    app = create_app()
    
    with app.app_context():
        print("开始修复must_change_password字段...")
        
        # 获取所有用户
        users = User.query.all()
        fixed_count = 0
        
        for user in users:
            # 检查密码是否为默认密码123456
            is_default = user.check_password('123456')
            
            if not is_default and user.must_change_password:
                # 密码不是123456但must_change_password为True，说明用户已经修改过密码
                print(f"修复用户: {user.username} ({user.real_name}) - 密码已修改过，设置must_change_password=False")
                user.must_change_password = False
                fixed_count += 1
            elif is_default and not user.must_change_password and not user.is_super_admin:
                # 密码是123456但must_change_password为False，需要强制修改
                print(f"标记用户: {user.username} ({user.real_name}) - 使用默认密码，设置must_change_password=True")
                user.must_change_password = True
                fixed_count += 1
            elif user.is_super_admin and user.must_change_password:
                # 超级管理员不需要强制修改密码
                print(f"修复超级管理员: {user.username} ({user.real_name}) - 设置must_change_password=False")
                user.must_change_password = False
                fixed_count += 1
        
        if fixed_count > 0:
            db.session.commit()
            print(f"\n✅ 修复完成！共修复 {fixed_count} 个用户")
        else:
            print("\n✅ 所有用户状态正常，无需修复")
        
        # 统计
        total_users = len(users)
        need_change = User.query.filter_by(must_change_password=True).count()
        print(f"\n📊 统计信息：")
        print(f"   总用户数: {total_users}")
        print(f"   需要修改密码: {need_change}")
        print(f"   无需修改密码: {total_users - need_change}")

if __name__ == '__main__':
    fix_must_change_password()

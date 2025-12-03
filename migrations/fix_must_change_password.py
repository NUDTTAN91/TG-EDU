#!/usr/bin/env python3
"""
一次性迁移脚本：修复must_change_password字段
将所有密码不是默认密码123456的用户的must_change_password设置为False

注意：这是一次性迁移，只需要执行一次，之后由用户创建/修改逻辑自动维护
"""
import sqlite3
import os

def fix_must_change_password():
    """修复must_change_password字段"""
    db_path = '/app/data/tg_edu.db'
    
    # 检查数据库是否存在
    if not os.path.exists(db_path):
        print('数据库不存在，跳过迁移')
        return
    
    print('开始一次性迁移：修复must_change_password字段...')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有用户
        cursor.execute('SELECT id, username, real_name, password_hash, role FROM user')
        users = cursor.fetchall()
        
        if not users:
            print('没有用户，跳过迁移')
            conn.close()
            return
        
        fixed_count = 0
        
        # 需要导入werkzeug来验证密码
        from werkzeug.security import check_password_hash
        
        for user_id, username, real_name, password_hash, role in users:
            # 检查密码是否为123456
            is_default = check_password_hash(password_hash, '123456')
            
            if role == 'super_admin':
                # 超级管理员：始终为False
                cursor.execute('UPDATE user SET must_change_password = 0 WHERE id = ?', (user_id,))
                fixed_count += 1
                print(f'修复超级管理员: {username} ({real_name})')
            elif is_default:
                # 密码是123456：设置为True
                cursor.execute('UPDATE user SET must_change_password = 1 WHERE id = ?', (user_id,))
                fixed_count += 1
                print(f'标记需要修改: {username} ({real_name}) - 使用默认密码')
            else:
                # 密码不是123456：设置为False
                cursor.execute('UPDATE user SET must_change_password = 0 WHERE id = ?', (user_id,))
                fixed_count += 1
                print(f'修复已改密码: {username} ({real_name}) - 密码已修改过')
        
        conn.commit()
        
        # 统计
        cursor.execute('SELECT COUNT(*) FROM user WHERE must_change_password = 1')
        need_change = cursor.fetchone()[0]
        total = len(users)
        
        print(f'\n✅ 迁移完成！共修复 {fixed_count} 个用户')
        print(f'\n📊 统计信息：')
        print(f'   总用户数: {total}')
        print(f'   需要修改密码: {need_change}')
        print(f'   无需修改密码: {total - need_change}')
        
        conn.close()
        
    except Exception as e:
        print(f'迁移失败: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    fix_must_change_password()

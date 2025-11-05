"""
启用SQLite WAL模式以提高并发性能
WAL模式允许读写操作并发进行，大幅减少锁等待时间
"""
import sqlite3
import os

db_path = 'storage/data/homework.db'

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查当前模式
        cursor.execute('PRAGMA journal_mode')
        current_mode = cursor.fetchone()[0]
        print(f'当前日志模式: {current_mode}')
        
        # 启用WAL模式
        cursor.execute('PRAGMA journal_mode=WAL')
        new_mode = cursor.fetchone()[0]
        print(f'新日志模式: {new_mode}')
        
        # 优化WAL性能
        cursor.execute('PRAGMA synchronous=NORMAL')  # 提高写入速度
        cursor.execute('PRAGMA cache_size=-64000')    # 64MB缓存
        cursor.execute('PRAGMA temp_store=MEMORY')    # 临时表存储在内存
        
        # 设置busy timeout（毫秒）
        cursor.execute('PRAGMA busy_timeout=30000')   # 30秒超时
        
        conn.commit()
        conn.close()
        
        print('✓ WAL模式已启用，数据库性能优化完成')
        print('  - 读写可以并发进行')
        print('  - 大幅减少锁等待')
        print('  - 提升页面加载速度')
        
    except Exception as e:
        print(f'✗ 启用WAL模式失败: {e}')
else:
    print(f'✗ 数据库文件不存在: {db_path}')

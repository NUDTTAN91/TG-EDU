"""定时任务服务 - 自动更新阶段状态和处理AI批改队列"""
from flask_apscheduler import APScheduler
from app.services.stage_service import StageService
import os


scheduler = APScheduler()


def init_scheduler(app):
    """初始化定时任务调度器"""
    # 只在第一个worker中启动调度器
    # 使用环境变量来控制，避免多个worker重复启动
    import os
    import time
    import sys
    
    # 检查是否是迁移脚本或工具脚本（不启动调度器）
    script_name = os.path.basename(sys.argv[0] if sys.argv else '')
    # 迁移脚本和工具脚本都可能在 migrations/ 或 scripts/ 目录下
    if script_name.startswith('migrate_') or script_name in ['init_db.py', 'update_stage_status.py', 'enable_wal_mode.py']:
        return
    
    # 检查是否已有其他worker启动了调度器
    scheduler_lock_file = '/tmp/tg_edu_scheduler_flask.lock'
    current_pid = os.getpid()
    
    try:
        # 如果锁文件已存在，检查其创建时间
        if os.path.exists(scheduler_lock_file):
            # 检查锁文件是否是最近30秒内创建的（同一批worker）
            lock_age = time.time() - os.path.getmtime(scheduler_lock_file)
            if lock_age < 30:  # 30秒内
                with open(scheduler_lock_file, 'r') as f:
                    lock_pid = f.read().strip()
                print(f"⚠️  Worker {current_pid}: 调度器已在Worker {lock_pid}中启动，跳过")
                return
            else:
                # 过期的锁，删除它（可能是上次运行留下的）
                os.remove(scheduler_lock_file)
        
        # 创建锁文件，写入当前进程ID
        with open(scheduler_lock_file, 'w') as f:
            f.write(str(current_pid))
    except Exception as e:
        print(f"❌ 创建调度器锁文件失败: {e}")
        return
    
    # 配置调度器
    app.config['SCHEDULER_API_ENABLED'] = False  # 禁用API，提高安全性
    
    scheduler.init_app(app)
    
    # 添加定时任务：每分钟检查一次阶段状态
    @scheduler.task('interval', id='update_stage_status', minutes=1, misfire_grace_time=900)
    def scheduled_stage_update():
        """定时更新阶段状态"""
        with app.app_context():
            try:
                print("⏰ 定时任务：开始更新阶段状态...")
                StageService.check_and_update_stages()
                print("✅ 定时任务：阶段状态更新完成")
            except Exception as e:
                print(f"❌ 定时任务：阶段状态更新失败 - {str(e)}")
                import traceback
                traceback.print_exc()
    
    # 添加定时任务：每10秒处理一次AI批改队列
    @scheduler.task('interval', id='process_ai_queue', seconds=10, misfire_grace_time=60)
    def scheduled_ai_queue_process():
        """定时处理AI批改队列"""
        with app.app_context():
            try:
                from app.services.ai_queue_service import AIQueueService
                AIQueueService.process_queue()
            except Exception as e:
                print(f"❌ AI队列处理失败: {str(e)}")
                import traceback
                traceback.print_exc()
    
    # 启动调度器
    scheduler.start()
    print(f"🚀 Worker {current_pid}: 定时任务调度器已启动")

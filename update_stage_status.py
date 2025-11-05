"""定时任务 - 自动更新阶段状态"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.stage_service import StageService

def run_stage_update():
    """运行阶段状态更新任务"""
    app = create_app()
    
    with app.app_context():
        print("开始更新阶段状态...")
        result = StageService.check_and_update_stages()
        
        if result:
            print("✅ 阶段状态更新成功")
        else:
            print("❌ 阶段状态更新失败")

if __name__ == '__main__':
    run_stage_update()

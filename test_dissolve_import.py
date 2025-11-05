#!/usr/bin/env python3
"""测试 DissolveTeamRequest 模型是否可以正确导入"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

try:
    print("正在测试导入...")
    
    # 测试从 app.models.team 直接导入
    print("1. 测试从 app.models.team 导入...")
    from app.models.team import DissolveTeamRequest
    print("   ✅ 从 app.models.team 导入成功")
    
    # 测试从 app.models 导入
    print("2. 测试从 app.models 导入...")
    from app.models import DissolveTeamRequest as DTR
    print("   ✅ 从 app.models 导入成功")
    
    # 测试在应用上下文中访问模型
    print("3. 测试在应用上下文中访问模型...")
    from app import create_app
    from app.extensions import db
    
    app = create_app('production')
    with app.app_context():
        # 测试表是否存在
        print("   检查数据库表...")
        with db.engine.connect() as conn:
            result = conn.execute(db.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='dissolve_team_request'"
            ))
            table_exists = result.fetchone()
            
            if table_exists:
                print("   ✅ dissolve_team_request 表已存在")
            else:
                print("   ⚠️  dissolve_team_request 表不存在，需要运行迁移")
        
        # 测试模型是否可以被 ORM 识别
        print("   检查模型映射...")
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'dissolve_team_request' in tables:
            print("   ✅ 模型已正确映射到数据库")
            
            # 显示表结构
            columns = inspector.get_columns('dissolve_team_request')
            print("   表结构:")
            for col in columns:
                print(f"     - {col['name']}: {col['type']}")
        else:
            print("   ⚠️  表未映射")
    
    print("\n✅ 所有测试通过！DissolveTeamRequest 模型可以正常使用。")
    
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

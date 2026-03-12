"""
数据库迁移脚本：添加 AI 自动改卷模式相关字段
为 assignment 表添加：
- ai_grading_mode: AI 改卷模式
- reference_answer: 参考答案文本
- reference_answer_filename: 参考答案文件名
- reference_answer_original_filename: 参考答案原始文件名
- reference_answer_file_path: 参考答案文件路径
- reference_answer_file_size: 参考答案文件大小
"""
import sqlite3
import os

def migrate():
    """执行迁移"""
    # 支持多个可能的数据库路径
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage', 'data', 'homework.db'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage', 'data', 'app.db'),
        '/app/storage/data/homework.db',
        '/app/storage/data/app.db',
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print(f"数据库文件不存在，尝试过: {possible_paths}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查并添加 ai_grading_mode 字段
        cursor.execute("PRAGMA table_info(assignment)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'ai_grading_mode' not in columns:
            cursor.execute("ALTER TABLE assignment ADD COLUMN ai_grading_mode INTEGER DEFAULT 0")
            print("已添加 ai_grading_mode 字段")
        else:
            print("ai_grading_mode 字段已存在")
        
        if 'reference_answer' not in columns:
            cursor.execute("ALTER TABLE assignment ADD COLUMN reference_answer TEXT")
            print("已添加 reference_answer 字段")
        else:
            print("reference_answer 字段已存在")
        
        if 'reference_answer_filename' not in columns:
            cursor.execute("ALTER TABLE assignment ADD COLUMN reference_answer_filename VARCHAR(255)")
            print("已添加 reference_answer_filename 字段")
        else:
            print("reference_answer_filename 字段已存在")
        
        if 'reference_answer_original_filename' not in columns:
            cursor.execute("ALTER TABLE assignment ADD COLUMN reference_answer_original_filename VARCHAR(255)")
            print("已添加 reference_answer_original_filename 字段")
        else:
            print("reference_answer_original_filename 字段已存在")
        
        if 'reference_answer_file_path' not in columns:
            cursor.execute("ALTER TABLE assignment ADD COLUMN reference_answer_file_path VARCHAR(500)")
            print("已添加 reference_answer_file_path 字段")
        else:
            print("reference_answer_file_path 字段已存在")
        
        if 'reference_answer_file_size' not in columns:
            cursor.execute("ALTER TABLE assignment ADD COLUMN reference_answer_file_size INTEGER")
            print("已添加 reference_answer_file_size 字段")
        else:
            print("reference_answer_file_size 字段已存在")
        
        conn.commit()
        print("AI 自动改卷模式字段迁移完成")
        
        # 检查并添加 submission 表的 AI 评分字段
        cursor.execute("PRAGMA table_info(submission)")
        submission_columns = [column[1] for column in cursor.fetchall()]
        
        if 'ai_score' not in submission_columns:
            cursor.execute("ALTER TABLE submission ADD COLUMN ai_score FLOAT")
            print("已添加 submission.ai_score 字段")
        else:
            print("submission.ai_score 字段已存在")
        
        if 'ai_feedback' not in submission_columns:
            cursor.execute("ALTER TABLE submission ADD COLUMN ai_feedback TEXT")
            print("已添加 submission.ai_feedback 字段")
        else:
            print("submission.ai_feedback 字段已存在")
        
        conn.commit()
        print("Submission 表 AI 评分字段迁移完成")
        return True
        
    except Exception as e:
        print(f"迁移失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    migrate()

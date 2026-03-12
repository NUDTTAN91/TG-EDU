"""AI 批改队列处理服务"""
import json
import threading
from datetime import datetime
from flask import current_app


class AIQueueService:
    """AI 批改队列处理服务"""
    
    # 处理锁，防止并发问题
    _processing_lock = threading.Lock()
    _is_processing = False
    
    @staticmethod
    def process_queue():
        """处理队列中的任务"""
        from app.models import AIGradingTask, AIGradingConfig, Submission, Assignment
        from app.services.ai_grading_service import AIGradingService
        from app.extensions import db
        
        # 防止重复处理
        if AIQueueService._is_processing:
            return
        
        with AIQueueService._processing_lock:
            if AIQueueService._is_processing:
                return
            AIQueueService._is_processing = True
        
        try:
            # 获取配置
            config = AIGradingConfig.get_config()
            max_concurrent = config.max_concurrent
            
            # 获取当前正在处理的任务数
            processing_count = AIGradingTask.query.filter_by(
                status=AIGradingTask.STATUS_PROCESSING
            ).count()
            
            # 计算可以处理的任务数
            available_slots = max_concurrent - processing_count
            if available_slots <= 0:
                return
            
            # 获取待处理的任务
            pending_tasks = AIGradingTask.query.filter_by(
                status=AIGradingTask.STATUS_PENDING
            ).order_by(AIGradingTask.created_at.asc()).limit(available_slots).all()
            
            if not pending_tasks:
                return
            
            print(f"📝 AI队列：发现 {len(pending_tasks)} 个待处理任务")
            
            for task in pending_tasks:
                try:
                    AIQueueService._process_single_task(task)
                except Exception as e:
                    print(f"❌ AI队列：任务 {task.id} 处理失败: {e}")
                    import traceback
                    traceback.print_exc()
        
        finally:
            AIQueueService._is_processing = False
    
    @staticmethod
    def _process_single_task(task):
        """处理单个任务"""
        from app.models import AIGradingTask, Submission, Assignment
        from app.services.ai_grading_service import AIGradingService
        from app.extensions import db
        
        # 标记为处理中
        task.status = AIGradingTask.STATUS_PROCESSING
        task.started_at = datetime.utcnow()
        db.session.commit()
        
        print(f"🔄 AI队列：开始处理任务 {task.id}")
        
        try:
            # 获取提交和作业信息
            submission = Submission.query.get(task.submission_id)
            assignment = Assignment.query.get(task.assignment_id)
            
            if not submission or not assignment:
                raise ValueError("提交或作业不存在")
            
            # 获取参考答案
            reference_content = None
            if assignment.ai_grading_mode == 1:  # 有参考答案模式
                if assignment.reference_answer:
                    reference_content = assignment.reference_answer
                elif assignment.reference_answer_file_path:
                    result = AIGradingService.extract_file_content(
                        assignment.reference_answer_file_path
                    )
                    if isinstance(result, tuple):
                        reference_content = result[0]
                    else:
                        reference_content = result
            
            # 获取学生提交内容
            result = AIGradingService.extract_file_content(submission.file_path)
            if isinstance(result, tuple):
                student_content = result[0]
                extract_error = result[1]
            else:
                student_content = result
                extract_error = None
            
            if not student_content:
                raise ValueError(f"无法提取学生提交内容: {extract_error or '未知错误'}")
            
            # 构建请求参数（用于记录对话）
            request_params = {
                'assignment_title': assignment.title,
                'assignment_description': assignment.description or '',
                'grading_criteria': assignment.grading_criteria or '',
                'student_content_preview': student_content[:500] + '...' if len(student_content) > 500 else student_content,
                'reference_answer_preview': (reference_content[:500] + '...' if reference_content and len(reference_content) > 500 else reference_content) if reference_content else None,
                'max_score': 100
            }
            
            # 调用 AI 评分
            ai_result = AIGradingService.grade_submission(
                assignment_title=assignment.title,
                assignment_description=assignment.description or '',
                grading_criteria=assignment.grading_criteria or '',
                student_content=student_content,
                reference_answer=reference_content,
                max_score=100
            )
            
            # 记录对话日志
            conversation_log = {
                'request': request_params,
                'response': ai_result,
                'timestamp': datetime.utcnow().isoformat()
            }
            task.conversation_log = json.dumps(conversation_log, ensure_ascii=False, indent=2)
            
            if ai_result.get('success'):
                # 成功
                task.status = AIGradingTask.STATUS_COMPLETED
                task.score = ai_result.get('score')
                task.feedback = ai_result.get('comment')
                task.completed_at = datetime.utcnow()
                
                # 更新提交记录
                submission.ai_score = ai_result.get('score')
                submission.ai_feedback = ai_result.get('comment')
                
                print(f"✅ AI队列：任务 {task.id} 完成，评分: {task.score}")
            else:
                # 失败
                task.status = AIGradingTask.STATUS_FAILED
                task.error_message = ai_result.get('error', 'AI 评分失败')
                task.completed_at = datetime.utcnow()
                
                print(f"⚠️ AI队列：任务 {task.id} 失败: {task.error_message}")
            
            db.session.commit()
            
        except Exception as e:
            # 异常处理
            task.status = AIGradingTask.STATUS_FAILED
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            
            # 记录错误日志
            error_log = {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
            task.conversation_log = json.dumps(error_log, ensure_ascii=False, indent=2)
            
            db.session.commit()
            
            print(f"❌ AI队列：任务 {task.id} 异常: {e}")
            raise

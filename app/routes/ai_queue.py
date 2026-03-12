"""AI 批改队列管理路由"""
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.models import AIGradingTask, AIGradingConfig
from app.extensions import db
from app.utils.decorators import super_admin_required

ai_queue_bp = Blueprint('ai_queue', __name__, url_prefix='/admin/ai-queue')


@ai_queue_bp.route('/')
@login_required
@super_admin_required
def index():
    """AI 批改队列页面"""
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status', '', type=str)
    
    # 构建查询
    query = AIGradingTask.query.order_by(AIGradingTask.created_at.desc())
    
    # 状态筛选
    if status_filter != '':
        try:
            status_filter_int = int(status_filter)
            query = query.filter(AIGradingTask.status == status_filter_int)
        except ValueError:
            pass
    
    # 分页
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    tasks = pagination.items
    
    # 获取统计数据
    total_tasks = AIGradingTask.query.count()
    pending_count = AIGradingTask.query.filter_by(status=AIGradingTask.STATUS_PENDING).count()
    processing_count = AIGradingTask.query.filter_by(status=AIGradingTask.STATUS_PROCESSING).count()
    completed_count = AIGradingTask.query.filter_by(status=AIGradingTask.STATUS_COMPLETED).count()
    failed_count = AIGradingTask.query.filter_by(status=AIGradingTask.STATUS_FAILED).count()
    
    # 获取配置
    config = AIGradingConfig.get_config()
    
    return render_template('ai_queue/index.html',
                          tasks=tasks,
                          pagination=pagination,
                          total_tasks=total_tasks,
                          pending_count=pending_count,
                          processing_count=processing_count,
                          completed_count=completed_count,
                          failed_count=failed_count,
                          config=config,
                          status_filter=status_filter)


@ai_queue_bp.route('/config', methods=['POST'])
@login_required
@super_admin_required
def update_config():
    """更新配置"""
    data = request.get_json() or {}
    max_concurrent = data.get('max_concurrent', 3)
    
    try:
        max_concurrent = int(max_concurrent)
        if max_concurrent < 1:
            max_concurrent = 1
        if max_concurrent > 10:
            max_concurrent = 10
            
        AIGradingConfig.set_max_concurrent(max_concurrent)
        
        return jsonify({
            'success': True,
            'message': f'并发数已更新为 {max_concurrent}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'更新失败: {str(e)}'
        }), 400


@ai_queue_bp.route('/task/<int:task_id>')
@login_required
@super_admin_required
def task_detail(task_id):
    """获取任务详情（包括对话记录）"""
    task = AIGradingTask.query.get_or_404(task_id)
    
    return jsonify({
        'success': True,
        'data': {
            'id': task.id,
            'student_name': task.student.real_name if task.student else '未知',
            'assignment_title': task.assignment.title if task.assignment else '未知',
            'class_name': task.class_name,
            'teacher_name': task.teacher_name,
            'status': task.status,
            'status_text': task.status_text,
            'score': task.score,
            'feedback': task.feedback,
            'error_message': task.error_message,
            'conversation_log': task.conversation_log,
            'created_at': task.created_at.strftime('%Y-%m-%d %H:%M:%S') if task.created_at else None,
            'started_at': task.started_at.strftime('%Y-%m-%d %H:%M:%S') if task.started_at else None,
            'completed_at': task.completed_at.strftime('%Y-%m-%d %H:%M:%S') if task.completed_at else None
        }
    })


@ai_queue_bp.route('/task/<int:task_id>/retry', methods=['POST'])
@login_required
@super_admin_required
def retry_task(task_id):
    """重试失败的任务"""
    task = AIGradingTask.query.get_or_404(task_id)
    
    if task.status != AIGradingTask.STATUS_FAILED:
        return jsonify({
            'success': False,
            'message': '只能重试失败的任务'
        }), 400
    
    # 重置任务状态
    task.status = AIGradingTask.STATUS_PENDING
    task.error_message = None
    task.started_at = None
    task.completed_at = None
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '任务已重新加入队列'
    })


@ai_queue_bp.route('/task/<int:task_id>', methods=['DELETE'])
@login_required
@super_admin_required
def delete_task(task_id):
    """删除任务"""
    task = AIGradingTask.query.get_or_404(task_id)
    
    db.session.delete(task)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '任务已删除'
    })


@ai_queue_bp.route('/clear-completed', methods=['POST'])
@login_required
@super_admin_required
def clear_completed():
    """清除已完成的任务"""
    deleted = AIGradingTask.query.filter_by(status=AIGradingTask.STATUS_COMPLETED).delete()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'已清除 {deleted} 条已完成的任务'
    })

"""操作日志路由"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import UserRole, User
from app.services.log_service import LogService
from app.utils.decorators import require_role
from datetime import datetime, timedelta

bp = Blueprint('logs', __name__, url_prefix='/logs')


@bp.route('/')
@login_required
@require_role(UserRole.SUPER_ADMIN)
def index():
    """日志列表页面 - 仅超级管理员可访问"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)  # 默认每页显示10条
    
    # 过滤条件
    user_id = request.args.get('user_id', type=int)
    operation_type = request.args.get('operation_type')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # 转换日期
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        except:
            pass
    
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            end_date = end_date + timedelta(days=1)  # 包含当天结束
        except:
            pass
    
    # 获取日志
    pagination = LogService.get_logs(
        page=page,
        per_page=per_page,
        user_id=user_id,
        operation_type=operation_type,
        start_date=start_date,
        end_date=end_date
    )
    
    # 获取统计信息
    stats = LogService.get_operation_stats()
    
    # 获取所有用户（用于筛选）
    users = User.query.order_by(User.username).all()
    
    # 操作类型列表
    operation_types = [
        ('login', '登录'),
        ('logout', '登出'),
        ('submit', '提交作业'),
        ('view', '查看'),
        ('apply', '申请'),
        ('create', '创建'),
        ('update', '更新'),
        ('delete', '删除'),
        ('download', '下载'),
        ('grade', '评分'),
    ]
    
    return render_template(
        'logs/index.html',
        pagination=pagination,
        logs=pagination.items,
        stats=stats,
        users=users,
        operation_types=operation_types,
        # 当前过滤条件
        current_user_id=user_id,
        current_operation_type=operation_type,
        current_start_date=start_date_str,
        current_end_date=end_date_str,
        current_per_page=per_page
    )


@bp.route('/api/stats')
@login_required
@require_role(UserRole.SUPER_ADMIN)
def api_stats():
    """获取统计数据的API - 用于图表展示"""
    stats = LogService.get_operation_stats()
    
    return jsonify({
        'total_logs': stats['total_logs'],
        'today_logs': stats['today_logs'],
        'operation_type_stats': [
            {'type': item[0], 'count': item[1]}
            for item in stats['operation_type_stats']
        ],
        'user_stats': [
            {'username': item[0], 'count': item[1]}
            for item in stats['user_stats']
        ]
    })

"""
补交相关路由
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models import Assignment, User, Submission, MakeupRequest
from app.utils.decorators import require_teacher_or_admin
from app.services.log_service import LogService

bp = Blueprint('makeup', __name__, url_prefix='/makeup')


@bp.route('/request/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def request_makeup(assignment_id):
    """学生申请补交"""
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 检查是否已经有待处理的申请
    existing_request = MakeupRequest.query.filter_by(
        student_id=current_user.id,
        assignment_id=assignment_id,
        status='pending'
    ).first()
    
    if existing_request:
        flash('您已经提交过补交申请，请等待老师审批', 'warning')
        return redirect(url_for('student.dashboard'))
    
    if request.method == 'POST':
        reason = request.form.get('reason', '').strip()
        
        if not reason:
            flash('请填写补交理由', 'error')
            return render_template('makeup/request_form.html', assignment=assignment)
        
        # 创建补交申请
        makeup_request = MakeupRequest(
            student_id=current_user.id,
            assignment_id=assignment_id,
            reason=reason
        )
        
        db.session.add(makeup_request)
        db.session.commit()
        
        # 记录申请日志
        LogService.log_operation(
            operation_type='apply',
            operation_desc=f'申请补交作业「{assignment.title}」',
            result='success'
        )
        
        flash('补交申请已提交，请等待老师审批', 'success')
        return redirect(url_for('student.dashboard'))
    
    return render_template('makeup/request_form.html', assignment=assignment)


@bp.route('/my_requests')
@login_required
def my_requests():
    """学生查看自己的补交申请"""
    requests = MakeupRequest.query.filter_by(
        student_id=current_user.id
    ).order_by(MakeupRequest.created_at.desc()).all()
    
    return render_template('makeup/my_requests.html', requests=requests)


@bp.route('/manage')
@login_required
@require_teacher_or_admin
def manage_requests():
    """老师管理补交申请"""
    status = request.args.get('status', 'pending')
    
    # 获取补交申请列表
    query = MakeupRequest.query
    
    if not current_user.is_super_admin:
        # 普通老师只能看到自己班级的申请
        from app.models import class_teacher
        teacher_classes = db.session.query(class_teacher.c.class_id).filter(
            class_teacher.c.teacher_id == current_user.id
        ).all()
        class_ids = [c[0] for c in teacher_classes]
        
        # 筛选这些班级的作业
        assignment_ids = db.session.query(Assignment.id).filter(
            Assignment.class_id.in_(class_ids)
        ).all()
        assignment_ids = [a[0] for a in assignment_ids]
        
        query = query.filter(MakeupRequest.assignment_id.in_(assignment_ids))
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    requests = query.order_by(MakeupRequest.created_at.desc()).all()
    
    return render_template('makeup/manage_requests.html', 
                         requests=requests, 
                         current_status=status)


@bp.route('/approve/<int:request_id>', methods=['POST'])
@login_required
@require_teacher_or_admin
def approve_request(request_id):
    """批准补交申请"""
    makeup_request = MakeupRequest.query.get_or_404(request_id)
    
    if makeup_request.status != 'pending':
        return jsonify({'success': False, 'message': '该申请已经处理过了'})
    
    deadline_str = request.form.get('deadline')
    if not deadline_str:
        return jsonify({'success': False, 'message': '请设置补交截止时间'})
    
    try:
        # 老师输入的是北京时间，需要转换为UTC时间
        from app.utils.helpers import BEIJING_TZ
        import pytz
        beijing_tz = pytz.timezone('Asia/Shanghai')
        # 解析为 naive datetime
        deadline_naive = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        # 设置为北京时区
        deadline_beijing = beijing_tz.localize(deadline_naive)
        # 转换为UTC时间
        deadline = deadline_beijing.astimezone(pytz.UTC).replace(tzinfo=None)
    except:
        return jsonify({'success': False, 'message': '时间格式错误'})
    
    makeup_request.status = 'approved'
    makeup_request.deadline = deadline
    makeup_request.processed_by = current_user.id
    makeup_request.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    # 记录批准日志
    student = User.query.get(makeup_request.student_id)
    assignment = Assignment.query.get(makeup_request.assignment_id)
    LogService.log_operation(
        operation_type='approve',
        operation_desc=f'批准 {student.real_name} 的补交申请：{assignment.title}',
        result='success'
    )
    
    return jsonify({'success': True, 'message': '已批准补交申请'})


@bp.route('/reject/<int:request_id>', methods=['POST'])
@login_required
@require_teacher_or_admin
def reject_request(request_id):
    """拒绝补交申请"""
    makeup_request = MakeupRequest.query.get_or_404(request_id)
    
    if makeup_request.status != 'pending':
        return jsonify({'success': False, 'message': '该申请已经处理过了'})
    
    reject_reason = request.form.get('reject_reason', '').strip()
    
    makeup_request.status = 'rejected'
    makeup_request.reject_reason = reject_reason
    makeup_request.processed_by = current_user.id
    makeup_request.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': '已拒绝补交申请'})


@bp.route('/batch_approve', methods=['POST'])
@login_required
@require_teacher_or_admin
def batch_approve():
    """批量批准补交申请"""
    request_ids = request.form.getlist('request_ids[]')
    deadline_str = request.form.get('deadline')
    
    if not request_ids:
        return jsonify({'success': False, 'message': '请选择要批准的申请'})
    
    if not deadline_str:
        return jsonify({'success': False, 'message': '请设置补交截止时间'})
    
    try:
        # 老师输入的是北京时间，需要转换为UTC时间
        from app.utils.helpers import BEIJING_TZ
        import pytz
        beijing_tz = pytz.timezone('Asia/Shanghai')
        # 解析为 naive datetime
        deadline_naive = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        # 设置为北京时区
        deadline_beijing = beijing_tz.localize(deadline_naive)
        # 转换为UTC时间
        deadline = deadline_beijing.astimezone(pytz.UTC).replace(tzinfo=None)
    except:
        return jsonify({'success': False, 'message': '时间格式错误'})
    
    # 批量更新
    updated_count = 0
    for request_id in request_ids:
        makeup_request = MakeupRequest.query.get(request_id)
        if makeup_request and makeup_request.status == 'pending':
            makeup_request.status = 'approved'
            makeup_request.deadline = deadline
            makeup_request.processed_by = current_user.id
            makeup_request.updated_at = datetime.utcnow()
            updated_count += 1
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'已批准 {updated_count} 个补交申请'})


@bp.route('/modify_deadline/<int:request_id>', methods=['POST'])
@login_required
@require_teacher_or_admin
def modify_deadline(request_id):
    """修改补交申请的截止时间"""
    from flask import current_app
    makeup_request = MakeupRequest.query.get_or_404(request_id)
    
    if makeup_request.status != 'approved':
        return jsonify({'success': False, 'message': '只能修改已批准的申请'})
    
    deadline_str = request.form.get('deadline')
    current_app.logger.info(f"[MODIFY_DEADLINE] 接收到的deadline: {deadline_str}")
    
    if not deadline_str:
        return jsonify({'success': False, 'message': '请设置补交截止时间'})
    
    try:
        # 老师输入的是北京时间，需要转换为UTC时间
        import pytz
        beijing_tz = pytz.timezone('Asia/Shanghai')
        # 解析为 naive datetime
        deadline_naive = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        current_app.logger.info(f"[MODIFY_DEADLINE] 解析后: {deadline_naive}")
        # 设置为北京时区
        deadline_beijing = beijing_tz.localize(deadline_naive)
        current_app.logger.info(f"[MODIFY_DEADLINE] 北京时间: {deadline_beijing}")
        # 转换为UTC时间
        deadline = deadline_beijing.astimezone(pytz.UTC).replace(tzinfo=None)
        current_app.logger.info(f"[MODIFY_DEADLINE] UTC时间: {deadline}")
    except Exception as e:
        current_app.logger.error(f"[MODIFY_DEADLINE] 错误: {str(e)}")
        return jsonify({'success': False, 'message': f'时间格式错误: {str(e)}'})
    
    makeup_request.deadline = deadline
    makeup_request.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': '已修改补交截止时间'})

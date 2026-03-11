"""AI 自动评分相关路由"""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Assignment, Submission
from app.services.ai_grading_service import AIGradingService
from app.utils.decorators import require_teacher_or_admin

bp = Blueprint('ai_grading', __name__, url_prefix='/api/ai-grading')


@bp.route('/check-status', methods=['GET'])
@login_required
@require_teacher_or_admin
def check_api_status():
    """检查 AI 评分 API 是否可用"""
    is_available, message = AIGradingService.check_api_available()
    return jsonify({
        'success': True,
        'available': is_available,
        'message': message
    })


@bp.route('/grade-submission/<int:submission_id>', methods=['POST'])
@login_required
@require_teacher_or_admin
def grade_submission(submission_id):
    """
    对单个提交进行 AI 评分
    
    请求参数（可选）：
    - grading_criteria: 评分标准（如果不传，使用作业默认评分标准）
    - max_score: 满分值（默认100）
    """
    submission = Submission.query.get_or_404(submission_id)
    assignment = submission.assignment
    
    # 权限检查：只有该作业的管理教师或超级管理员可以评分
    if not current_user.is_super_admin:
        # 检查是否有权限管理该作业
        if hasattr(assignment, 'class_obj') and assignment.class_obj:
            if assignment.class_obj not in current_user.teaching_classes:
                return jsonify({
                    'success': False,
                    'message': '您没有权限为该作业评分'
                }), 403
    
    # 获取评分参数
    data = request.get_json() or {}
    grading_criteria = data.get('grading_criteria') or getattr(assignment, 'grading_criteria', None)
    max_score = data.get('max_score', 100)
    
    # 检查文件是否存在
    if not submission.file_path:
        return jsonify({
            'success': False,
            'message': '该提交没有上传文件'
        })
    
    # 调用 AI 评分
    score, comment, error = AIGradingService.grade_submission_by_file(
        assignment_title=assignment.title,
        assignment_description=assignment.description,
        grading_criteria=grading_criteria,
        file_path=submission.file_path,
        max_score=max_score
    )
    
    if error:
        return jsonify({
            'success': False,
            'message': error
        })
    
    return jsonify({
        'success': True,
        'data': {
            'submission_id': submission_id,
            'ai_score': score,
            'ai_comment': comment,
            'max_score': max_score
        }
    })


@bp.route('/apply-grade/<int:submission_id>', methods=['POST'])
@login_required
@require_teacher_or_admin
def apply_ai_grade(submission_id):
    """
    应用 AI 评分结果到提交记录
    
    请求参数：
    - score: 最终分数（可以是 AI 评分，也可以是教师调整后的分数）
    - comment: 评语
    """
    submission = Submission.query.get_or_404(submission_id)
    assignment = submission.assignment
    
    # 权限检查
    if not current_user.is_super_admin:
        if hasattr(assignment, 'class_obj') and assignment.class_obj:
            if assignment.class_obj not in current_user.teaching_classes:
                return jsonify({
                    'success': False,
                    'message': '您没有权限为该作业评分'
                }), 403
    
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': '缺少评分数据'
        })
    
    score = data.get('score')
    comment = data.get('comment', '')
    
    if score is None:
        return jsonify({
            'success': False,
            'message': '缺少分数'
        })
    
    try:
        score = int(score)
        if score < 0:
            score = 0
    except (ValueError, TypeError):
        return jsonify({
            'success': False,
            'message': '分数格式错误'
        })
    
    # 更新提交记录
    submission.score = score
    submission.feedback = comment
    submission.graded_by = current_user.id
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '评分已保存',
        'data': {
            'submission_id': submission_id,
            'score': score,
            'comment': comment
        }
    })


@bp.route('/batch-grade/<int:assignment_id>', methods=['POST'])
@login_required
@require_teacher_or_admin
def batch_grade_assignment(assignment_id):
    """
    批量为作业的所有未评分提交进行 AI 评分
    
    注意：这只是生成 AI 评分建议，不会直接保存
    """
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 权限检查
    if not current_user.is_super_admin:
        if hasattr(assignment, 'class_obj') and assignment.class_obj:
            if assignment.class_obj not in current_user.teaching_classes:
                return jsonify({
                    'success': False,
                    'message': '您没有权限为该作业评分'
                }), 403
    
    data = request.get_json() or {}
    grading_criteria = data.get('grading_criteria') or getattr(assignment, 'grading_criteria', None)
    max_score = data.get('max_score', 100)
    only_ungraded = data.get('only_ungraded', True)  # 默认只评未评分的
    
    # 获取需要评分的提交
    query = Submission.query.filter_by(assignment_id=assignment_id)
    if only_ungraded:
        query = query.filter(Submission.score.is_(None))
    
    submissions = query.all()
    
    if not submissions:
        return jsonify({
            'success': True,
            'message': '没有需要评分的提交',
            'data': {'results': []}
        })
    
    results = []
    success_count = 0
    error_count = 0
    
    for submission in submissions:
        if not submission.file_path:
            results.append({
                'submission_id': submission.id,
                'student_name': submission.student.real_name if submission.student else '未知',
                'success': False,
                'error': '没有上传文件'
            })
            error_count += 1
            continue
        
        score, comment, error = AIGradingService.grade_submission_by_file(
            assignment_title=assignment.title,
            assignment_description=assignment.description,
            grading_criteria=grading_criteria,
            file_path=submission.file_path,
            max_score=max_score
        )
        
        if error:
            results.append({
                'submission_id': submission.id,
                'student_name': submission.student.real_name if submission.student else '未知',
                'success': False,
                'error': error
            })
            error_count += 1
        else:
            results.append({
                'submission_id': submission.id,
                'student_name': submission.student.real_name if submission.student else '未知',
                'success': True,
                'ai_score': score,
                'ai_comment': comment
            })
            success_count += 1
    
    return jsonify({
        'success': True,
        'message': f'批量评分完成：成功 {success_count} 个，失败 {error_count} 个',
        'data': {
            'results': results,
            'success_count': success_count,
            'error_count': error_count
        }
    })

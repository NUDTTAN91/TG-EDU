"""大作业系统路由 - Part 1: 主要功能"""
import os
import uuid
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models import User, Class, UserRole
from app.models.team import MajorAssignment, Team, TeamMember, TeamInvitation, LeaveTeamRequest
from app.utils import safe_chinese_filename, to_beijing_time, BEIJING_TZ
from app.utils.decorators import require_teacher_or_admin, require_role
from app.services import NotificationService

bp = Blueprint('major_assignment', __name__)


@bp.route('/major_assignments')
@login_required
def major_assignment_dashboard():
    """大作业管理仪表板"""
    if current_user.is_super_admin:
        major_assignments = MajorAssignment.query.order_by(MajorAssignment.created_at.desc()).all()
    elif current_user.is_teacher:
        # 查询创建的、管理的和所教班级的大作业
        teacher_class_ids = [c.id for c in current_user.teaching_classes]
        major_assignments = MajorAssignment.query.filter(
            or_(
                MajorAssignment.creator_id == current_user.id,
                MajorAssignment.teachers.any(id=current_user.id),
                MajorAssignment.class_id.in_(teacher_class_ids)
            )
        ).order_by(MajorAssignment.created_at.desc()).all()
    else:
        student_class_ids = [c.id for c in current_user.classes]
        if student_class_ids:
            major_assignments = MajorAssignment.query.filter(
                MajorAssignment.class_id.in_(student_class_ids),
                MajorAssignment.is_active == True
            ).order_by(MajorAssignment.created_at.desc()).all()
        else:
            major_assignments = []
    
    return render_template('major_assignment_dashboard.html', major_assignments=major_assignments)


@bp.route('/major_assignments/create', methods=['GET', 'POST'])
@login_required
@require_teacher_or_admin
def create_major_assignment():
    """创建大作业"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description', '')
        class_id = request.form.get('class_id')
        min_team_size = request.form.get('min_team_size', 2, type=int)
        max_team_size = request.form.get('max_team_size', 5, type=int)
        due_date_str = request.form.get('due_date')
        requirement_type = request.form.get('requirement_type', 'file')
        teacher_ids = request.form.getlist('teacher_ids')  # 获取多个教师ID
        
        if not title or not class_id:
            flash('请填写必填项')
            return redirect(url_for('major_assignment.create_major_assignment'))
        
        if min_team_size > max_team_size:
            flash('最小组队人数不能大于最大组队人数')
            return redirect(url_for('major_assignment.create_major_assignment'))
        
        due_date = None
        if due_date_str:
            try:
                # 解析北京时间字符串
                beijing_dt = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
                # 将北京时间转换为UTC时间（北京时间-8小时）
                beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
                due_date = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception as e:
                flash(f'日期格式错误: {str(e)}')
                return redirect(url_for('major_assignment.create_major_assignment'))
        
        major_assignment = MajorAssignment(
            title=title,
            description=description,
            class_id=class_id,
            creator_id=current_user.id,  # 创建者
            min_team_size=min_team_size,
            max_team_size=max_team_size,
            due_date=due_date
        )
        
        # 添加管理教师
        if teacher_ids:
            for teacher_id in teacher_ids:
                teacher = User.query.get(int(teacher_id))
                if teacher and (teacher.is_teacher or teacher.is_super_admin):
                    major_assignment.teachers.append(teacher)
        
        # 如果没有指定教师，默认添加创建者
        if not major_assignment.teachers and not current_user.is_super_admin:
            major_assignment.teachers.append(current_user)
        
        if requirement_type == 'file':
            req_file = request.files.get('requirement_file')
            if req_file and req_file.filename:
                from flask import current_app
                original_filename = req_file.filename
                safe_filename_str = safe_chinese_filename(original_filename)
                filename = f"major_req_{uuid.uuid4().hex}_{safe_filename_str}"
                file_path = os.path.join(current_app.config['APPENDIX_FOLDER'], filename)
                req_file.save(file_path)
                major_assignment.requirement_file_path = file_path
                major_assignment.requirement_file_name = original_filename
        else:
            req_url = request.form.get('requirement_url')
            if req_url:
                major_assignment.requirement_url = req_url
        
        db.session.add(major_assignment)
        db.session.commit()
        
        # 发送通知给班级学生
        class_obj = Class.query.get(class_id)
        if class_obj:
            students = class_obj.students
            for student in students:
                NotificationService.create_notification(
                    sender_id=current_user.id,
                    receiver_id=student.id,
                    title=f'新大作业：{title}',
                    content=f'{current_user.real_name} 老师布置了新大作业「{title}」，请组建{min_team_size}-{max_team_size}人团队。' + 
                            (f' 截止时间：{to_beijing_time(due_date).strftime("%Y-%m-%d %H:%M")}' if due_date else ''),
                    notification_type='major_assignment'
                )
        
        flash('大作业布置成功！')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    # GET请求
    if current_user.is_super_admin:
        classes = Class.query.filter_by(is_active=True).all()
        # 超级管理员可以选择所有教师
        teachers = User.query.filter(
            (User.role == UserRole.TEACHER) | (User.role == UserRole.SUPER_ADMIN)
        ).all()
    else:
        classes = current_user.teaching_classes
        # 普通教师只能选择自己
        teachers = [current_user]
    
    return render_template('create_major_assignment.html', classes=classes, teachers=teachers)


@bp.route('/major_assignments/<int:assignment_id>/teams')
@login_required
@require_teacher_or_admin
def view_major_assignment_teams(assignment_id):
    """查看大作业的分组情况"""
    major_assignment = MajorAssignment.query.get_or_404(assignment_id)
    
    # 使用can_manage方法检查权限
    if not major_assignment.can_manage(current_user):
        flash('您没有权限查看此大作业')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    teams = major_assignment.teams
    total_teams = len(teams)
    confirmed_teams = len([t for t in teams if t.status == 'confirmed'])
    pending_teams = len([t for t in teams if t.status == 'pending'])
    
    return render_template('view_major_assignment_teams.html',
                         major_assignment=major_assignment,
                         teams=teams,
                         total_teams=total_teams,
                         confirmed_teams=confirmed_teams,
                         pending_teams=pending_teams)


@bp.route('/major_assignments/<int:assignment_id>/student')
@login_required
@require_role(UserRole.STUDENT)
def student_major_assignment_detail(assignment_id):
    """学生查看大作业详情和管理团队"""
    major_assignment = MajorAssignment.query.get_or_404(assignment_id)
    
    if major_assignment.class_id not in [c.id for c in current_user.classes]:
        flash('您不在该班级中')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    my_team = None
    for team in major_assignment.teams:
        if team.leader_id == current_user.id:
            my_team = team
            break
        for member in team.members:
            if member.user_id == current_user.id:
                my_team = team
                break
        if my_team:
            break
    
    classmates = []
    if my_team and my_team.leader_id == current_user.id:
        existing_member_ids = {current_user.id}
        existing_member_ids.update([m.user_id for m in my_team.members])
        
        all_team_member_ids = set()
        for team in major_assignment.teams:
            all_team_member_ids.add(team.leader_id)
            all_team_member_ids.update([m.user_id for m in team.members])
        
        class_obj = Class.query.get(major_assignment.class_id)
        classmates = [s for s in class_obj.students 
                     if s.id not in existing_member_ids and s.id not in all_team_member_ids]
    
    return render_template('student_major_assignment_detail.html',
                         major_assignment=major_assignment,
                         my_team=my_team,
                         classmates=classmates)


@bp.route('/major_assignments/<int:assignment_id>/create_team', methods=['POST'])
@login_required
@require_role(UserRole.STUDENT)
def create_team(assignment_id):
    """学生创建团队"""
    major_assignment = MajorAssignment.query.get_or_404(assignment_id)
    team_name = request.form.get('team_name')
    
    for team in major_assignment.teams:
        if team.leader_id == current_user.id:
            flash('您已经是一个团队的组长')
            return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=assignment_id))
        for member in team.members:
            if member.user_id == current_user.id:
                flash('您已经加入了一个团队')
                return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=assignment_id))
    
    team = Team(
        name=team_name,
        major_assignment_id=assignment_id,
        leader_id=current_user.id
    )
    db.session.add(team)
    db.session.commit()
    
    flash('团队创建成功！')
    return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=assignment_id))


@bp.route('/major_assignments/<int:assignment_id>/requirement')
@login_required
def download_major_assignment_requirement(assignment_id):
    """下载大作业要求文件"""
    major_assignment = MajorAssignment.query.get_or_404(assignment_id)
    
    if not major_assignment.requirement_file_path:
        flash('没有要求文件')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    if not os.path.exists(major_assignment.requirement_file_path):
        flash('文件不存在')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    return send_from_directory(
        directory=os.path.dirname(major_assignment.requirement_file_path),
        path=os.path.basename(major_assignment.requirement_file_path),
        as_attachment=True,
        download_name=major_assignment.requirement_file_name
    )


@bp.route('/major_assignments/<int:assignment_id>/edit', methods=['GET', 'POST'])
@login_required
@require_teacher_or_admin
def edit_major_assignment(assignment_id):
    """编辑大作业"""
    major_assignment = MajorAssignment.query.get_or_404(assignment_id)
    
    # 使用can_manage方法检查权限
    if not major_assignment.can_manage(current_user):
        flash('您没有权限编辑此大作业')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    if request.method == 'POST':
        major_assignment.title = request.form.get('title')
        major_assignment.description = request.form.get('description', '')
        major_assignment.min_team_size = request.form.get('min_team_size', 2, type=int)
        major_assignment.max_team_size = request.form.get('max_team_size', 5, type=int)
        teacher_ids = request.form.getlist('teacher_ids')  # 获取多个教师ID
        
        due_date_str = request.form.get('due_date')
        if due_date_str:
            try:
                beijing_dt = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
                beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
                major_assignment.due_date = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception as e:
                flash(f'日期格式错误: {str(e)}')
                return redirect(url_for('major_assignment.edit_major_assignment', assignment_id=assignment_id))
        
        # 更新管理教师（只有超级管理员和创建者可以修改）
        if current_user.is_super_admin or current_user.id == major_assignment.creator_id:
            # 清空现有管理教师
            major_assignment.teachers = []
            
            # 添加新的管理教师
            if teacher_ids:
                for teacher_id in teacher_ids:
                    teacher = User.query.get(int(teacher_id))
                    if teacher and (teacher.is_teacher or teacher.is_super_admin):
                        major_assignment.teachers.append(teacher)
            
            # 如果没有指定教师且非超级管理员，默认添加创建者
            if not major_assignment.teachers and not current_user.is_super_admin:
                creator = User.query.get(major_assignment.creator_id)
                if creator:
                    major_assignment.teachers.append(creator)
        
        db.session.commit()
        flash('大作业修改成功！')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    # GET请求 - 准备教师列表
    if current_user.is_super_admin:
        teachers = User.query.filter(
            (User.role == UserRole.TEACHER) | (User.role == UserRole.SUPER_ADMIN)
        ).all()
    else:
        # 普通教师只能选择自己
        teachers = [current_user]
    
    # 将截止时间转换为北京时间（用于表单显示）
    due_date_beijing = None
    if major_assignment.due_date:
        due_date_beijing = to_beijing_time(major_assignment.due_date)
    
    return render_template('edit_major_assignment.html', 
                         major_assignment=major_assignment,
                         teachers=teachers,
                         due_date_beijing=due_date_beijing)


@bp.route('/teams/<int:team_id>/invite', methods=['POST'])
@login_required
def invite_team_members(team_id):
    """组长邀请成员加入团队"""
    team = Team.query.get_or_404(team_id)
    
    if team.leader_id != current_user.id:
        flash('只有组长才能邀请成员')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    invitee_ids = request.form.getlist('invitee_ids')
    
    for invitee_id in invitee_ids:
        invitee = User.query.get(int(invitee_id))
        if not invitee:
            continue
        
        in_team = False
        for t in team.major_assignment.teams:
            if t.leader_id == invitee.id or any(m.user_id == invitee.id for m in t.members):
                flash(f'{invitee.real_name} 已经有团队了')
                in_team = True
                break
        
        if in_team:
            continue
        
        invitation = TeamInvitation(
            team_id=team_id,
            inviter_id=current_user.id,
            invitee_id=invitee.id
        )
        db.session.add(invitation)
        
        NotificationService.create_notification(
            sender_id=current_user.id,
            receiver_id=invitee.id,
            title=f'团队邀请：{team.name}',
            content=f'{current_user.real_name} 邀请您加入团队「{team.name}」，大作业：{team.major_assignment.title}',
            notification_type='team_invitation'
        )
    
    db.session.commit()
    flash('邀请已发送')
    return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))


@bp.route('/teams/<int:team_id>/confirm', methods=['POST'])
@login_required
@require_teacher_or_admin
def confirm_team(team_id):
    """教师确认团队"""
    team = Team.query.get_or_404(team_id)
    
    # 检查权限
    if not team.major_assignment.can_manage(current_user):
        flash('您没有权限确认此团队')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    team.status = 'confirmed'
    team.confirmed_at = datetime.utcnow()
    team.confirmed_by = current_user.id
    db.session.commit()
    
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=team.leader_id,
        title='团队已确认',
        content=f'您的团队「{team.name}」已被 {current_user.real_name} 确认',
        notification_type='system'
    )
    
    flash('团队已确认')
    return redirect(url_for('major_assignment.view_major_assignment_teams', assignment_id=team.major_assignment_id))


@bp.route('/teams/<int:team_id>/reject', methods=['POST'])
@login_required
@require_teacher_or_admin
def reject_team(team_id):
    """教师拒绝团队"""
    team = Team.query.get_or_404(team_id)
    
    # 检查权限
    if not team.major_assignment.can_manage(current_user):
        flash('您没有权限拒绝此团队')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    reject_reason = request.form.get('reject_reason', '')
    
    team.status = 'rejected'
    db.session.commit()
    
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=team.leader_id,
        title='团队被拒绝',
        content=f'您的团队「{team.name}」被拒绝。原因：{reject_reason}',
        notification_type='system'
    )
    
    flash('团队已拒绝')
    return redirect(url_for('major_assignment.view_major_assignment_teams', assignment_id=team.major_assignment_id))


@bp.route('/teams/<int:team_id>/leave', methods=['POST'])
@login_required
def request_leave_team(team_id):
    """申请退组"""
    team = Team.query.get_or_404(team_id)
    reason = request.form.get('reason')
    
    is_member = any(member.user_id == current_user.id for member in team.members)
    
    if not is_member:
        flash('您不是该团队成员')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    leave_request = LeaveTeamRequest(
        team_id=team_id,
        member_id=current_user.id,
        reason=reason
    )
    db.session.add(leave_request)
    db.session.commit()
    
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=team.leader_id,
        title='退组申请',
        content=f'{current_user.real_name} 申请退出团队「{team.name}」。原因：{reason}',
        notification_type='leave_request'
    )
    
    flash('退组申请已提交，等待组长审批')
    return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))


@bp.route('/team_invitations/<int:invitation_id>/accept', methods=['POST'])
@login_required
def accept_team_invitation(invitation_id):
    """接受团队邀请"""
    invitation = TeamInvitation.query.get_or_404(invitation_id)
    
    if invitation.invitee_id != current_user.id:
        flash('无效的操作')
        return redirect(url_for('notification.notifications'))
    
    if invitation.status != 'pending':
        flash('该邀请已处理')
        return redirect(url_for('notification.notifications'))
    
    team = invitation.team
    for t in team.major_assignment.teams:
        if t.leader_id == current_user.id or any(m.user_id == current_user.id for m in t.members):
            flash('您已经有团队了')
            invitation.status = 'cancelled'
            db.session.commit()
            return redirect(url_for('notification.notifications'))
    
    team_member = TeamMember(team_id=team.id, user_id=current_user.id)
    db.session.add(team_member)
    
    invitation.status = 'accepted'
    invitation.responded_at = datetime.utcnow()
    db.session.commit()
    
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=team.leader_id,
        title='邀请已接受',
        content=f'{current_user.real_name} 已接受您的团队邀请，加入了团队「{team.name}」',
        notification_type='system'
    )
    
    flash('成功加入团队！')
    return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))


@bp.route('/team_invitations/<int:invitation_id>/reject', methods=['POST'])
@login_required
def reject_team_invitation(invitation_id):
    """拒绝团队邀请"""
    invitation = TeamInvitation.query.get_or_404(invitation_id)
    
    if invitation.invitee_id != current_user.id:
        flash('无效的操作')
        return redirect(url_for('notification.notifications'))
    
    if invitation.status != 'pending':
        flash('该邀请已处理')
        return redirect(url_for('notification.notifications'))
    
    invitation.status = 'rejected'
    invitation.responded_at = datetime.utcnow()
    db.session.commit()
    
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=invitation.team.leader_id,
        title='邀请被拒绝',
        content=f'{current_user.real_name} 拒绝了您的团队邀请',
        notification_type='system'
    )
    
    flash('已拒绝邀请')
    return redirect(url_for('notification.notifications'))


@bp.route('/leave_requests/<int:request_id>/approve_by_leader', methods=['POST'])
@login_required
def approve_leave_request_by_leader(request_id):
    """组长批准退组请求"""
    leave_request = LeaveTeamRequest.query.get_or_404(request_id)
    team = leave_request.team
    
    if team.leader_id != current_user.id:
        flash('只有组长才能处理退组请求')
        return redirect(url_for('notification.notifications'))
    
    if leave_request.status != 'pending_leader':
        flash('该请求已处理')
        return redirect(url_for('notification.notifications'))
    
    leave_request.status = 'approved'
    leave_request.leader_responded_at = datetime.utcnow()
    leave_request.reviewer_id = current_user.id
    
    member_to_remove = TeamMember.query.filter_by(team_id=team.id, user_id=leave_request.member_id).first()
    if member_to_remove:
        db.session.delete(member_to_remove)
    
    db.session.commit()
    
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=leave_request.member_id,
        title='退组申请已批准',
        content=f'组长已批准您退出团队「{team.name}」',
        notification_type='system'
    )
    
    flash('已批准退组申请')
    return redirect(url_for('notification.notifications'))


@bp.route('/leave_requests/<int:request_id>/reject_by_leader', methods=['POST'])
@login_required
def reject_leave_request_by_leader(request_id):
    """组长拒绝退组请求"""
    leave_request = LeaveTeamRequest.query.get_or_404(request_id)
    team = leave_request.team
    
    if team.leader_id != current_user.id:
        flash('只有组长才能处理退组请求')
        return redirect(url_for('notification.notifications'))
    
    if leave_request.status != 'pending_leader':
        flash('该请求已处理')
        return redirect(url_for('notification.notifications'))
    
    review_comment = request.form.get('review_comment', '')
    
    leave_request.status = 'leader_rejected'
    leave_request.leader_responded_at = datetime.utcnow()
    leave_request.reviewer_id = current_user.id
    leave_request.review_comment = review_comment
    db.session.commit()
    
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=leave_request.member_id,
        title='退组申请被拒绝',
        content=f'组长拒绝了您的退组申请。理由：{review_comment}\n您可以提升权限请求教师处理。',
        notification_type='system'
    )
    
    flash('已拒绝退组申请')
    return redirect(url_for('notification.notifications'))


@bp.route('/leave_requests/<int:request_id>/escalate', methods=['POST'])
@login_required
def escalate_leave_request(request_id):
    """提升权限，请求教师处理退组"""
    leave_request = LeaveTeamRequest.query.get_or_404(request_id)
    
    if leave_request.member_id != current_user.id:
        flash('无效的操作')
        return redirect(url_for('notification.notifications'))
    
    if leave_request.status != 'leader_rejected':
        flash('只有被组长拒绝的申请才能提升权限')
        return redirect(url_for('notification.notifications'))
    
    leave_request.status = 'pending_teacher'
    db.session.commit()
    
    # 通知所有管理教师
    major_assignment = leave_request.team.major_assignment
    for teacher in major_assignment.teachers:
        NotificationService.create_notification(
            sender_id=current_user.id,
            receiver_id=teacher.id,
            title='退组申请提升权限',
            content=f'{current_user.real_name} 请求您处理退组申请（团队：{leave_request.team.name}）。原因：{leave_request.reason}',
            notification_type='leave_request'
        )
    
    flash('已提升权限，等待教师处理')
    return redirect(url_for('notification.notifications'))


@bp.route('/leave_requests/<int:request_id>/approve_by_teacher', methods=['POST'])
@login_required
@require_teacher_or_admin
def approve_leave_request_by_teacher(request_id):
    """教师批准退组请求"""
    leave_request = LeaveTeamRequest.query.get_or_404(request_id)
    team = leave_request.team
    
    # 检查权限
    if not team.major_assignment.can_manage(current_user):
        flash('您没有权限处理此请求')
        return redirect(url_for('notification.notifications'))
    
    if leave_request.status != 'pending_teacher':
        flash('该请求已处理')
        return redirect(url_for('notification.notifications'))
    
    leave_request.status = 'approved'
    leave_request.teacher_responded_at = datetime.utcnow()
    leave_request.reviewer_id = current_user.id
    
    member_to_remove = TeamMember.query.filter_by(team_id=team.id, user_id=leave_request.member_id).first()
    if member_to_remove:
        db.session.delete(member_to_remove)
    
    db.session.commit()
    
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=leave_request.member_id,
        title='退组申请已批准',
        content=f'教师已批准您退出团队「{team.name}」',
        notification_type='system'
    )
    
    flash('已批准退组申请')
    return redirect(url_for('notification.notifications'))


@bp.route('/leave_requests/<int:request_id>/reject_by_teacher', methods=['POST'])
@login_required
@require_teacher_or_admin
def reject_leave_request_by_teacher(request_id):
    """教师拒绝退组请求"""
    leave_request = LeaveTeamRequest.query.get_or_404(request_id)
    team = leave_request.team
    
    # 检查权限
    if not team.major_assignment.can_manage(current_user):
        flash('您没有权限处理此请求')
        return redirect(url_for('notification.notifications'))
    
    if leave_request.status != 'pending_teacher':
        flash('该请求已处理')
        return redirect(url_for('notification.notifications'))
    
    review_comment = request.form.get('review_comment', '')
    
    leave_request.status = 'teacher_rejected'
    leave_request.teacher_responded_at = datetime.utcnow()
    leave_request.reviewer_id = current_user.id
    leave_request.review_comment = review_comment
    db.session.commit()
    
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=leave_request.member_id,
        title='退组申请被教师拒绝',
        content=f'教师拒绝了您的退组申请。理由：{review_comment}',
        notification_type='system'
    )
    
    flash('已拒绝退组申请')
    return redirect(url_for('notification.notifications'))

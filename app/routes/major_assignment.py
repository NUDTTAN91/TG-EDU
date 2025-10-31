"""大作业系统路由 - Part 1: 主要功能"""
import os
import uuid
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models import User, Class, UserRole
from app.models.team import MajorAssignment, Team, TeamMember, TeamInvitation, LeaveTeamRequest, DissolveTeamRequest
from app.models.team import MajorAssignmentAttachment, MajorAssignmentLink, Stage
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
    # 普通教师权限检查：必须有班级或导入过学生才能创建大作业
    if current_user.is_teacher and not current_user.is_super_admin:
        # 检查是否有负责的班级
        has_classes = len(current_user.teaching_classes) > 0
        # 检查是否导入过学生
        has_created_students = User.query.filter_by(
            role=UserRole.STUDENT, 
            created_by=current_user.id
        ).first() is not None
        
        if not has_classes and not has_created_students:
            flash('您还没有班级或学生，无法创建大作业。请先在"学生管理"中导入学生，或联系管理员为您分配班级。')
            return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description', '')
        class_id = request.form.get('class_id')
        min_team_size = request.form.get('min_team_size', 2, type=int)
        max_team_size = request.form.get('max_team_size', 5, type=int)
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        requirement_type = request.form.get('requirement_type', 'file')
        teacher_ids = request.form.getlist('teacher_ids')  # 获取多个教师ID
        
        if not title or not class_id:
            flash('请填写必填项')
            return redirect(url_for('major_assignment.create_major_assignment'))
        
        if min_team_size > max_team_size:
            flash('最小组队人数不能大于最大组队人数')
            return redirect(url_for('major_assignment.create_major_assignment'))
        
        # 处理开始日期
        start_date = None
        if start_date_str:
            try:
                beijing_dt = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
                beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
                start_date = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception as e:
                flash(f'开始日期格式错误: {str(e)}')
                return redirect(url_for('major_assignment.create_major_assignment'))
        
        # 处理结束日期
        end_date = None
        if end_date_str:
            try:
                beijing_dt = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
                beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
                end_date = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception as e:
                flash(f'结束日期格式错误: {str(e)}')
                return redirect(url_for('major_assignment.create_major_assignment'))
        
        # 验证日期逻辑
        if start_date and end_date and start_date >= end_date:
            flash('开始日期必须早于结束日期')
            return redirect(url_for('major_assignment.create_major_assignment'))
        
        major_assignment = MajorAssignment(
            title=title,
            description=description,
            class_id=class_id,
            creator_id=current_user.id,
            min_team_size=min_team_size,
            max_team_size=max_team_size,
            start_date=start_date,
            end_date=end_date
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
        
        db.session.add(major_assignment)
        db.session.flush()  # 先flush获取ID
        
        # 处理多个附件
        requirement_files = request.files.getlist('requirement_files')  # 支持多个文件
        if requirement_files:
            from flask import current_app
            for req_file in requirement_files:
                if req_file and req_file.filename:
                    original_filename = req_file.filename
                    safe_filename_str = safe_chinese_filename(original_filename)
                    filename = f"major_req_{uuid.uuid4().hex}_{safe_filename_str}"
                    file_path = os.path.join(current_app.config['APPENDIX_FOLDER'], filename)
                    req_file.save(file_path)
                    
                    # 获取文件大小
                    file_size = os.path.getsize(file_path)
                    
                    # 创建附件记录
                    attachment = MajorAssignmentAttachment(
                        major_assignment_id=major_assignment.id,
                        file_path=file_path,
                        original_filename=original_filename,
                        file_size=file_size,
                        uploaded_by=current_user.id
                    )
                    db.session.add(attachment)
        
        # 处理多个链接
        requirement_urls = request.form.getlist('requirement_urls')  # 支持多个链接
        requirement_url_titles = request.form.getlist('requirement_url_titles')  # 链接标题
        
        for i, req_url in enumerate(requirement_urls):
            if req_url and req_url.strip():
                url_title = requirement_url_titles[i] if i < len(requirement_url_titles) else ''
                
                # 创建链接记录
                link = MajorAssignmentLink(
                    major_assignment_id=major_assignment.id,
                    url=req_url.strip(),
                    title=url_title.strip() if url_title else f'链接{i+1}',
                    created_by=current_user.id
                )
                db.session.add(link)
        
        # 兼容旧系统：如果使用旧的单文件/单链接方式
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
        
        # 创建预设阶段
        from app.models.team import Stage
        
        # 组队阶段
        if request.form.get('add_team_formation_stage'):
            team_formation_start_str = request.form.get('team_formation_start')
            team_formation_end_str = request.form.get('team_formation_end')
            
            if team_formation_start_str and team_formation_end_str:
                try:
                    # 处理开始时间
                    beijing_dt = datetime.strptime(team_formation_start_str, '%Y-%m-%dT%H:%M')
                    beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
                    tf_start = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
                    
                    # 处理结束时间
                    beijing_dt = datetime.strptime(team_formation_end_str, '%Y-%m-%dT%H:%M')
                    beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
                    tf_end = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
                    
                    # 验证时间
                    if tf_start < tf_end:
                        team_formation_stage = Stage(
                            major_assignment_id=major_assignment.id,
                            name='组队阶段',
                            description='学生自由组队，阶段结束时系统将自动为未组队学生分配团队',
                            stage_type='team_formation',
                            start_date=tf_start,
                            end_date=tf_end,
                            order=1
                        )
                        db.session.add(team_formation_stage)
                except Exception as e:
                    print(f'创建组队阶段失败: {str(e)}')
        
        # 分工阶段
        if request.form.get('add_division_stage'):
            division_start_str = request.form.get('division_start')
            division_end_str = request.form.get('division_end')
            
            if division_start_str and division_end_str:
                try:
                    # 处理开始时间
                    beijing_dt = datetime.strptime(division_start_str, '%Y-%m-%dT%H:%M')
                    beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
                    div_start = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
                    
                    # 处理结束时间
                    beijing_dt = datetime.strptime(division_end_str, '%Y-%m-%dT%H:%M')
                    beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
                    div_end = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
                    
                    # 验证时间
                    if div_start < div_end:
                        division_stage = Stage(
                            major_assignment_id=major_assignment.id,
                            name='分工阶段',
                            description='团队成员分配角色，阶段结束时系统将自动分配未分配的必须角色',
                            stage_type='division',
                            start_date=div_start,
                            end_date=div_end,
                            order=2
                        )
                        db.session.add(division_stage)
                except Exception as e:
                    print(f'创建分工阶段失败: {str(e)}')
        
        db.session.commit()
        
        # 发送通知给班级学生
        class_obj = Class.query.get(class_id)
        if class_obj:
            students = class_obj.students
            # 构建时间提示
            time_info = ''
            if start_date and end_date:
                time_info = f' 作业时间：{to_beijing_time(start_date).strftime("%Y-%m-%d")} 至 {to_beijing_time(end_date).strftime("%Y-%m-%d")}'
            
            for student in students:
                NotificationService.create_notification(
                    sender_id=current_user.id,
                    receiver_id=student.id,
                    title=f'新大作业：{title}',
                    content=f'{current_user.real_name} 老师布置了新大作业「{title}」，请组建{min_team_size}-{max_team_size}人团队。{time_info}',
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
    from app.models.team import Stage
    
    major_assignment = MajorAssignment.query.get_or_404(assignment_id)
    
    # 使用can_manage方法检查权限
    if not major_assignment.can_manage(current_user):
        flash('您没有权限查看此大作业')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    teams = major_assignment.teams
    total_teams = len(teams)
    confirmed_teams = len([t for t in teams if t.status == 'confirmed'])
    pending_teams = len([t for t in teams if t.status == 'pending'])
    
    # 统计已组队学生数
    total_students = 0
    for team in teams:
        total_students += team.get_member_count()
    
    # 获取所有阶段
    stages = Stage.query.filter_by(
        major_assignment_id=assignment_id
    ).order_by(Stage.order).all()
    
    # 获取分工阶段
    division_stages = Stage.query.filter_by(
        major_assignment_id=assignment_id,
        stage_type='division'
    ).order_by(Stage.order).all()
    
    return render_template('view_major_assignment_teams.html',
                         major_assignment=major_assignment,
                         teams=teams,
                         total_teams=total_teams,
                         confirmed_teams=confirmed_teams,
                         pending_teams=pending_teams,
                         total_students=total_students,
                         stages=stages,
                         division_stages=division_stages)


@bp.route('/major_assignments/<int:assignment_id>/student')
@login_required
@require_role(UserRole.STUDENT)
def student_major_assignment_detail(assignment_id):
    """学生查看大作业详情和管理团队"""
    from app.models.team import Stage
    
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
    
    # 获取邀请记录（只有组长才能查看）
    team_invitations = []
    if my_team and my_team.leader_id == current_user.id:
        # 查询该团队的所有邀请
        team_invitations = TeamInvitation.query.filter_by(
            team_id=my_team.id
        ).order_by(TeamInvitation.created_at.desc()).all()
    
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
    
    # 获取分工阶段
    division_stages = Stage.query.filter_by(
        major_assignment_id=assignment_id,
        stage_type='division'
    ).order_by(Stage.order).all()
    
    # 获取组队阶段
    team_formation_stages = Stage.query.filter_by(
        major_assignment_id=assignment_id,
        stage_type='team_formation'
    ).order_by(Stage.order).all()
    
    # 如果有团队，获取任务（不再依赖任务阶段）
    my_tasks = []
    if my_team:
        from app.models.team import TeamTask
        my_tasks = TeamTask.query.filter(
            TeamTask.team_id == my_team.id
        ).order_by(TeamTask.created_at).all()
    
    # 获取所有阶段（按顺序排列）
    all_stages = Stage.query.filter_by(
        major_assignment_id=assignment_id
    ).order_by(Stage.order).all()
    
    return render_template('student_major_assignment_detail.html',
                         major_assignment=major_assignment,
                         my_team=my_team,
                         classmates=classmates,
                         team_invitations=team_invitations,
                         division_stages=division_stages,
                         team_formation_stages=team_formation_stages,
                         my_tasks=my_tasks,
                         all_stages=all_stages)


@bp.route('/major_assignments/<int:assignment_id>/create_team', methods=['POST'])
@login_required
@require_role(UserRole.STUDENT)
def create_team(assignment_id):
    """学生创建团队"""
    major_assignment = MajorAssignment.query.get_or_404(assignment_id)
    
    # 检查是否已经在团队中
    for team in major_assignment.teams:
        if team.leader_id == current_user.id:
            flash('您已经是一个团队的组长')
            return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=assignment_id))
        for member in team.members:
            if member.user_id == current_user.id:
                flash('您已经加入了一个团队')
                return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=assignment_id))
    
    # 自动生成团队名称：组长姓名 + 的团队
    team_name = f'{current_user.real_name}的团队'
    
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
    """下载大作业要求文件（旧系统，兼容保留）"""
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


@bp.route('/major_assignments/attachment/<int:attachment_id>/download')
@login_required
def download_major_assignment_attachment(attachment_id):
    """下载大作业附件（新系统）"""
    attachment = MajorAssignmentAttachment.query.get_or_404(attachment_id)
    
    if not os.path.exists(attachment.file_path):
        flash('附件文件不存在')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    return send_from_directory(
        directory=os.path.dirname(attachment.file_path),
        path=os.path.basename(attachment.file_path),
        as_attachment=True,
        download_name=attachment.original_filename
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
        
        # 处理开始日期
        start_date_str = request.form.get('start_date')
        if start_date_str:
            try:
                beijing_dt = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
                beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
                major_assignment.start_date = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception as e:
                flash(f'开始日期格式错误: {str(e)}')
                return redirect(url_for('major_assignment.edit_major_assignment', assignment_id=assignment_id))
        else:
            major_assignment.start_date = None
        
        # 处理结束日期
        end_date_str = request.form.get('end_date')
        if end_date_str:
            try:
                beijing_dt = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
                beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
                major_assignment.end_date = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception as e:
                flash(f'结束日期格式错误: {str(e)}')
                return redirect(url_for('major_assignment.edit_major_assignment', assignment_id=assignment_id))
        else:
            major_assignment.end_date = None
        
        # 验证日期逻辑
        if major_assignment.start_date and major_assignment.end_date:
            if major_assignment.start_date >= major_assignment.end_date:
                flash('开始日期必须早于结束日期')
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
        
        # 处理多个新附件
        requirement_files = request.files.getlist('requirement_files')
        if requirement_files:
            from flask import current_app
            for req_file in requirement_files:
                if req_file and req_file.filename:
                    original_filename = req_file.filename
                    safe_filename_str = safe_chinese_filename(original_filename)
                    filename = f"major_req_{uuid.uuid4().hex}_{safe_filename_str}"
                    file_path = os.path.join(current_app.config['APPENDIX_FOLDER'], filename)
                    req_file.save(file_path)
                    
                    # 获取文件大小
                    file_size = os.path.getsize(file_path)
                    
                    # 创建附件记录
                    attachment = MajorAssignmentAttachment(
                        major_assignment_id=major_assignment.id,
                        file_path=file_path,
                        original_filename=original_filename,
                        file_size=file_size,
                        uploaded_by=current_user.id
                    )
                    db.session.add(attachment)
        
        # 处理多个新链接
        requirement_urls = request.form.getlist('requirement_urls')
        requirement_url_titles = request.form.getlist('requirement_url_titles')
        
        for i, req_url in enumerate(requirement_urls):
            if req_url and req_url.strip():
                url_title = requirement_url_titles[i] if i < len(requirement_url_titles) else ''
                
                # 创建链接记录
                link = MajorAssignmentLink(
                    major_assignment_id=major_assignment.id,
                    url=req_url.strip(),
                    title=url_title.strip() if url_title else f'链接{i+1}',
                    created_by=current_user.id
                )
                db.session.add(link)
        
        # 处理删除附件
        delete_attachment_ids = request.form.getlist('delete_attachments')
        if delete_attachment_ids:
            for att_id in delete_attachment_ids:
                attachment = MajorAssignmentAttachment.query.get(int(att_id))
                if attachment and attachment.major_assignment_id == major_assignment.id:
                    # 删除文件
                    if os.path.exists(attachment.file_path):
                        try:
                            os.remove(attachment.file_path)
                        except Exception as e:
                            print(f"删除附件文件失败: {e}")
                    db.session.delete(attachment)
        
        # 处理删除链接
        delete_link_ids = request.form.getlist('delete_links')
        if delete_link_ids:
            for link_id in delete_link_ids:
                link = MajorAssignmentLink.query.get(int(link_id))
                if link and link.major_assignment_id == major_assignment.id:
                    db.session.delete(link)
        
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
    
    # 将日期转换为北京时间（用于表单显示）
    start_date_beijing = None
    end_date_beijing = None
    
    if major_assignment.start_date:
        start_date_beijing = to_beijing_time(major_assignment.start_date)
    
    if major_assignment.end_date:
        end_date_beijing = to_beijing_time(major_assignment.end_date)
    
    return render_template('edit_major_assignment.html', 
                         major_assignment=major_assignment,
                         teachers=teachers,
                         start_date_beijing=start_date_beijing,
                         end_date_beijing=end_date_beijing)


@bp.route('/teams/<int:team_id>/invite', methods=['POST'])
@login_required
def invite_team_members(team_id):
    """组长邀请成员加入团队（通过姓名和学号验证）"""
    team = Team.query.get_or_404(team_id)
    
    if team.leader_id != current_user.id:
        flash('只有组长才能邀请成员')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 检查分组阶段是否已完成
    team_formation_stage = Stage.query.filter_by(
        major_assignment_id=team.major_assignment_id,
        stage_type='team_formation'
    ).first()
    
    if team_formation_stage and team_formation_stage.status == 'completed':
        flash('当前操作不在阶段，请联系管理员或老师')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 检查团队是否已锁定
    if team.is_locked:
        flash('团队已锁定，无法邀请成员。请联系老师调整')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 获取输入的姓名和学号
    invitee_name = request.form.get('invitee_name', '').strip()
    invitee_number = request.form.get('invitee_number', '').strip()
    
    if not invitee_name or not invitee_number:
        flash('请填写同学的姓名和学号')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 查找匹配的学生（姓名和学号必须同时匹配）
    invitee = User.query.filter(
        User.real_name == invitee_name,
        User.student_id == invitee_number,
        User.role == UserRole.STUDENT
    ).first()
    
    if not invitee:
        flash(f'找不到姓名为「{invitee_name}」、学号为「{invitee_number}」的学生，请检查后重试')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 检查是否在同一个班级
    major_assignment = team.major_assignment
    class_obj = Class.query.get(major_assignment.class_id)
    if invitee not in class_obj.students:
        flash(f'{invitee.real_name} 不在该大作业的班级中')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 检查是否已经在团队中
    for t in major_assignment.teams:
        if t.leader_id == invitee.id:
            flash(f'{invitee.real_name} 已经是其他团队的组长')
            return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
        for m in t.members:
            if m.user_id == invitee.id:
                flash(f'{invitee.real_name} 已经加入了其他团队')
                return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 检查是否已经发送过邀请
    existing_invitation = TeamInvitation.query.filter_by(
        team_id=team_id,
        invitee_id=invitee.id,
        status='pending'
    ).first()
    
    if existing_invitation:
        flash(f'已经向 {invitee.real_name} 发送过邀请，请等待对方回应')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 创建邀请
    invitation = TeamInvitation(
        team_id=team_id,
        inviter_id=current_user.id,
        invitee_id=invitee.id
    )
    db.session.add(invitation)
    
    # 发送通知
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=invitee.id,
        title=f'团队邀请：{team.name}',
        content=f'{current_user.real_name} 邀请您加入团队「{team.name}」，大作业：{team.major_assignment.title}',
        notification_type='team_invitation'
    )
    
    db.session.commit()
    flash(f'已向 {invitee.real_name} 发送邀请')
    return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))


@bp.route('/teams/<int:team_id>/request_confirmation', methods=['POST'])
@login_required
def request_team_confirmation(team_id):
    """组长请求确认团队"""
    team = Team.query.get_or_404(team_id)
    
    # 检查是否是组长
    if team.leader_id != current_user.id:
        flash('只有组长才能请求确认')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 检查团队状态
    if team.status == 'confirmed':
        flash('团队已经被确认')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    if team.confirmation_requested_at:
        flash('已经发送过确认请求，请等待老师处理')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 检查人数是否符合要求
    is_size_valid = team.is_size_valid()
    confirmation_reason = request.form.get('confirmation_reason', '').strip()
    
    if not is_size_valid:
        # 人数不符合要求，必须填写理由
        if not confirmation_reason:
            flash(f'团队人数不符合要求（需要{team.major_assignment.min_team_size}-{team.major_assignment.max_team_size}人，当前{team.get_member_count()}人），请填写申请理由')
            return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
        
        # 保存申请理由
        team.confirmation_request_reason = confirmation_reason
        team.size_exception_reason = confirmation_reason  # 兼容旧字段
    
    # 记录请求确认时间
    team.confirmation_requested_at = datetime.utcnow()
    team.status = 'pending'  # 设置为待确认
    db.session.commit()
    
    # 通知所有管理该大作业的老师
    major_assignment = team.major_assignment
    
    # 构建通知内容
    if is_size_valid:
        notification_content = f'{current_user.real_name} 请求确认团队「{team.name}」（大作业：{major_assignment.title}）'
    else:
        notification_content = f'{current_user.real_name} 请求确认团队「{team.name}」（大作业：{major_assignment.title}）\n注意：团队人数不符合要求（当前{team.get_member_count()}人，要求{team.major_assignment.min_team_size}-{team.major_assignment.max_team_size}人）\n申请理由：{confirmation_reason}'
    
    # 通知创建者
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=major_assignment.creator_id,
        title=f'团队确认请求：{team.name}',
        content=notification_content,
        notification_type='team_confirmation'
    )
    
    # 通知所有管理老师
    for teacher in major_assignment.teachers:
        if teacher.id != major_assignment.creator_id:  # 避免重复通知
            NotificationService.create_notification(
                sender_id=current_user.id,
                receiver_id=teacher.id,
                title=f'团队确认请求：{team.name}',
                content=notification_content,
                notification_type='team_confirmation'
            )
    
    flash('确认请求已发送，请等待老师处理')
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
    team.is_locked = True  # 确认后锁定团队
    db.session.commit()
    
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=team.leader_id,
        title='团队已确认',
        content=f'您的团队「{team.name}」已被 {current_user.real_name} 确认，团队已锁定，无法再调整成员',
        notification_type='system'
    )
    
    # 通知所有成员
    for member in team.members:
        NotificationService.create_notification(
            sender_id=current_user.id,
            receiver_id=member.user_id,
            title='团队已确认',
            content=f'团队「{team.name}」已被 {current_user.real_name} 确认，团队已锁定',
            notification_type='system'
        )
    
    flash('团队已确认并锁定')
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
    
    reject_reason = request.form.get('reject_reason', '').strip()
    
    # 保存拒绝理由
    team.status = 'rejected'
    team.reject_reason = reject_reason if reject_reason else '未填写拒绝理由'
    team.confirmation_requested_at = None  # 清除请求确认时间，允许重新请求
    db.session.commit()
    
    # 构建通知内容
    notification_content = f'您的团队「{team.name}」被 {current_user.real_name} 拒绝。'
    if reject_reason:
        notification_content += f'\n拒绝理由：{reject_reason}'
    notification_content += '\n您可以调整团队后重新申请确认。'
    
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=team.leader_id,
        title='团队被拒绝',
        content=notification_content,
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


@bp.route('/team_invitations/<int:invitation_id>/resend', methods=['POST'])
@login_required
def resend_team_invitation(invitation_id):
    """重新发送团队邀请"""
    invitation = TeamInvitation.query.get_or_404(invitation_id)
    team = invitation.team
    
    # 检查是否是组长
    if team.leader_id != current_user.id:
        flash('只有组长才能重新发送邀请')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 只有被拒绝的邀请才能重新发送
    if invitation.status != 'rejected':
        flash('只能重新发送被拒绝的邀请')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    invitee = invitation.invitee
    major_assignment = team.major_assignment
    
    # 检查被邀请人是否已经在其他团队中
    for t in major_assignment.teams:
        if t.leader_id == invitee.id:
            flash(f'{invitee.real_name} 已经是其他团队的组长，无法邀请')
            return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
        for m in t.members:
            if m.user_id == invitee.id:
                flash(f'{invitee.real_name} 已经加入了其他团队，无法邀请')
                return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 检查是否有待处理的邀请
    existing_pending = TeamInvitation.query.filter_by(
        team_id=team.id,
        invitee_id=invitee.id,
        status='pending'
    ).first()
    
    if existing_pending:
        flash(f'已经向 {invitee.real_name} 发送过邀请，请等待对方回应')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 创建新的邀请
    new_invitation = TeamInvitation(
        team_id=team.id,
        inviter_id=current_user.id,
        invitee_id=invitee.id
    )
    db.session.add(new_invitation)
    
    # 发送通知
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=invitee.id,
        title=f'团队邀请：{team.name}',
        content=f'{current_user.real_name} 再次邀请您加入团队「{team.name}」，大作业：{major_assignment.title}',
        notification_type='team_invitation'
    )
    
    db.session.commit()
    flash(f'已重新向 {invitee.real_name} 发送邀请')
    return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))


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


@bp.route('/teams/<int:team_id>/request_dissolve', methods=['POST'])
@login_required
def request_dissolve_team(team_id):
    """组长申请解散团队"""
    team = Team.query.get_or_404(team_id)
    
    # 检查是否是组长
    if team.leader_id != current_user.id:
        flash('只有组长才能申请解散团队')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 检查分组阶段是否已完成
    team_formation_stage = Stage.query.filter_by(
        major_assignment_id=team.major_assignment_id,
        stage_type='team_formation'
    ).first()
    
    if team_formation_stage and team_formation_stage.status == 'completed':
        flash('当前操作不在阶段，请联系管理员或老师')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 检查是否已有待处理的解散请求
    existing_request = DissolveTeamRequest.query.filter_by(
        team_id=team_id,
        status='pending'
    ).first()
    
    if existing_request:
        flash('已经提交过解散申请，请等待处理')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('请填写解散原因')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 创建解散请求
    dissolve_request = DissolveTeamRequest(
        team_id=team_id,
        leader_id=current_user.id,
        reason=reason
    )
    db.session.add(dissolve_request)
    db.session.commit()
    
    # 通知所有管理教师和超级管理员
    major_assignment = team.major_assignment
    
    # 通知管理教师
    for teacher in major_assignment.teachers:
        NotificationService.create_notification(
            sender_id=current_user.id,
            receiver_id=teacher.id,
            title=f'团队解散申请：{team.name}',
            content=f'{current_user.real_name} 申请解散团队「{team.name}」（大作业：{major_assignment.title}）。原因：{reason}',
            notification_type='dissolve_request'
        )
    
    # 通知超级管理员
    super_admins = User.query.filter_by(role=UserRole.SUPER_ADMIN).all()
    for admin in super_admins:
        if admin.id not in [t.id for t in major_assignment.teachers]:
            NotificationService.create_notification(
                sender_id=current_user.id,
                receiver_id=admin.id,
                title=f'团队解散申请：{team.name}',
                content=f'{current_user.real_name} 申请解散团队「{team.name}」（大作业：{major_assignment.title}）。原因：{reason}',
                notification_type='dissolve_request'
            )
    
    flash('解散申请已提交，等待管理员或负责老师审批')
    return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))


@bp.route('/dissolve_requests/<int:request_id>/approve', methods=['POST'])
@login_required
@require_teacher_or_admin
def approve_dissolve_request(request_id):
    """管理员/教师批准解散团队请求"""
    dissolve_request = DissolveTeamRequest.query.get_or_404(request_id)
    team = dissolve_request.team
    
    # 检查权限
    if not team.major_assignment.can_manage(current_user):
        flash('您没有权限处理此请求')
        return redirect(url_for('notification.notifications'))
    
    if dissolve_request.status != 'pending':
        flash('该请求已处理')
        return redirect(url_for('notification.notifications'))
    
    # 保存团队信息（在删除前）
    team_name = team.name
    leader_id = team.leader_id
    assignment_id = team.major_assignment_id
    team_id = team.id
    
    # 删除所有团队成员
    TeamMember.query.filter_by(team_id=team_id).delete()
    
    # 删除所有邀请
    TeamInvitation.query.filter_by(team_id=team_id).delete()
    
    # 删除所有解散请求（包括当前请求）
    DissolveTeamRequest.query.filter_by(team_id=team_id).delete()
    
    # 删除团队
    db.session.delete(team)
    db.session.commit()
    
    # 通知组长
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=leader_id,
        title='团队解散申请已批准',
        content=f'{current_user.real_name} 已批准您解散团队「{team_name}」的申请',
        notification_type='system'
    )
    
    flash('已批准解散团队申请')
    return redirect(url_for('notification.notifications'))


@bp.route('/dissolve_requests/<int:request_id>/reject', methods=['POST'])
@login_required
@require_teacher_or_admin
def reject_dissolve_request(request_id):
    """管理员/教师拒绝解散团队请求"""
    dissolve_request = DissolveTeamRequest.query.get_or_404(request_id)
    team = dissolve_request.team
    
    # 检查权限
    if not team.major_assignment.can_manage(current_user):
        flash('您没有权限处理此请求')
        return redirect(url_for('notification.notifications'))
    
    if dissolve_request.status != 'pending':
        flash('该请求已处理')
        return redirect(url_for('notification.notifications'))
    
    review_comment = request.form.get('review_comment', '')
    
    dissolve_request.status = 'rejected'
    dissolve_request.responded_at = datetime.utcnow()
    dissolve_request.reviewer_id = current_user.id
    dissolve_request.review_comment = review_comment
    db.session.commit()
    
    # 通知组长
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=dissolve_request.leader_id,
        title='团队解散申请被拒绝',
        content=f'{current_user.real_name} 拒绝了您解散团队「{team.name}」的申请。理由：{review_comment}',
        notification_type='system'
    )
    
    flash('已拒绝解散团队申请')
    return redirect(url_for('notification.notifications'))


@bp.route('/teams/<int:team_id>/admin_dissolve', methods=['POST'])
@login_required
@require_teacher_or_admin
def admin_dissolve_team(team_id):
    """管理员/教师直接解散团队"""
    team = Team.query.get_or_404(team_id)
    
    # 检查权限
    if not team.major_assignment.can_manage(current_user):
        flash('您没有权限解散此团队')
        return redirect(url_for('major_assignment.view_major_assignment_teams', assignment_id=team.major_assignment_id))
    
    reason = request.form.get('reason', '').strip()
    team_name = team.name
    leader_id = team.leader_id
    assignment_id = team.major_assignment_id
    
    # 获取所有成员ID（用于通知）
    member_ids = [leader_id]
    for member in team.members:
        member_ids.append(member.user_id)
    
    # 删除所有团队成员
    TeamMember.query.filter_by(team_id=team.id).delete()
    
    # 删除所有邀请
    TeamInvitation.query.filter_by(team_id=team.id).delete()
    
    # 删除所有退组请求
    LeaveTeamRequest.query.filter_by(team_id=team.id).delete()
    
    # 删除所有解散请求
    DissolveTeamRequest.query.filter_by(team_id=team.id).delete()
    
    # 删除团队
    db.session.delete(team)
    db.session.commit()
    
    # 通知所有成员
    for member_id in member_ids:
        NotificationService.create_notification(
            sender_id=current_user.id,
            receiver_id=member_id,
            title=f'团队已被解散：{team_name}',
            content=f'{current_user.real_name} 解散了团队「{team_name}」' + 
                    (f'。原因：{reason}' if reason else ''),
            notification_type='system'
        )
    
    flash(f'已解散团队「{team_name}」')
    return redirect(url_for('major_assignment.view_major_assignment_teams', assignment_id=assignment_id))


@bp.route('/teams/<int:team_id>/members', methods=['GET'])
@login_required
@require_teacher_or_admin
def get_team_members(team_id):
    """获取团队成员列表（API）"""
    from flask import jsonify
    
    team = Team.query.get_or_404(team_id)
    
    # 检查权限
    if not team.major_assignment.can_manage(current_user):
        return jsonify({'success': False, 'message': '没有权限'}), 403
    
    members = []
    for member in team.members:
        members.append({
            'id': member.user.id,
            'real_name': member.user.real_name,
            'student_id': member.user.student_id
        })
    
    leader = {
        'id': team.leader.id,
        'real_name': team.leader.real_name,
        'student_id': team.leader.student_id
    }
    
    return jsonify({
        'success': True,
        'members': members,
        'leader': leader
    })


@bp.route('/teams/<int:team_id>/members/<int:member_id>/remove', methods=['POST'])
@login_required
@require_teacher_or_admin
def remove_team_member(team_id, member_id):
    """移除团队成员（API）"""
    from flask import jsonify
    
    team = Team.query.get_or_404(team_id)
    
    # 检查权限
    if not team.major_assignment.can_manage(current_user):
        return jsonify({'success': False, 'message': '没有权限'}), 403
    
    # 不能移除组长
    if team.leader_id == member_id:
        return jsonify({'success': False, 'message': '不能移除组长，请先转移组长或解散团队'}), 400
    
    # 查找并删除成员
    member = TeamMember.query.filter_by(team_id=team_id, user_id=member_id).first()
    if not member:
        return jsonify({'success': False, 'message': '成员不存在'}), 404
    
    member_name = member.user.real_name
    db.session.delete(member)
    db.session.commit()
    
    # 通知被移除的成员
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=member_id,
        title=f'您已被移出团队：{team.name}',
        content=f'{current_user.real_name} 将您从团队「{team.name}」中移除',
        notification_type='system'
    )
    
    # 通知组长
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=team.leader_id,
        title=f'成员被移除：{member_name}',
        content=f'{current_user.real_name} 将 {member_name} 从您的团队「{team.name}」中移除',
        notification_type='system'
    )
    
    return jsonify({'success': True, 'message': '移除成功'})


@bp.route('/teams/<int:team_id>/members/add', methods=['POST'])
@login_required
@require_teacher_or_admin
def add_team_member(team_id):
    """添加团队成员（API）"""
    from flask import jsonify
    
    team = Team.query.get_or_404(team_id)
    
    # 检查权限
    if not team.major_assignment.can_manage(current_user):
        return jsonify({'success': False, 'message': '没有权限'}), 403
    
    data = request.get_json()
    name = data.get('name', '').strip()
    number = data.get('number', '').strip()
    
    if not name or not number:
        return jsonify({'success': False, 'message': '请填写姓名和学号'}), 400
    
    # 查找学生
    student = User.query.filter(
        User.real_name == name,
        User.student_id == number,
        User.role == UserRole.STUDENT
    ).first()
    
    if not student:
        return jsonify({'success': False, 'message': f'找不到姓名为「{name}」、学号为「{number}」的学生'}), 404
    
    # 检查是否在同一班级
    major_assignment = team.major_assignment
    class_obj = Class.query.get(major_assignment.class_id)
    if student not in class_obj.students:
        return jsonify({'success': False, 'message': f'{student.real_name} 不在该大作业的班级中'}), 400
    
    # 检查是否已在其他团队
    for t in major_assignment.teams:
        if t.leader_id == student.id:
            return jsonify({'success': False, 'message': f'{student.real_name} 已经是其他团队的组长'}), 400
        for m in t.members:
            if m.user_id == student.id:
                return jsonify({'success': False, 'message': f'{student.real_name} 已经在其他团队中'}), 400
    
    # 检查人数限制
    current_count = team.get_member_count()
    if current_count >= major_assignment.max_team_size:
        return jsonify({'success': False, 'message': f'团队人数已达到上限（{major_assignment.max_team_size}人）'}), 400
    
    # 添加成员
    new_member = TeamMember(team_id=team_id, user_id=student.id)
    db.session.add(new_member)
    db.session.commit()
    
    # 通知学生
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=student.id,
        title=f'您已被添加到团队：{team.name}',
        content=f'{current_user.real_name} 将您添加到团队「{team.name}」（大作业：{major_assignment.title}）',
        notification_type='system'
    )
    
    # 通知组长
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=team.leader_id,
        title=f'新成员已添加：{student.real_name}',
        content=f'{current_user.real_name} 将 {student.real_name} 添加到您的团队「{team.name}」',
        notification_type='system'
    )
    
    return jsonify({'success': True, 'message': '添加成功'})


@bp.route('/teams/<int:team_id>/transfer_leader', methods=['POST'])
@login_required
@require_teacher_or_admin
def transfer_team_leader(team_id):
    """转移组长（API）"""
    from flask import jsonify
    
    team = Team.query.get_or_404(team_id)
    
    # 检查权限
    if not team.major_assignment.can_manage(current_user):
        return jsonify({'success': False, 'message': '没有权限'}), 403
    
    data = request.get_json()
    new_leader_id = data.get('new_leader_id')
    
    if not new_leader_id:
        return jsonify({'success': False, 'message': '请选择新组长'}), 400
    
    new_leader_id = int(new_leader_id)
    
    # 检查新组长是否在团队中
    member = TeamMember.query.filter_by(team_id=team_id, user_id=new_leader_id).first()
    if not member:
        return jsonify({'success': False, 'message': '新组长不在团队中'}), 400
    
    old_leader_id = team.leader_id
    old_leader = team.leader
    new_leader = member.user
    
    # 将旧组长添加为普通成员
    old_leader_member = TeamMember(team_id=team_id, user_id=old_leader_id)
    db.session.add(old_leader_member)
    
    # 删除新组长的成员记录
    db.session.delete(member)
    
    # 更新组长
    team.leader_id = new_leader_id
    db.session.commit()
    
    # 通知旧组长
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=old_leader_id,
        title=f'组长已转移：{team.name}',
        content=f'{current_user.real_name} 将团队「{team.name}」的组长转移给 {new_leader.real_name}',
        notification_type='system'
    )
    
    # 通知新组长
    NotificationService.create_notification(
        sender_id=current_user.id,
        receiver_id=new_leader_id,
        title=f'您已成为组长：{team.name}',
        content=f'{current_user.real_name} 将您设置为团队「{team.name}」的组长',
        notification_type='system'
    )
    
    return jsonify({'success': True, 'message': '转移成功'})


# ==================== 阶段管理 ====================

@bp.route('/major_assignments/<int:assignment_id>/stages')
@login_required
@require_teacher_or_admin
def manage_stages(assignment_id):
    """阶段管理页面"""
    from app.models.team import Stage
    
    major_assignment = MajorAssignment.query.get_or_404(assignment_id)
    
    # 检查权限
    if not major_assignment.can_manage(current_user):
        flash('您没有权限管理此大作业')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    # 获取所有阶段，按顺序排列
    stages = Stage.query.filter_by(
        major_assignment_id=assignment_id
    ).order_by(Stage.order).all()
    
    return render_template('manage_stages.html',
                         major_assignment=major_assignment,
                         stages=stages)


@bp.route('/major_assignments/<int:assignment_id>/stages/create', methods=['POST'])
@login_required
@require_teacher_or_admin
def create_stage(assignment_id):
    """创建阶段"""
    from app.models.team import Stage
    
    major_assignment = MajorAssignment.query.get_or_404(assignment_id)
    
    # 检查权限
    if not major_assignment.can_manage(current_user):
        flash('您没有权限管理此大作业')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    # 检查是否设置了开始和结束日期
    if not major_assignment.start_date or not major_assignment.end_date:
        flash('请先设置大作业的开始和结束日期')
        return redirect(url_for('major_assignment.manage_stages', assignment_id=assignment_id))
    
    name = request.form.get('name')
    stage_type = request.form.get('stage_type')
    description = request.form.get('description', '')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    
    if not name or not stage_type or not start_date_str or not end_date_str:
        flash('请填写所有必填项')
        return redirect(url_for('major_assignment.manage_stages', assignment_id=assignment_id))
    
    # 处理日期
    try:
        beijing_dt = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
        beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
        start_date = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
        
        beijing_dt = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
        beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
        end_date = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception as e:
        flash(f'日期格式错误: {str(e)}')
        return redirect(url_for('major_assignment.manage_stages', assignment_id=assignment_id))
    
    # 验证日期
    if start_date >= end_date:
        flash('开始时间必须早于结束时间')
        return redirect(url_for('major_assignment.manage_stages', assignment_id=assignment_id))
    
    # 验证阶段日期在大作业范围内
    if start_date < major_assignment.start_date or end_date > major_assignment.end_date:
        flash('阶段时间必须在大作业的开始和结束日期之间')
        return redirect(url_for('major_assignment.manage_stages', assignment_id=assignment_id))
    
    # 获取当前最大顺序号
    max_order = db.session.query(db.func.max(Stage.order)).filter_by(
        major_assignment_id=assignment_id
    ).scalar() or 0
    
    # 创建阶段
    stage = Stage(
        major_assignment_id=assignment_id,
        name=name,
        stage_type=stage_type,
        description=description,
        start_date=start_date,
        end_date=end_date,
        order=max_order + 1,
        status='pending'
    )
    db.session.add(stage)
    db.session.commit()
    
    flash(f'阶段「{name}」创建成功！')
    return redirect(url_for('major_assignment.manage_stages', assignment_id=assignment_id))


@bp.route('/major_assignments/stages/<int:stage_id>/edit', methods=['POST'])
@login_required
@require_teacher_or_admin
def edit_stage(stage_id):
    """编辑阶段"""
    from app.models.team import Stage
    
    stage = Stage.query.get_or_404(stage_id)
    major_assignment = stage.major_assignment
    
    # 检查权限
    if not major_assignment.can_manage(current_user):
        flash('您没有权限管理此大作业')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    name = request.form.get('name')
    description = request.form.get('description', '')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    
    if not name or not start_date_str or not end_date_str:
        flash('请填写所有必填项')
        return redirect(url_for('major_assignment.manage_stages', assignment_id=major_assignment.id))
    
    # 处理日期
    try:
        beijing_dt = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
        beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
        start_date = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
        
        beijing_dt = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
        beijing_aware = beijing_dt.replace(tzinfo=BEIJING_TZ)
        end_date = beijing_aware.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception as e:
        flash(f'日期格式错误: {str(e)}')
        return redirect(url_for('major_assignment.manage_stages', assignment_id=major_assignment.id))
    
    # 验证日期
    if start_date >= end_date:
        flash('开始时间必须早于结束时间')
        return redirect(url_for('major_assignment.manage_stages', assignment_id=major_assignment.id))
    
    # 验证阶段日期在大作业范围内
    if major_assignment.start_date and major_assignment.end_date:
        if start_date < major_assignment.start_date or end_date > major_assignment.end_date:
            flash('阶段时间必须在大作业的开始和结束日期之间')
            return redirect(url_for('major_assignment.manage_stages', assignment_id=major_assignment.id))
    
    # 更新阶段
    stage.name = name
    stage.description = description
    stage.start_date = start_date
    stage.end_date = end_date
    db.session.commit()
    
    flash(f'阶段「{name}」修改成功！')
    return redirect(url_for('major_assignment.manage_stages', assignment_id=major_assignment.id))


@bp.route('/major_assignments/stages/<int:stage_id>/delete', methods=['POST'])
@login_required
@require_teacher_or_admin
def delete_stage(stage_id):
    """删除阶段"""
    from app.models.team import Stage
    
    stage = Stage.query.get_or_404(stage_id)
    major_assignment = stage.major_assignment
    
    # 检查权限
    if not major_assignment.can_manage(current_user):
        flash('您没有权限管理此大作业')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    stage_name = stage.name
    db.session.delete(stage)
    db.session.commit()
    
    flash(f'阶段「{stage_name}」已删除')
    return redirect(url_for('major_assignment.manage_stages', assignment_id=major_assignment.id))


@bp.route('/major_assignments/stages/update_status', methods=['POST'])
@login_required
@require_teacher_or_admin
def update_stage_status():
    """手动触发更新阶段状态"""
    from flask import jsonify
    from app.services.stage_service import StageService
    
    try:
        StageService.check_and_update_stages()
        return jsonify({
            'success': True,
            'message': '阶段状态已更新！已执行所有自动处理逻辑。'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'更新失败: {str(e)}'
        }), 500


@bp.route('/major_assignments/stages/<int:stage_id>/activate', methods=['POST'])
@login_required
@require_teacher_or_admin
def activate_stage(stage_id):
    """手动激活阶段"""
    from flask import jsonify
    from app.models.team import Stage
    
    stage = Stage.query.get_or_404(stage_id)
    major_assignment = stage.major_assignment
    
    # 检查权限
    if not major_assignment.can_manage(current_user):
        return jsonify({
            'success': False,
            'message': '没有权限'
        }), 403
    
    # 检查状态
    if stage.status != 'pending':
        return jsonify({
            'success': False,
            'message': f'阶段已经是 {stage.status} 状态'
        }), 400
    
    stage.status = 'active'
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'阶段「{stage.name}」已激活！'
    })


@bp.route('/major_assignments/stages/<int:stage_id>/complete', methods=['POST'])
@login_required
@require_teacher_or_admin
def complete_stage(stage_id):
    """手动完成阶段"""
    from flask import jsonify
    from app.models.team import Stage
    from app.services.stage_service import StageService
    
    stage = Stage.query.get_or_404(stage_id)
    major_assignment = stage.major_assignment
    
    # 检查权限
    if not major_assignment.can_manage(current_user):
        return jsonify({
            'success': False,
            'message': '没有权限'
        }), 403
    
    # 检查状态
    if stage.status not in ['pending', 'active']:
        return jsonify({
            'success': False,
            'message': f'阶段已经是 {stage.status} 状态'
        }), 400
    
    try:
        stage.status = 'completed'
        db.session.commit()
        
        # 执行自动处理逻辑
        StageService._on_stage_completed(stage)
        
        return jsonify({
            'success': True,
            'message': f'阶段「{stage.name}」已完成！已执行自动处理逻辑。'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'完成失败: {str(e)}'
        }), 500


@bp.route('/major_assignments/stages/<int:stage_id>/restart', methods=['POST'])
@login_required
@require_teacher_or_admin
def restart_stage(stage_id):
    """重新开始阶段"""
    from flask import jsonify
    from app.models.team import Stage
    
    stage = Stage.query.get_or_404(stage_id)
    major_assignment = stage.major_assignment
    
    # 检查权限
    if not major_assignment.can_manage(current_user):
        return jsonify({
            'success': False,
            'message': '没有权限'
        }), 403
    
    # 检查状态
    if stage.status != 'completed':
        return jsonify({
            'success': False,
            'message': f'只有已完成的阶段才能重新开始'
        }), 400
    
    try:
        # 重置为待开始状态
        stage.status = 'pending'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'阶段「{stage.name}」已重置为“待开始”状态，您可以重新激活该阶段。'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'重启失败: {str(e)}'
        }), 500


# ==================== 分工角色管理 ====================

@bp.route('/major_assignments/stages/<int:stage_id>/division_roles')
@login_required
@require_teacher_or_admin
def manage_division_roles(stage_id):
    """管理分工阶段的角色"""
    from app.models.team import Stage, DivisionRole
    
    stage = Stage.query.get_or_404(stage_id)
    major_assignment = stage.major_assignment
    
    # 检查权限
    if not major_assignment.can_manage(current_user):
        flash('您没有权限管理此大作业')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    # 检查阶段类型
    if stage.stage_type != 'division':
        flash('只有分工阶段才能管理分工角色')
        return redirect(url_for('major_assignment.manage_stages', assignment_id=major_assignment.id))
    
    # 获取所有分工角色
    division_roles = DivisionRole.query.filter_by(stage_id=stage_id).all()
    
    return render_template('manage_division_roles.html',
                         stage=stage,
                         division_roles=division_roles)


@bp.route('/major_assignments/stages/<int:stage_id>/division_roles/create', methods=['POST'])
@login_required
@require_teacher_or_admin
def create_division_role(stage_id):
    """创建分工角色"""
    from app.models.team import Stage, DivisionRole
    
    stage = Stage.query.get_or_404(stage_id)
    major_assignment = stage.major_assignment
    
    # 检查权限
    if not major_assignment.can_manage(current_user):
        flash('您没有权限管理此大作业')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    # 检查阶段类型
    if stage.stage_type != 'division':
        flash('只有分工阶段才能创建分工角色')
        return redirect(url_for('major_assignment.manage_stages', assignment_id=major_assignment.id))
    
    name = request.form.get('name')
    description = request.form.get('description', '')
    is_required = request.form.get('is_required') == 'on'
    
    if not name:
        flash('请填写角色名称')
        return redirect(url_for('major_assignment.manage_division_roles', stage_id=stage_id))
    
    # 创建角色
    role = DivisionRole(
        stage_id=stage_id,
        name=name,
        description=description,
        is_required=is_required
    )
    db.session.add(role)
    db.session.commit()
    
    flash(f'角色「{name}」创建成功！')
    return redirect(url_for('major_assignment.manage_division_roles', stage_id=stage_id))


@bp.route('/major_assignments/division_roles/<int:role_id>/edit', methods=['POST'])
@login_required
@require_teacher_or_admin
def edit_division_role(role_id):
    """编辑分工角色"""
    from app.models.team import DivisionRole
    
    role = DivisionRole.query.get_or_404(role_id)
    stage = role.stage
    major_assignment = stage.major_assignment
    
    # 检查权限
    if not major_assignment.can_manage(current_user):
        flash('您没有权限管理此大作业')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    name = request.form.get('name')
    description = request.form.get('description', '')
    is_required = request.form.get('is_required') == 'on'
    
    if not name:
        flash('请填写角色名称')
        return redirect(url_for('major_assignment.manage_division_roles', stage_id=stage.id))
    
    # 更新角色
    role.name = name
    role.description = description
    role.is_required = is_required
    db.session.commit()
    
    flash(f'角色「{name}」修改成功！')
    return redirect(url_for('major_assignment.manage_division_roles', stage_id=stage.id))


@bp.route('/major_assignments/division_roles/<int:role_id>/delete', methods=['POST'])
@login_required
@require_teacher_or_admin
def delete_division_role(role_id):
    """删除分工角色"""
    from app.models.team import DivisionRole, TeamDivision
    
    role = DivisionRole.query.get_or_404(role_id)
    stage = role.stage
    major_assignment = stage.major_assignment
    
    # 检查权限
    if not major_assignment.can_manage(current_user):
        flash('您没有权限管理此大作业')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    # 删除所有相关的团队分工
    TeamDivision.query.filter_by(division_role_id=role_id).delete()
    
    role_name = role.name
    db.session.delete(role)
    db.session.commit()
    
    flash(f'角色「{role_name}」已删除')
    return redirect(url_for('major_assignment.manage_division_roles', stage_id=stage.id))


# ==================== 团队分工分配 ====================

@bp.route('/teams/<int:team_id>/stages/<int:stage_id>/assign_divisions')
@login_required
def team_assign_divisions(team_id, stage_id):
    """组长为团队分配分工角色（自由定义）"""
    from app.models.team import Stage, TeamDivision
    
    team = Team.query.get_or_404(team_id)
    stage = Stage.query.get_or_404(stage_id)
    
    # 检查是否是组长
    if team.leader_id != current_user.id:
        flash('只有组长才能分配分工')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 注意：团队锁定只限制成员增减，不限制分工分配
    # 因此这里不检查 is_locked 状态
    
    # 检查阶段类型
    if stage.stage_type != 'division':
        flash('该阶段不是分工阶段')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 获取团队成员列表（包括组长）
    team_members = [team.leader]
    team_members.extend([m.user for m in team.members])
    
    # 获取已存在的分工（按角色名称分组）
    existing_divisions_query = db.session.query(
        TeamDivision.role_name,
        TeamDivision.role_description,
        db.func.group_concat(TeamDivision.member_id).label('member_ids')
    ).filter_by(team_id=team_id, stage_id=stage_id).group_by(
        TeamDivision.role_name, TeamDivision.role_description
    ).all()
    
    existing_divisions = []
    for div in existing_divisions_query:
        member_ids = [int(mid) for mid in div.member_ids.split(',')] if div.member_ids else []
        existing_divisions.append({
            'role_name': div.role_name,
            'role_description': div.role_description,
            'member_ids': member_ids
        })
    
    return render_template('team_assign_divisions.html',
                         team=team,
                         stage=stage,
                         team_members=team_members,
                         existing_divisions=existing_divisions)


@bp.route('/teams/<int:team_id>/stages/<int:stage_id>/save_divisions', methods=['POST'])
@login_required
def save_team_divisions(team_id, stage_id):
    """保存团队分工分配（自由定义）"""
    from app.models.team import Stage, TeamDivision
    
    team = Team.query.get_or_404(team_id)
    stage = Stage.query.get_or_404(stage_id)
    
    # 检查是否是组长
    if team.leader_id != current_user.id:
        flash('只有组长才能分配分工')
        return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))
    
    # 注意：团队锁定只限制成员增减，不限制分工分配
    # 因此这里不检查 is_locked 状态
    
    # 删除该团队在该阶段的所有旧分工
    TeamDivision.query.filter_by(team_id=team_id, stage_id=stage_id).delete()
    
    # 获取表单数据
    role_names = request.form.getlist('role_name[]')
    role_descriptions = request.form.getlist('role_description[]')
    role_members = request.form.getlist('role_members[]')
    
    if not role_names:
        flash('请至少添加一个角色分工')
        return redirect(url_for('major_assignment.team_assign_divisions', team_id=team_id, stage_id=stage_id))
    
    # 处理每个角色
    for i, role_name in enumerate(role_names):
        if not role_name or not role_name.strip():
            continue
            
        role_description = role_descriptions[i] if i < len(role_descriptions) else ''
        
        # 获取该角色的成员列表（从表单中解析多选值）
        # role_members[] 是多选下拉框，Flask会将所有选中的值放在一个数组中
        # 但是我们需要按照每个角色来分组
        # 每个 select 的 name 都是 role_members[]，所以需要特殊处理
        
        # 使用表单索引来区分不同的角色
        member_ids_key = f'role_members_{i}[]'
        member_ids = request.form.getlist(member_ids_key)
        
        if not member_ids:
            flash(f'角色「{role_name}」必须分配至少一名成员')
            return redirect(url_for('major_assignment.team_assign_divisions', team_id=team_id, stage_id=stage_id))
        
        # 为每个成员创建一条分工记录
        for member_id in member_ids:
            if not member_id:
                continue
                
            division = TeamDivision(
                team_id=team_id,
                stage_id=stage_id,
                role_name=role_name.strip(),
                role_description=role_description.strip() if role_description else None,
                member_id=int(member_id),
                assigned_at=datetime.utcnow(),
                assigned_by=current_user.id
            )
            db.session.add(division)
    
    db.session.commit()
    flash('分工分配已保存！')
    return redirect(url_for('major_assignment.student_major_assignment_detail', assignment_id=team.major_assignment_id))


# ==================== 大作业删除 ====================

@bp.route('/major_assignments/<int:assignment_id>/delete', methods=['POST'])
@login_required
@require_teacher_or_admin
def delete_major_assignment(assignment_id):
    """删除大作业（级联删除所有相关数据）"""
    from flask import jsonify
    from app.models.team import Stage, DivisionRole, TeamDivision
    import os
    
    major_assignment = MajorAssignment.query.get_or_404(assignment_id)
    
    # 检查权限（只有管理员、创建者和管理教师可以删除）
    if not major_assignment.can_manage(current_user):
        return jsonify({
            'success': False,
            'message': '没有权限删除此大作业'
        }), 403
    
    try:
        # 保存信息用于日志
        assignment_title = major_assignment.title
        
        # 1. 删除所有阶段和相关数据
        stages = Stage.query.filter_by(major_assignment_id=assignment_id).all()
        for stage in stages:
            # 删除分工角色和团队分工
            if stage.stage_type == 'division':
                roles = DivisionRole.query.filter_by(stage_id=stage.id).all()
                for role in roles:
                    # 删除所有团队分工
                    TeamDivision.query.filter_by(division_role_id=role.id).delete()
                    db.session.delete(role)
            
            db.session.delete(stage)
        
        # 2. 删除所有团队和相关数据
        teams = Team.query.filter_by(major_assignment_id=assignment_id).all()
        for team in teams:
            # 删除团队成员
            TeamMember.query.filter_by(team_id=team.id).delete()
            
            # 删除团队邀请
            TeamInvitation.query.filter_by(team_id=team.id).delete()
            
            # 删除退组请求
            LeaveTeamRequest.query.filter_by(team_id=team.id).delete()
            
            # 删除解散请求
            DissolveTeamRequest.query.filter_by(team_id=team.id).delete()
            
            # 删除团队分工（如果有）
            TeamDivision.query.filter_by(team_id=team.id).delete()
            
            # 删除团队
            db.session.delete(team)
        
        # 3. 删除附件和链接
        # 删除新系统的附件
        attachments = MajorAssignmentAttachment.query.filter_by(
            major_assignment_id=assignment_id
        ).all()
        for attachment in attachments:
            # 删除物理文件
            if os.path.exists(attachment.file_path):
                try:
                    os.remove(attachment.file_path)
                except Exception as e:
                    print(f'删除附件文件失败: {str(e)}')
            db.session.delete(attachment)
        
        # 删除新系统的链接
        links = MajorAssignmentLink.query.filter_by(
            major_assignment_id=assignment_id
        ).all()
        for link in links:
            db.session.delete(link)
        
        # 删除旧系统的作业要求文件（兼容）
        if major_assignment.requirement_file_path:
            if os.path.exists(major_assignment.requirement_file_path):
                try:
                    os.remove(major_assignment.requirement_file_path)
                except Exception as e:
                    print(f'删除旧系统文件失败: {str(e)}')
        
        # 4. 清空管理教师关联
        major_assignment.teachers = []
        
        # 5. 删除大作业
        db.session.delete(major_assignment)
        
        # 提交事务
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'大作业「{assignment_title}」已成功删除！'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'删除失败: {str(e)}'
        }), 500


# ==================== 任务管理相关路由 ====================

@bp.route('/major_assignments/<int:assignment_id>/tasks')
@login_required
def view_assignment_tasks(assignment_id):
    """查看大作业的所有任务（教师/管理员视角）"""
    from app.models.team import TeamTask
    
    major_assignment = MajorAssignment.query.get_or_404(assignment_id)
    
    # 权限检查
    if not major_assignment.can_manage(current_user):
        flash('您没有权限查看此大作业的任务')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    # 获取该大作业的所有团队任务
    teams = Team.query.filter_by(major_assignment_id=assignment_id).all()
    team_ids = [t.id for t in teams]
    
    tasks = TeamTask.query.filter(
        TeamTask.team_id.in_(team_ids)
    ).order_by(
        TeamTask.team_id, TeamTask.created_at
    ).all() if team_ids else []
    
    # 按团队分组
    from collections import defaultdict
    tasks_by_team = defaultdict(list)
    for task in tasks:
        tasks_by_team[task.team].append(task)
    
    return render_template('view_assignment_tasks.html',
                         major_assignment=major_assignment,
                         tasks_by_team=dict(tasks_by_team),
                         teams=teams)


@bp.route('/stages/<int:stage_id>/tasks')
@login_required
def view_stage_tasks(stage_id):
    """查看任务阶段的所有任务（教师/管理员视角） - 已废弃，重定向到大作业任务视图"""
    from app.models.team import Stage
    
    stage = Stage.query.get_or_404(stage_id)
    major_assignment = stage.major_assignment
    
    # 权限检查
    if not major_assignment.can_manage(current_user):
        flash('您没有权限查看此阶段的任务')
        return redirect(url_for('major_assignment.major_assignment_dashboard'))
    
    # 重定向到新的任务视图
    return redirect(url_for('major_assignment.view_assignment_tasks', 
                          assignment_id=major_assignment.id))


@bp.route('/teams/<int:team_id>/tasks')
@login_required
def team_task_management(team_id):
    """团队任务管理（组长视角）"""
    from app.models.team import TeamTask
    
    team = Team.query.get_or_404(team_id)
    
    # 权限检查：必须是组长或团队成员（组长可以管理，成员可以查看）
    is_leader = team.leader_id == current_user.id
    is_member = any(m.user_id == current_user.id for m in team.members)
    
    if not is_leader and not is_member:
        flash('您不是该团队成员')
        return redirect(url_for('major_assignment.student_major_assignment_detail', 
                              assignment_id=team.major_assignment_id))
    
    # 获取团队成员
    team_members = [team.leader]
    team_members.extend([m.user for m in team.members])
    
    # 获取该团队的所有任务
    tasks = TeamTask.query.filter_by(
        team_id=team_id
    ).order_by(TeamTask.created_at).all()
    
    return render_template('team_task_management.html',
                         team=team,
                         team_members=team_members,
                         tasks=tasks,
                         is_leader=is_leader)


@bp.route('/teams/<int:team_id>/tasks/create', methods=['POST'])
@login_required
def create_task(team_id):
    """创建任务（组长）"""
    from app.models.team import TeamTask
    
    team = Team.query.get_or_404(team_id)
    
    # 权限检查
    if team.leader_id != current_user.id:
        flash('只有组长可以创建任务')
        return redirect(url_for('major_assignment.student_major_assignment_detail',
                              assignment_id=team.major_assignment_id))
    
    title = request.form.get('title')
    description = request.form.get('description', '')
    assigned_to = request.form.get('assigned_to')  # 可选
    priority = request.form.get('priority', 'medium')
    
    if not title:
        flash('请填写任务标题')
        return redirect(url_for('major_assignment.team_task_management',
                              team_id=team_id))
    
    task = TeamTask(
        team_id=team_id,
        stage_id=None,  # 不再依赖阶段
        title=title,
        description=description,
        assigned_to=int(assigned_to) if assigned_to else None,
        priority=priority,
        created_by=current_user.id
    )
    db.session.add(task)
    db.session.commit()
    
    # 如果分配给了某人，发送通知
    if assigned_to:
        NotificationService.create_notification(
            sender_id=current_user.id,
            receiver_id=int(assigned_to),
            title=f'新任务：{title}',
            content=f'组长 {current_user.real_name} 为您分配了新任务「{title}」',
            notification_type='task'
        )
    
    flash(f'任务「{title}」创建成功！')
    return redirect(url_for('major_assignment.team_task_management',
                          team_id=team_id))


@bp.route('/tasks/<int:task_id>/update_progress', methods=['POST'])
@login_required
def update_task_progress(task_id):
    """更新任务进度（组员）"""
    from app.models.team import TeamTask, TaskProgress
    
    task = TeamTask.query.get_or_404(task_id)
    
    # 权限检查：必须是团队成员或被分配者
    team = task.team
    is_member = (current_user.id == team.leader_id or 
                any(m.user_id == current_user.id for m in team.members))
    
    if not is_member:
        return jsonify({'success': False, 'message': '您不是该团队成员'}), 403
    
    progress = request.form.get('progress', type=int)
    status = request.form.get('status')
    comment = request.form.get('comment', '')
    
    if progress is None or not (0 <= progress <= 100):
        return jsonify({'success': False, 'message': '进度必须在0-100之间'}), 400
    
    # 创建进度记录
    progress_record = TaskProgress(
        task_id=task_id,
        user_id=current_user.id,
        progress=progress,
        status=status,
        comment=comment
    )
    db.session.add(progress_record)
    
    # 更新任务进度和状态
    task.progress = progress
    if status:
        task.status = status
    
    if progress == 100 and not task.completed_at:
        task.completed_at = datetime.utcnow()
        task.status = 'completed'
    
    db.session.commit()
    
    # 通知组长
    if team.leader_id != current_user.id:
        NotificationService.create_notification(
            sender_id=current_user.id,
            receiver_id=team.leader_id,
            title=f'任务进度更新：{task.title}',
            content=f'{current_user.real_name} 更新了任务「{task.title}」的进度至 {progress}%',
            notification_type='task'
        )
    
    return jsonify({
        'success': True,
        'message': '进度更新成功',
        'progress': progress,
        'status': task.status
    })


@bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    """删除任务（组长）"""
    from app.models.team import TeamTask
    
    task = TeamTask.query.get_or_404(task_id)
    team = task.team
    
    # 权限检查
    if team.leader_id != current_user.id:
        flash('只有组长可以删除任务')
        return redirect(url_for('major_assignment.student_major_assignment_detail',
                              assignment_id=team.major_assignment_id))
    
    task_title = task.title
    team_id = task.team_id
    
    db.session.delete(task)
    db.session.commit()
    
    flash(f'任务「{task_title}」已删除')
    return redirect(url_for('major_assignment.team_task_management',
                          team_id=team_id))

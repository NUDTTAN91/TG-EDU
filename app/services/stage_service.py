"""阶段管理服务"""
from datetime import datetime
from app.extensions import db
from app.models.team import Stage, Team, TeamMember, DivisionRole, TeamDivision, MajorAssignment
from app.models.user import User
from app.services.notification_service import NotificationService
import random


class StageService:
    """阶段管理服务类"""
    
    @staticmethod
    def update_stage_status():
        """更新所有阶段的状态（定时任务调用）"""
        now = datetime.utcnow()
        
        # 查找所有需要更新状态的阶段
        stages = Stage.query.filter(
            Stage.status.in_(['pending', 'active'])
        ).all()
        
        for stage in stages:
            old_status = stage.status
            
            # 检查是否应该开始
            if stage.status == 'pending' and stage.start_date and now >= stage.start_date:
                stage.status = 'active'
                StageService._on_stage_started(stage)
            
            # 检查是否应该结束
            if stage.status == 'active' and stage.end_date and now >= stage.end_date:
                stage.status = 'completed'
                StageService._on_stage_completed(stage)
            
            if old_status != stage.status:
                db.session.commit()
    
    @staticmethod
    def _on_stage_started(stage):
        """阶段开始时的处理"""
        print(f"阶段 {stage.name} 已开始")
        
        # 可以在这里添加通知逻辑
        # 例如：通知所有相关学生阶段已开始
    
    @staticmethod
    def _on_stage_completed(stage):
        """阶段结束时的处理"""
        print(f"阶段 {stage.name} 已结束")
        
        if stage.stage_type == 'team_formation':
            # 组队阶段结束，自动分组
            StageService._auto_assign_ungrouped_students(stage)
        
        elif stage.stage_type == 'division':
            # 分工阶段结束，自动分配未分配的必须角色
            StageService._auto_assign_unassigned_roles(stage)
    
    @staticmethod
    def _auto_assign_ungrouped_students(stage):
        """自动为未组队的学生分配团队"""
        try:
            major_assignment = stage.major_assignment
            
            # 获取班级中所有学生
            from app.models.class_model import Class
            class_obj = Class.query.get(major_assignment.class_id)
            if not class_obj:
                print(f"错误：找不到班级 ID={major_assignment.class_id}")
                return
            
            # 找出所有已经在团队中的学生ID
            assigned_student_ids = set()
            for team in major_assignment.teams:
                assigned_student_ids.add(team.leader_id)
                for member in team.members:
                    assigned_student_ids.add(member.user_id)
            
            # 找出未组队的学生
            ungrouped_students = [
                student for student in class_obj.students 
                if student.id not in assigned_student_ids
            ]
            
            if not ungrouped_students:
                print(f"阶段 {stage.name}: 所有学生都已组队")
                return
            
            print(f"阶段 {stage.name}: 发现 {len(ungrouped_students)} 名未组队学生")
            
            # 随机打乱学生顺序
            random.shuffle(ungrouped_students)
            
            # 计算每个团队的目标人数
            min_size = major_assignment.min_team_size
            max_size = major_assignment.max_team_size
            
            # 创建新团队并分配学生
            current_team = None
            current_team_size = 0
            team_count = 0
            
            for student in ungrouped_students:
                try:
                    # 如果当前没有团队或当前团队已满，创建新团队
                    if current_team is None or current_team_size >= max_size:
                        # 使用第一个学生作为组长
                        current_team = Team(
                            name=f'{student.real_name}的团队（系统自动分配）',
                            major_assignment_id=major_assignment.id,
                            leader_id=student.id,
                            status='confirmed',
                            confirmed_at=datetime.utcnow(),
                            confirmed_by=None,  # 系统自动确认
                            is_locked=False  # 不锁定，允许教师后续调整
                        )
                        db.session.add(current_team)
                        db.session.flush()  # 立即分配ID，但不提交
                        current_team_size = 1
                        team_count += 1
                        
                        print(f"  创建团队 #{team_count}: {current_team.name} (组长: {student.real_name})")
                        
                        # 通知组长
                        try:
                            NotificationService.create_notification(
                                sender_id=None,
                                receiver_id=student.id,
                                title=f'系统自动分组：{current_team.name}',
                                content=f'组队阶段已结束，系统已自动为您创建团队「{current_team.name}」，您被指定为组长。',
                                notification_type='system'
                            )
                        except Exception as e:
                            print(f"  警告：创建通知失败: {str(e)}")
                    else:
                        # 加入当前团队
                        member = TeamMember(
                            team_id=current_team.id,
                            user_id=student.id
                        )
                        db.session.add(member)
                        current_team_size += 1
                        
                        print(f"  添加成员: {student.real_name} -> {current_team.name}")
                        
                        # 通知成员
                        try:
                            NotificationService.create_notification(
                                sender_id=None,
                                receiver_id=student.id,
                                title=f'系统自动分组：{current_team.name}',
                                content=f'组队阶段已结束，系统已自动将您分配到团队「{current_team.name}」。',
                                notification_type='system'
                            )
                        except Exception as e:
                            print(f"  警告：创建通知失败: {str(e)}")
                except Exception as e:
                    print(f"  错误：处理学生 {student.real_name} 时出错: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            db.session.commit()
            print(f"阶段 {stage.name}: 自动分组完成，共创建 {team_count} 个团队")
        except Exception as e:
            print(f"错误：自动分组失败: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            raise
    
    @staticmethod
    def _auto_assign_unassigned_roles(stage):
        """自动为团队分配未分配的必须角色"""
        major_assignment = stage.major_assignment
        
        # 获取该阶段的所有必须角色
        required_roles = DivisionRole.query.filter_by(
            stage_id=stage.id,
            is_required=True
        ).all()
        
        if not required_roles:
            print(f"阶段 {stage.name}: 没有必须角色")
            return
        
        # 处理每个团队
        for team in major_assignment.teams:
            # 获取团队所有成员（包括组长）
            team_members = [team.leader]
            team_members.extend([m.user for m in team.members])
            
            # 检查每个必须角色
            for role in required_roles:
                # 查找该团队对该角色的分配
                division = TeamDivision.query.filter_by(
                    team_id=team.id,
                    division_role_id=role.id
                ).first()
                
                # 如果未分配或分配的成员为空
                if not division or not division.member_id:
                    # 随机选择一个成员
                    selected_member = random.choice(team_members)
                    
                    if not division:
                        # 创建新分配
                        division = TeamDivision(
                            team_id=team.id,
                            division_role_id=role.id
                        )
                        db.session.add(division)
                    
                    # 设置分配
                    division.member_id = selected_member.id
                    division.assigned_at = datetime.utcnow()
                    division.assigned_by = None  # 系统自动分配
                    
                    # 通知被分配的成员
                    NotificationService.create_notification(
                        sender_id=None,
                        receiver_id=selected_member.id,
                        title=f'系统自动分配角色：{role.name}',
                        content=f'分工阶段「{stage.name}」已结束，系统已自动将您分配到角色「{role.name}」（团队：{team.name}）。',
                        notification_type='system'
                    )
                    
                    # 通知组长
                    if team.leader_id != selected_member.id:
                        NotificationService.create_notification(
                            sender_id=None,
                            receiver_id=team.leader_id,
                            title=f'系统自动分配角色：{role.name}',
                            content=f'分工阶段「{stage.name}」已结束，系统已自动将 {selected_member.real_name} 分配到角色「{role.name}」。',
                            notification_type='system'
                        )
        
        db.session.commit()
        print(f"阶段 {stage.name}: 自动分配角色完成")
    
    @staticmethod
    def check_and_update_stages():
        """检查并更新阶段状态（供定时任务或手动触发调用）"""
        try:
            StageService.update_stage_status()
            return True
        except Exception as e:
            print(f"更新阶段状态失败: {str(e)}")
            db.session.rollback()
            return False

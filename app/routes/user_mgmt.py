"""用户管理路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, case
from app.extensions import db
from app.models import User, UserRole, Class, Notification
from app.utils import require_teacher_or_admin, require_role

bp = Blueprint('user_mgmt', __name__, url_prefix='/admin/users')


@bp.route('/')
@login_required
@require_teacher_or_admin
def manage_users():
    """用户管理列表"""
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 获取筛选和搜索参数
    role_filter = request.args.get('role', '')
    class_filter = request.args.get('class', '', type=str)
    search_query = request.args.get('search', '').strip()
    
    # 限制每页数量范围
    if per_page not in [10, 20, 50, 100]:
        per_page = 10
    
    # 根据用户角色显示不同的用户列表
    if current_user.is_super_admin:
        # 超级管理员可以查看所有用户
        query = User.query
        
        # 角色筛选
        if role_filter:
            query = query.filter_by(role=role_filter)
        
        # 搜索功能：搜索用户名、真实姓名、学号
        if search_query:
            query = query.filter(
                or_(
                    User.username.like(f'%{search_query}%'),
                    User.real_name.like(f'%{search_query}%'),
                    User.student_id.like(f'%{search_query}%')
                )
            )
        
        # 班级筛选
        if class_filter:
            try:
                class_id = int(class_filter)
                if role_filter == UserRole.TEACHER:
                    query = query.join(User.teaching_classes).filter(Class.id == class_id)
                elif role_filter == UserRole.STUDENT:
                    query = query.join(User.classes).filter(Class.id == class_id)
                else:
                    teachers_in_class = User.query.join(User.teaching_classes).filter(Class.id == class_id)
                    students_in_class = User.query.join(User.classes).filter(Class.id == class_id)
                    query = teachers_in_class.union(students_in_class)
            except ValueError:
                pass
        
        # 先构建完整查询，再分页
        # 按角色优先级排序：超级管理员(0) > 教师(1) > 学生(2)，然后按创建时间排序
        role_order = case(
            (User.role == UserRole.SUPER_ADMIN, 0),
            (User.role == UserRole.TEACHER, 1),
            (User.role == UserRole.STUDENT, 2),
            else_=3
        )
        pagination = query.order_by(role_order, User.created_at.asc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        users = pagination.items
    else:
        # 教师只能看到自己班级的学生
        teacher_class_ids = [c.id for c in current_user.teaching_classes]
        query = User.query.filter_by(role=UserRole.STUDENT)
        
        if teacher_class_ids:
            query = query.filter(
                or_(
                    User.created_by == current_user.id,
                    User.classes.any(Class.id.in_(teacher_class_ids))
                )
            )
        else:
            query = query.filter_by(created_by=current_user.id)
        
        # 搜索功能：搜索用户名、真实姓名、学号
        if search_query:
            query = query.filter(
                or_(
                    User.username.like(f'%{search_query}%'),
                    User.real_name.like(f'%{search_query}%'),
                    User.student_id.like(f'%{search_query}%')
                )
            )
        
        # 班级筛选
        if class_filter and teacher_class_ids:
            try:
                class_id = int(class_filter)
                if class_id in teacher_class_ids:
                    query = query.filter(User.classes.any(Class.id == class_id))
            except ValueError:
                pass
        
        # 先构建完整查询，再分页
        query = query.order_by(User.created_at.asc()).distinct()
        all_students = query.all()
        total = len(all_students)
        start = (page - 1) * per_page
        end = start + per_page
        users = all_students[start:end]
        
        # 简单分页对象
        class SimplePagination:
            def __init__(self, items, page, per_page, total):
                self.items = items
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = (total + per_page - 1) // per_page if per_page > 0 else 0
                self.has_prev = page > 1
                self.has_next = page < self.pages
                self.prev_num = page - 1 if self.has_prev else None
                self.next_num = page + 1 if self.has_next else None
            
            def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
                last = 0
                for num in range(1, self.pages + 1):
                    if num <= left_edge or \
                       (num > self.page - left_current - 1 and num < self.page + right_current) or \
                       num > self.pages - right_edge:
                        if last + 1 != num:
                            yield None
                        yield num
                        last = num
        
        pagination = SimplePagination(users, page, per_page, total)
    
    # 获取所有班级用于筛选
    if current_user.is_super_admin:
        all_classes = Class.query.filter_by(is_active=True).order_by(Class.name.asc()).all()
    else:
        all_classes = current_user.teaching_classes
    
    # 权限检查函数
    def can_teacher_manage_student(teacher, student):
        if student.role != UserRole.STUDENT:
            return False
        if teacher.is_super_admin:
            return True
        if teacher.is_teacher:
            for class_obj in teacher.teaching_classes:
                if student in class_obj.students:
                    return True
        return False
    
    # 计算全局统计数据（不受分页影响）
    if current_user.is_super_admin:
        # 使用与分页相同的筛选条件构建统计查询
        stats_query = User.query
        
        # 应用相同的筛选条件
        if role_filter:
            stats_query = stats_query.filter_by(role=role_filter)
        if search_query:
            stats_query = stats_query.filter(
                or_(
                    User.username.like(f'%{search_query}%'),
                    User.real_name.like(f'%{search_query}%'),
                    User.student_id.like(f'%{search_query}%')
                )
            )
        if class_filter:
            try:
                class_id = int(class_filter)
                if role_filter == UserRole.TEACHER:
                    stats_query = stats_query.join(User.teaching_classes).filter(Class.id == class_id)
                elif role_filter == UserRole.STUDENT:
                    stats_query = stats_query.join(User.classes).filter(Class.id == class_id)
                else:
                    teachers_in_class = User.query.join(User.teaching_classes).filter(Class.id == class_id)
                    students_in_class = User.query.join(User.classes).filter(Class.id == class_id)
                    stats_query = teachers_in_class.union(students_in_class)
            except ValueError:
                pass
        
        # 统计各角色数量
        all_filtered_users = stats_query.all()
        total_super_admins = len([u for u in all_filtered_users if u.role == UserRole.SUPER_ADMIN])
        total_teachers = len([u for u in all_filtered_users if u.role == UserRole.TEACHER])
        total_students = len([u for u in all_filtered_users if u.role == UserRole.STUDENT])
        total_users = len(all_filtered_users)
    else:
        # 教师只统计自己可见的学生
        teacher_class_ids = [c.id for c in current_user.teaching_classes]
        stats_query = User.query.filter_by(role=UserRole.STUDENT)
        
        if teacher_class_ids:
            stats_query = stats_query.filter(
                or_(
                    User.created_by == current_user.id,
                    User.classes.any(Class.id.in_(teacher_class_ids))
                )
            )
        else:
            stats_query = stats_query.filter_by(created_by=current_user.id)
        
        # 应用搜索条件
        if search_query:
            stats_query = stats_query.filter(
                or_(
                    User.username.like(f'%{search_query}%'),
                    User.real_name.like(f'%{search_query}%'),
                    User.student_id.like(f'%{search_query}%')
                )
            )
        
        # 应用班级筛选
        if class_filter and teacher_class_ids:
            try:
                class_id = int(class_filter)
                if class_id in teacher_class_ids:
                    stats_query = stats_query.filter(User.classes.any(Class.id == class_id))
            except ValueError:
                pass
        
        all_filtered_students = stats_query.distinct().all()
        total_super_admins = 0  # 教师看不到管理员
        total_teachers = 0  # 教师看不到其他教师
        total_students = len(all_filtered_students)
        total_users = total_students
    
    return render_template('manage_users.html',
                         users=users,
                         pagination=pagination,
                         all_classes=all_classes,
                         can_teacher_manage_student=can_teacher_manage_student,
                         total_super_admins=total_super_admins,
                         total_teachers=total_teachers,
                         total_students=total_students,
                         total_users=total_users)


@bp.route('/add', methods=['GET', 'POST'])
@login_required
@require_teacher_or_admin
def add_user():
    """添加用户"""
    if request.method == 'POST':
        username = request.form['username']
        real_name = request.form['real_name']
        password = request.form['password']
        role = request.form['role']
        student_id = request.form.get('student_id', '')
        class_ids = request.form.getlist('classes')
        
        # 确保真实姓名和用户名一致
        username = real_name
        
        # 权限检查
        if not current_user.is_super_admin and role != UserRole.STUDENT:
            flash('您只能添加学生用户')
            available_classes = get_available_classes()
            return render_template('add_user.html', available_classes=available_classes)
        
        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
            available_classes = get_available_classes()
            return render_template('add_user.html', available_classes=available_classes)
        
        # 检查真实姓名是否已存在
        if User.query.filter_by(real_name=real_name).first():
            flash('真实姓名已存在')
            available_classes = get_available_classes()
            return render_template('add_user.html', available_classes=available_classes)
        
        # 检查学号
        if role == UserRole.STUDENT and student_id.strip():
            if User.query.filter_by(student_id=student_id.strip()).first():
                flash('学号已存在')
                available_classes = get_available_classes()
                return render_template('add_user.html', available_classes=available_classes)
        
        # 创建新用户
        user = User(
            username=username,
            real_name=real_name,
            role=role,
            student_id=student_id if (role == UserRole.STUDENT and student_id.strip()) else None,
            created_by=current_user.id,
            must_change_password=False if role == UserRole.SUPER_ADMIN else True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()
        
        # 处理班级分配
        if role == UserRole.TEACHER and current_user.is_super_admin:
            teacher_class_ids = request.form.getlist('teacher_classes')
            if teacher_class_ids:
                classes_to_assign = Class.query.filter(Class.id.in_(teacher_class_ids)).all()
                user.teaching_classes.extend(classes_to_assign)
        elif role == UserRole.STUDENT:
            if class_ids:
                if current_user.is_super_admin:
                    classes = Class.query.filter(Class.id.in_(class_ids)).all()
                else:
                    teacher_class_ids = [str(c.id) for c in current_user.teaching_classes]
                    valid_class_ids = [cid for cid in class_ids if cid in teacher_class_ids]
                    classes = Class.query.filter(Class.id.in_(valid_class_ids)).all()
                user.classes.extend(classes)
        
        db.session.commit()
        flash(f'用户 {real_name} 创建成功')
        return redirect(url_for('user_mgmt.manage_users'))
    
    available_classes = get_available_classes()
    return render_template('add_user.html', available_classes=available_classes)


@bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@require_teacher_or_admin
def edit_user(user_id):
    """编辑用户"""
    user = User.query.get_or_404(user_id)
    
    # 权限检查
    if not current_user.is_super_admin:
        if user.role != UserRole.STUDENT:
            flash('您没有权限编辑此用户')
            return redirect(url_for('user_mgmt.manage_users'))
        
        student_in_teacher_classes = False
        for class_obj in current_user.teaching_classes:
            if user in class_obj.students:
                student_in_teacher_classes = True
                break
        
        if not student_in_teacher_classes:
            flash('您没有权限编辑此用户')
            return redirect(url_for('user_mgmt.manage_users'))
    
    if request.method == 'POST':
        user.real_name = request.form['real_name']
        user.username = user.real_name
        user.student_id = request.form.get('student_id', '').strip() if (user.role == UserRole.STUDENT and request.form.get('student_id', '').strip()) else None
        user.is_active = 'is_active' in request.form
        
        # 更新密码
        new_password = request.form.get('password')
        if new_password:
            if len(new_password) < 6:
                flash('密码长度至少6位')
                available_classes = get_available_classes()
                return render_template('edit_user.html', user=user, available_classes=available_classes)
            
            user.set_password(new_password)
            if current_user.is_super_admin and user.id != current_user.id and not user.is_super_admin:
                user.must_change_password = True
                flash(f'用户 {user.real_name} 的密码已更新，该用户下次登录时必须修改密码')
            else:
                flash(f'用户 {user.real_name} 的密码已更新')
        
        # 处理角色和班级
        old_role = user.role
        if current_user.is_super_admin:
            new_role = request.form['role']
            user.role = new_role
            
            if old_role != new_role:
                if old_role == UserRole.TEACHER:
                    user.teaching_classes.clear()
                elif old_role == UserRole.STUDENT:
                    user.classes.clear()
            
            if new_role == UserRole.TEACHER:
                teacher_class_ids = request.form.getlist('teacher_classes')
                user.teaching_classes.clear()
                if teacher_class_ids:
                    classes_to_assign = Class.query.filter(Class.id.in_(teacher_class_ids)).all()
                    user.teaching_classes.extend(classes_to_assign)
            elif new_role == UserRole.STUDENT:
                student_class_ids = request.form.getlist('student_classes')
                user.classes.clear()
                if student_class_ids:
                    classes_to_assign = Class.query.filter(Class.id.in_(student_class_ids)).all()
                    user.classes.extend(classes_to_assign)
        elif user.role == UserRole.STUDENT:
            student_class_ids = request.form.getlist('student_classes')
            user.classes.clear()
            if student_class_ids:
                teacher_class_ids = [str(c.id) for c in current_user.teaching_classes]
                valid_class_ids = [cid for cid in student_class_ids if cid in teacher_class_ids]
                classes_to_assign = Class.query.filter(Class.id.in_(valid_class_ids)).all()
                user.classes.extend(classes_to_assign)
        
        db.session.commit()
        flash(f'用户 {user.real_name} 信息已更新')
        return redirect(url_for('user_mgmt.manage_users'))
    
    available_classes = get_available_classes()
    return render_template('edit_user.html', user=user, available_classes=available_classes)


@bp.route('/<int:user_id>/reset-password', methods=['POST'])
@login_required
@require_teacher_or_admin
def reset_user_password(user_id):
    """重置用户密码"""
    user = User.query.get_or_404(user_id)
    
    # 权限检查
    if not current_user.is_super_admin:
        if user.role != UserRole.STUDENT:
            flash('您没有权限重置此用户的密码')
            return redirect(url_for('user_mgmt.manage_users'))
        
        student_in_teacher_classes = False
        for class_obj in current_user.teaching_classes:
            if user in class_obj.students:
                student_in_teacher_classes = True
                break
        
        if not student_in_teacher_classes:
            flash('您没有权限重置此用户的密码')
            return redirect(url_for('user_mgmt.manage_users'))
    
    if user.id == current_user.id:
        flash('不能重置自己的密码，请使用修改密码功能')
        return redirect(url_for('user_mgmt.manage_users'))
    
    default_password = '123456'
    user.set_password(default_password)
    if not user.is_super_admin:
        user.must_change_password = True
    
    db.session.commit()
    flash(f'用户 {user.real_name} 的密码已重置为默认密码：{default_password}，该用户下次登录时必须修改密码')
    return redirect(url_for('user_mgmt.manage_users'))


@bp.route('/<int:user_id>/delete', methods=['POST'])
@login_required
@require_teacher_or_admin
def delete_user(user_id):
    """删除用户"""
    user = User.query.get_or_404(user_id)
    
    # 权限检查
    if not current_user.is_super_admin:
        if user.role != UserRole.STUDENT:
            flash('您没有权限删除此用户')
            return redirect(url_for('user_mgmt.manage_users'))
        
        student_in_teacher_classes = False
        for class_obj in current_user.teaching_classes:
            if user in class_obj.students:
                student_in_teacher_classes = True
                break
        
        if not student_in_teacher_classes:
            flash('您没有权限删除此用户')
            return redirect(url_for('user_mgmt.manage_users'))
    
    if user.id == current_user.id:
        flash('不能删除自己的账户')
        return redirect(url_for('user_mgmt.manage_users'))
    
    real_name = user.real_name
    
    # 删除用户相关的通知（作为发送者或接收者）
    Notification.query.filter(
        (Notification.sender_id == user.id) | (Notification.receiver_id == user.id)
    ).delete(synchronize_session=False)
    
    # 删除用户
    db.session.delete(user)
    db.session.commit()
    
    flash(f'用户 {real_name} 已删除')
    return redirect(url_for('user_mgmt.manage_users'))


def get_available_classes():
    """获取可用班级列表"""
    if current_user.is_super_admin:
        return Class.query.filter_by(is_active=True).all()
    else:
        return current_user.teaching_classes

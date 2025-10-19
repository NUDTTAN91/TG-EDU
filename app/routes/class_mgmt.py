"""班级管理路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import os
from app.extensions import db
from app.models import User, UserRole, Class, Assignment
from app.utils import require_teacher_or_admin, require_role

bp = Blueprint('class_mgmt', __name__, url_prefix='/admin/classes')


@bp.route('/')
@login_required
@require_teacher_or_admin
def manage_classes():
    """班级管理列表"""
    if current_user.is_super_admin:
        classes = Class.query.order_by(Class.created_at.desc()).all()
    else:
        # 教师只能看到自己的班级
        classes = current_user.teaching_classes
    
    return render_template('manage_classes.html', classes=classes)


@bp.route('/add', methods=['GET', 'POST'])
@login_required
@require_role(UserRole.SUPER_ADMIN)
def add_class():
    """创建班级"""
    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        description = request.form.get('description', '')
        grade = request.form.get('grade', '')
        
        # 检查班级代码是否已存在
        if Class.query.filter_by(code=code).first():
            flash('班级代码已存在')
            return render_template('add_class.html')
        
        # 创建新班级
        new_class = Class(
            name=name,
            code=code,
            description=description,
            grade=grade,
            created_by=current_user.id
        )
        
        db.session.add(new_class)
        db.session.commit()
        
        flash(f'班级 {name} 创建成功！现在可以在创建用户时将教师和学生分配到该班级')
        return redirect(url_for('class_mgmt.manage_classes'))
    
    return render_template('add_class.html')


@bp.route('/<int:class_id>/edit', methods=['GET', 'POST'])
@login_required
@require_teacher_or_admin
def edit_class(class_id):
    """编辑班级"""
    class_obj = Class.query.get_or_404(class_id)
    
    # 权限检查
    if not current_user.is_super_admin:
        if current_user not in class_obj.teachers:
            flash('您没有权限编辑此班级')
            return redirect(url_for('class_mgmt.manage_classes'))
    
    if request.method == 'POST':
        class_obj.name = request.form['name']
        class_obj.code = request.form['code']
        class_obj.description = request.form.get('description', '')
        class_obj.grade = request.form.get('grade', '')
        class_obj.is_active = 'is_active' in request.form
        
        # 更新教师分配（只有超级管理员可以修改）
        if current_user.is_super_admin:
            teacher_ids = request.form.getlist('teachers')
            class_obj.teachers.clear()
            if teacher_ids:
                teachers = User.query.filter(
                    User.id.in_(teacher_ids),
                    User.role == UserRole.TEACHER
                ).all()
                class_obj.teachers.extend(teachers)
        
        db.session.commit()
        flash(f'班级 {class_obj.name} 信息已更新')
        return redirect(url_for('class_mgmt.manage_classes'))
    
    teachers = User.query.filter_by(role=UserRole.TEACHER).all()
    return render_template('edit_class.html', class_obj=class_obj, teachers=teachers)


@bp.route('/<int:class_id>/delete', methods=['POST'])
@login_required
@require_teacher_or_admin
def delete_class(class_id):
    """删除班级"""
    class_obj = Class.query.get_or_404(class_id)
    
    # 权限检查
    if not current_user.is_super_admin:
        # 教师只能删除自己负责的空班级
        if current_user not in class_obj.teachers:
            flash('您没有权限删除此班级')
            return redirect(url_for('class_mgmt.manage_classes'))
        
        # 检查班级是否为空
        if class_obj.students or class_obj.assignments:
            flash('只能删除没有学生和作业的空班级')
            return redirect(url_for('class_mgmt.manage_classes'))
    else:
        # 超级管理员删除班级时的清理工作
        class_obj.students.clear()
        class_obj.teachers.clear()
        
        # 删除相关作业和提交文件
        for assignment in class_obj.assignments:
            for submission in assignment.submissions:
                try:
                    if os.path.exists(submission.file_path):
                        os.remove(submission.file_path)
                except Exception as e:
                    print(f"删除文件失败: {e}")
    
    class_name = class_obj.name
    db.session.delete(class_obj)
    db.session.commit()
    
    flash(f'班级 "{class_name}" 已成功删除')
    return redirect(url_for('class_mgmt.manage_classes'))


@bp.route('/<int:class_id>/students')
@login_required
@require_teacher_or_admin
def class_students(class_id):
    """班级学生管理"""
    class_obj = Class.query.get_or_404(class_id)
    
    # 权限检查
    if not current_user.is_super_admin:
        if current_user not in class_obj.teachers:
            flash('您没有权限管理此班级')
            return redirect(url_for('class_mgmt.manage_classes'))
    
    # 获取可以添加到班级的学生
    current_student_ids = [student.id for student in class_obj.students]
    available_students = User.query.filter(
        User.role == UserRole.STUDENT,
        ~User.id.in_(current_student_ids) if current_student_ids else True
    ).order_by(User.real_name).all()
    
    return render_template('class_students.html',
                         class_obj=class_obj,
                         available_students=available_students)


@bp.route('/<int:class_id>/add_student', methods=['POST'])
@login_required
@require_teacher_or_admin
def add_student_to_class(class_id):
    """添加学生到班级"""
    class_obj = Class.query.get_or_404(class_id)
    student_id = request.form.get('student_id')
    
    # 权限检查
    if not current_user.is_super_admin:
        if current_user not in class_obj.teachers:
            flash('您没有权限管理此班级')
            return redirect(url_for('class_mgmt.manage_classes'))
    
    student = User.query.filter_by(id=student_id, role=UserRole.STUDENT).first()
    if not student:
        flash('学生不存在')
        return redirect(url_for('class_mgmt.class_students', class_id=class_id))
    
    if student in class_obj.students:
        flash(f'{student.real_name} 已经在班级中')
    else:
        class_obj.students.append(student)
        db.session.commit()
        flash(f'已将 {student.real_name} 添加到班级')
    
    return redirect(url_for('class_mgmt.class_students', class_id=class_id))


@bp.route('/<int:class_id>/remove_student', methods=['POST'])
@login_required
@require_teacher_or_admin
def remove_student_from_class(class_id):
    """从班级移除学生"""
    class_obj = Class.query.get_or_404(class_id)
    student_id = request.form.get('student_id')
    student = User.query.get_or_404(student_id)
    
    # 权限检查
    if not current_user.is_super_admin:
        if current_user not in class_obj.teachers:
            flash('您没有权限管理此班级')
            return redirect(url_for('class_mgmt.manage_classes'))
    
    if student in class_obj.students:
        class_obj.students.remove(student)
        db.session.commit()
        flash(f'已将 {student.real_name} 从班级中移除')
    else:
        flash(f'{student.real_name} 不在此班级中')
    
    return redirect(url_for('class_mgmt.class_students', class_id=class_id))


@bp.route('/<int:class_id>/grades')
@login_required
@require_teacher_or_admin
def class_grades(class_id):
    """班级成绩统计"""
    class_obj = Class.query.get_or_404(class_id)
    
    # 权限检查
    if not current_user.is_super_admin:
        if current_user not in class_obj.teachers:
            flash('您没有权限查看此班级成绩')
            return redirect(url_for('class_mgmt.manage_classes'))
    
    # 获取班级所有作业
    assignments = Assignment.query.filter_by(class_id=class_id).order_by(Assignment.created_at).all()
    
    # 获取班级所有学生
    students = class_obj.students
    
    # 构建成绩统计数据
    from app.models import Submission, AssignmentGrade
    
    grade_stats = []
    for student in students:
        student_data = {
            'student': student,
            'grades': {},
            'graded_count': 0,
            'average': 0
        }
        
        total_average = 0
        graded_assignments = 0
        
        for assignment in assignments:
            # 使用新的评分系统获取平均分
            avg_grade = get_student_assignment_average_grade(assignment.id, student.id)
            
            if avg_grade is not None:
                student_data['grades'][assignment.id] = avg_grade
                total_average += avg_grade
                graded_assignments += 1
            else:
                # 尝试从旧系统获取
                submission = Submission.query.filter_by(
                    assignment_id=assignment.id,
                    student_id=student.id
                ).filter(Submission.grade.isnot(None)).order_by(
                    Submission.graded_at.desc()
                ).first()
                
                if submission and submission.grade is not None:
                    student_data['grades'][assignment.id] = submission.grade
                    total_average += submission.grade
                    graded_assignments += 1
        
        # 计算平均分
        if graded_assignments > 0:
            student_data['average'] = round(total_average / graded_assignments, 2)
            student_data['graded_count'] = graded_assignments
        
        grade_stats.append(student_data)
    
    # 按平均分排序
    grade_stats.sort(key=lambda x: x['average'], reverse=True)
    
    # 添加排名
    for rank, student_data in enumerate(grade_stats, 1):
        student_data['rank'] = rank
    
    return render_template('class_grades.html',
                         class_obj=class_obj,
                         assignments=assignments,
                         grade_stats=grade_stats)


def get_student_assignment_average_grade(assignment_id, student_id):
    """获取学生在某作业的平均分"""
    from app.models import AssignmentGrade
    from sqlalchemy import func
    
    avg_grade = db.session.query(func.avg(AssignmentGrade.grade)).filter(
        AssignmentGrade.assignment_id == assignment_id,
        AssignmentGrade.student_id == student_id
    ).scalar()
    
    return round(avg_grade, 2) if avg_grade is not None else None

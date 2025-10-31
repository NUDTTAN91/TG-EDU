"""批量导入/导出功能路由"""
import csv
import time
from io import StringIO
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models import User, Class, UserRole
from app.utils.decorators import require_role, require_teacher_or_admin

bp = Blueprint('import_export', __name__, url_prefix='/admin')


@bp.route('/users/batch-import', methods=['POST'])
@login_required
@require_teacher_or_admin
def batch_import_users():
    """批量导入用户（CSV/TSV/TXT格式）。超级管理员可导入所有类型用户，普通教师只能导入学生"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '请选择文件'})
    
    if not (file.filename.endswith('.csv') or file.filename.endswith('.tsv') or file.filename.endswith('.txt')):
        return jsonify({'success': False, 'message': '只支持CSV/TSV/TXT文件'})
    
    try:
        # 读取文件，使用更健壮的编码处理
        file_content = file.stream.read()
        
        # 尝试不同的编码方式解码
        encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'cp1252']
        decoded_content = None
        used_encoding = None
        
        for encoding in encodings:
            try:
                decoded_content = file_content.decode(encoding)
                used_encoding = encoding
                current_app.logger.info(f"成功使用编码: {encoding}")
                break
            except UnicodeDecodeError as e:
                current_app.logger.warning(f"编码 {encoding} 失败: {e}")
                continue
        
        if decoded_content is None:
            return jsonify({'success': False, 'message': '无法解码文件，请确保文件编码正确(支持UTF-8, GBK, GB2312等)'})
        
        # 使用解码后的内容创建StringIO对象
        csv_data = StringIO(decoded_content)
        
        # 检测分隔符：优先使用制表符，然后是逗号
        sample = decoded_content[:1024]  # 取前1024个字符作为样本
        if '\t' in sample:
            delimiter = '\t'
            current_app.logger.info("检测到制表符分隔")
        else:
            delimiter = ','
            current_app.logger.info("使用逗号分隔")
        
        try:
            reader = csv.DictReader(csv_data, delimiter=delimiter)
            # 验证CSV格式
            fieldnames = reader.fieldnames
            current_app.logger.info(f"CSV字段: {fieldnames}")
            
            if not fieldnames:
                return jsonify({'success': False, 'message': 'CSV文件格式不正确，请检查文件内容'})
            
            # 检查必要字段
            required_fields = ['姓名', '密码', '用户类型']
            missing_fields = [field for field in required_fields if field not in fieldnames]
            if missing_fields:
                return jsonify({
                    'success': False, 
                    'message': f'CSV文件缺少必要字段: {", ".join(missing_fields)}。必要字段包括: 姓名, 密码, 用户类型'
                })
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'CSV文件格式错误: {str(e)}'})
        
        # 重新创建reader来处理数据
        csv_data = StringIO(decoded_content)
        reader = csv.DictReader(csv_data, delimiter=delimiter)
        
        success_count = 0
        error_count = 0
        errors = []
        
        # 开始事务处理
        try:
            # 缓存已创建的班级，避免重复查询
            created_classes = {}
            
            # 使用session.no_autoflush防止自动刷新导致的问题
            with db.session.no_autoflush:
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # 获取并清理数据
                        real_name = row.get('姓名', '').strip()
                        password = row.get('密码', '').strip()
                        class_name = row.get('班级', '').strip()
                        role = row.get('用户类型', '').strip().lower()
                        id_number = row.get('学号/教工号', '').strip()
                        
                        current_app.logger.info(f"处理第{row_num}行: {real_name}, {role}, {class_name}")
                        
                        # 验证必要字段
                        if not real_name or not password or not role:
                            errors.append(f'第{row_num}行: 缺少必要字段(姓名、密码、用户类型)')
                            error_count += 1
                            continue
                        
                        # 验证用户类型
                        if role not in ['student', 'teacher']:
                            errors.append(f'第{row_num}行: 无效的用户类型 "{role}"，应为 "student" 或 "teacher"')
                            error_count += 1
                            continue
                        
                        # 普通教师只能导入学生
                        if not current_user.is_super_admin and role != 'student':
                            errors.append(f'第{row_num}行: 普通教师只能导入学生，无法导入教师')
                            error_count += 1
                            continue
                        
                        # 检查用户名是否已存在（通过用户名）
                        if User.query.filter_by(username=real_name).first():
                            errors.append(f'第{row_num}行: 用户名 "{real_name}" 已存在')
                            error_count += 1
                            continue
                        
                        # 检查真实姓名是否已存在
                        if User.query.filter_by(real_name=real_name).first():
                            errors.append(f'第{row_num}行: 用户 "{real_name}" 已存在')
                            error_count += 1
                            continue
                        
                        # 检查学号/教工号是否已存在（如果提供了）
                        if id_number and User.query.filter_by(student_id=id_number).first():
                            errors.append(f'第{row_num}行: 学号/教工号 "{id_number}" 已存在')
                            error_count += 1
                            continue
                        
                        # 创建用户
                        user = User(
                            username=real_name,  # 用户名和真实姓名相同
                            real_name=real_name,
                            role=role,
                            student_id=id_number if id_number else None,
                            created_by=current_user.id
                        )
                        user.set_password(password)
                        
                        db.session.add(user)
                        current_app.logger.info(f"创建用户: {real_name}")
                        
                        # 处理班级（在缓存中查找或创建）
                        class_obj = None
                        if class_name:
                            if class_name in created_classes:
                                # 从缓存中获取
                                class_obj = created_classes[class_name]
                                current_app.logger.info(f"从缓存中获取班级: {class_name}")
                            else:
                                # 查找数据库中的班级
                                class_obj = Class.query.filter_by(name=class_name).first()
                                if not class_obj:
                                    # 创建新班级
                                    class_code = f"C{int(time.time()*1000) % 1000000}"  # 使用时间戳生成唯一代码
                                    class_obj = Class(
                                        name=class_name,
                                        code=class_code,
                                        created_by=current_user.id
                                    )
                                    db.session.add(class_obj)
                                    current_app.logger.info(f"创建新班级: {class_name} (代码: {class_code})")
                                
                                # 加入缓存
                                created_classes[class_name] = class_obj
                        
                        # 先刷新以获取ID
                        db.session.flush()
                        
                        # 班级关联操作在flush之后进行
                        if class_obj:
                            if role == 'student':
                                # 检查是否已经在班级中（学生用classes关系）
                                if class_obj not in user.classes:
                                    # 数据一致性检查：确保学生不会被错误地加入教师关系
                                    if class_obj in user.teaching_classes:
                                        current_app.logger.warning(f"发现数据不一致：学生 {real_name} 已在教师关系中，先移除")
                                        user.teaching_classes.remove(class_obj)
                                    
                                    user.classes.append(class_obj)
                                    current_app.logger.info(f"将学生 {real_name} 分配到班级 {class_name}")
                                
                                # 如果是普通教师导入的学生，自动将该班级划归教师管理
                                if not current_user.is_super_admin:
                                    if class_obj not in current_user.teaching_classes:
                                        current_user.teaching_classes.append(class_obj)
                                        current_app.logger.info(f"自动将班级 {class_name} 划归教师 {current_user.real_name} 管理")
                            elif role == 'teacher':
                                # 检查是否已经在班级中（教师用teaching_classes关系）
                                if class_obj not in user.teaching_classes:
                                    # 数据一致性检查：确保教师不会被错误地加入学生关系
                                    if class_obj in user.classes:
                                        current_app.logger.warning(f"发现数据不一致：教师 {real_name} 已在学生关系中，先移除")
                                        user.classes.remove(class_obj)
                                    
                                    user.teaching_classes.append(class_obj)
                                    current_app.logger.info(f"将教师 {real_name} 分配到班级 {class_name}")
                        
                        success_count += 1
                        current_app.logger.info(f"成功处理用户: {real_name}")
                        
                    except Exception as e:
                        error_msg = f'第{row_num}行: {str(e)}'
                        errors.append(error_msg)
                        error_count += 1
                        current_app.logger.error(error_msg)
            
            # 提交事务
            db.session.commit()
            
            # 构建结果消息
            message = f'导入完成：成功 {success_count} 个，失败 {error_count} 个'
            if errors and len(errors) <= 10:
                message += '<br><br>错误详情：<br>' + '<br>'.join(errors)
            elif errors:
                message += f'<br><br>错误详情（前10条）：<br>' + '<br>'.join(errors[:10])
                message += f'<br>...还有 {len(errors) - 10} 条错误未显示'
            
            return jsonify({
                'success': True,
                'message': message,
                'success_count': success_count,
                'error_count': error_count,
                'errors': errors
            })
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"批量导入失败: {str(e)}")
            return jsonify({'success': False, 'message': f'导入失败: {str(e)}'})
    
    except Exception as e:
        current_app.logger.error(f"文件处理失败: {str(e)}")
        return jsonify({'success': False, 'message': f'文件处理失败: {str(e)}'})

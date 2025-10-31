"""批量导入/导出功能路由"""
import csv
import time
from io import StringIO, BytesIO
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

from app.extensions import db
from app.models import User, Class, UserRole
from app.utils.decorators import require_role, require_teacher_or_admin

bp = Blueprint('import_export', __name__, url_prefix='/admin')


def safe_str(value):
    """安全转换为字符串，处理NaN值"""
    if pd and PANDAS_AVAILABLE:
        if pd.isna(value) or value is None:
            return ''
    elif value is None:
        return ''
    return str(value).strip()


def detect_file_type(file_content):
    """通过文件魔数检测真实文件类型"""
    # Excel文件的魔数
    # XLSX: 50 4B 03 04 (PK..，ZIP格式)
    # XLS (BIFF8): D0 CF 11 E0 (OLE2格式)
    # XLS (BIFF5): 09 08 10 00 00 06 05 00
    
    if len(file_content) < 8:
        return 'unknown'
    
    # 检查前4个字节
    header = file_content[:4]
    
    # XLSX格式（ZIP压缩，PK开头）
    if header[:2] == b'PK':
        return 'xlsx'
    
    # XLS格式（OLE2文档）
    if header == b'\xD0\xCF\x11\xE0':
        return 'xls'
    
    # 检查是否是纯文本（CSV/TSV/TXT）
    # 尝试解码前100字节，如果成功且包含常见分隔符，认为是CSV
    try:
        sample = file_content[:100].decode('utf-8', errors='ignore')
        if ',' in sample or '\t' in sample or '\n' in sample:
            return 'csv'
    except:
        pass
    
    return 'unknown'


@bp.route('/users/batch-import', methods=['POST'])
@login_required
@require_teacher_or_admin
def batch_import_users():
    """批量导入用户（CSV/TSV/TXT/Excel格式）。超级管理员可导入所有类型用户，普通教师只能导入学生"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '请选择文件'})
    
    # 支持CSV、TSV、TXT和Excel格式
    allowed_extensions = ['.csv', '.tsv', '.txt', '.xlsx', '.xls']
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        return jsonify({'success': False, 'message': '只支持CSV/TSV/TXT/Excel文件（.csv, .tsv, .txt, .xlsx, .xls）'})
    
    try:
        # 读取文件内容用于类型检测
        file_content = file.stream.read()
        file.stream.seek(0)  # 重置文件指针
        
        # 检测真实文件类型（通过文件魔数，而不是扩展名）
        real_file_type = detect_file_type(file_content)
        current_app.logger.info(f"文件名: {file.filename}, 扩展名类型: {file.filename.split('.')[-1]}, 实际文件类型: {real_file_type}")
        
        # 根据实际文件类型判断是否为Excel
        is_excel = real_file_type in ['xlsx', 'xls']
        
        if is_excel:
            # 处理Excel文件（使用已读取的file_content）
            try:
                import pandas as pd
                from io import BytesIO
                
                # 使用BytesIO包装文件内容
                excel_file = BytesIO(file_content)
                
                # 根据实际文件类型选择引擎
                if real_file_type == 'xlsx':
                    df = pd.read_excel(excel_file, engine='openpyxl')
                else:  # xls
                    df = pd.read_excel(excel_file, engine='xlrd')
                
                # 检查DataFrame是否为空
                if df.empty:
                    return jsonify({'success': False, 'message': 'Excel文件为空或格式不正确'})
                
                # 清理列名：去除前后空格和BOM标记
                df.columns = df.columns.str.replace('\ufeff', '').str.strip()
                
                current_app.logger.info(f"Excel文件列名: {list(df.columns)}")
                
                # 检查必要字段
                required_fields = ['姓名', '密码', '用户类型']
                missing_fields = [field for field in required_fields if field not in df.columns]
                if missing_fields:
                    return jsonify({
                        'success': False,
                        'message': f'Excel文件缺少必要字段: {", ".join(missing_fields)}。必要字段包括: 姓名, 密码, 用户类型。当前字段: {", ".join(list(df.columns))}'
                    })
                
                # 将DataFrame转换为字典列表，方便后续处理
                data_rows = df.to_dict('records')
                current_app.logger.info(f"Excel文件共 {len(data_rows)} 行数据")
                
            except Exception as e:
                current_app.logger.error(f"读取Excel文件失败: {str(e)}")
                import traceback
                current_app.logger.error(traceback.format_exc())
                return jsonify({'success': False, 'message': f'读取Excel文件失败: {str(e)}'})
        else:
            # 处理CSV/TSV/TXT文件（file_content已经读取）
        
            # 尝试不同的编码方式解码
            encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'cp1252', 'latin1', 'iso-8859-1', 'big5', 'shift_jis']
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
                except Exception as e:
                    current_app.logger.warning(f"编码 {encoding} 失败（其他错误）: {e}")
                    continue
            
            if decoded_content is None:
                # 尝试使用chardet库自动检测编码
                try:
                    import chardet
                    detected = chardet.detect(file_content)
                    if detected['confidence'] > 0.7:
                        encoding = detected['encoding']
                        decoded_content = file_content.decode(encoding)
                        current_app.logger.info(f"使用chardet检测到编码: {encoding} (置信度: {detected['confidence']})")
                    else:
                        current_app.logger.warning(f"chardet检测到的编码置信度不足: {detected['confidence']}")
                except Exception as e:
                    current_app.logger.warning(f"chardet检测失败: {e}")
            
            if decoded_content is None:
                return jsonify({'success': False, 'message': '无法解码文件，请确保文件编码正确(支持UTF-8, GBK, GB2312等)。建议使用UTF-8编码保存CSV文件或直接使用Excel文件。'})
            
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
                current_app.logger.info(f"CSV原始字段: {fieldnames}")
                
                if not fieldnames:
                    return jsonify({'success': False, 'message': 'CSV文件格式不正确，请检查文件内容。建议使用Excel文件格式。'})
                
                # 清理字段名：去除前后空格和BOM标记
                cleaned_fieldnames = []
                for field in fieldnames:
                    if field:
                        # 去除BOM标记（如果存在）
                        cleaned = field.replace('\ufeff', '').strip()
                        cleaned_fieldnames.append(cleaned)
                    else:
                        cleaned_fieldnames.append('')
                
                current_app.logger.info(f"CSV清理后字段: {cleaned_fieldnames}")
                
                # 检查必要字段（使用清理后的字段名）
                required_fields = ['姓名', '密码', '用户类型']
                missing_fields = [field for field in required_fields if field not in cleaned_fieldnames]
                if missing_fields:
                    return jsonify({
                        'success': False, 
                        'message': f'CSV文件缺少必要字段: {", ".join(missing_fields)}。必要字段包括: 姓名, 密码, 用户类型。当前字段: {", ".join(cleaned_fieldnames)}。建议使用Excel文件格式。'
                    })
                
            except Exception as e:
                return jsonify({'success': False, 'message': f'CSV文件格式错误: {str(e)}。建议使用Excel文件格式。'})
            
            # 重新创建reader来处理数据
            csv_data = StringIO(decoded_content)
            reader_raw = csv.DictReader(csv_data, delimiter=delimiter)
            
            # 创建字段名映射：原始字段名 -> 清理后的字段名
            field_mapping = {}
            if reader_raw.fieldnames:
                for field in reader_raw.fieldnames:
                    if field:
                        cleaned = field.replace('\ufeff', '').strip()
                        field_mapping[field] = cleaned
            
            current_app.logger.info(f"字段映射: {field_mapping}")
            
            # 将CSV数据转换为字典列表，与Excel格式统一
            data_rows = []
            for row in reader_raw:
                row_cleaned = {}
                for original_field, value in row.items():
                    cleaned_field = field_mapping.get(original_field, original_field)
                    row_cleaned[cleaned_field] = value
                data_rows.append(row_cleaned)
            
            current_app.logger.info(f"CSV文件共 {len(data_rows)} 行数据")
        
        success_count = 0
        error_count = 0
        errors = []
        
        # 开始事务处理
        try:
            # 缓存已创建的班级，避免重复查询
            created_classes = {}
            
            # 使用session.no_autoflush防止自动刷新导致的问题
            with db.session.no_autoflush:
                for row_num, row_data in enumerate(data_rows, start=2):
                    try:
                        # 获取并清理数据（处理NaN值）
                        real_name = safe_str(row_data.get('姓名', ''))
                        password = safe_str(row_data.get('密码', ''))
                        class_name = safe_str(row_data.get('班级', ''))
                        role = safe_str(row_data.get('用户类型', '')).lower()
                        id_number = safe_str(row_data.get('学号/教工号', ''))
                        
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

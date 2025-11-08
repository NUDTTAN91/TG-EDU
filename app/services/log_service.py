"""操作日志服务"""
from flask import request
from flask_login import current_user
from app.extensions import db
from app.models.operation_log import OperationLog
import json
from datetime import datetime
import os

# IP定位相关
try:
    from ip2region import util, searcher
    IP2REGION_AVAILABLE = True
except ImportError:
    IP2REGION_AVAILABLE = False
    print("警告: ip2region库未安装，IP地理位置功能不可用")


class LogService:
    """日志服务类"""
    
    # IP2Region搜索器实例（单例模式）
    _ip2region_searcher = None
    
    @classmethod
    def get_ip2region_searcher(cls):
        """获取IP2Region搜索器实例"""
        if cls._ip2region_searcher is None and IP2REGION_AVAILABLE:
            try:
                # 查找ip2region.xdb文件
                xdb_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'ip2region.xdb')
                if not os.path.exists(xdb_path):
                    # 如果主文件不存在，尝试使用v4版本
                    xdb_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'ip2region_v4.xdb')
                if os.path.exists(xdb_path):
                    # 先加载header获取版本
                    header = util.load_header_from_file(xdb_path)
                    version = util.version_from_header(header)
                    # 使用检测到的版本创建searcher
                    cls._ip2region_searcher = searcher.new_with_file_only(version, xdb_path)
                else:
                    print(f"警告: ip2region.xdb文件不存在: {xdb_path}")
            except Exception as e:
                print(f"初始化IP2Region失败: {e}")
        return cls._ip2region_searcher
    
    @classmethod
    def get_ip_location(cls, ip_address):
        """获取IP地理位置，返回格式：IP地址（地点（运营商））"""
        if not ip_address or ip_address == '127.0.0.1' or ip_address.startswith('192.168.'):
            return f'{ip_address}（本地网络）'
        
        searcher = cls.get_ip2region_searcher()
        if searcher is None:
            return ip_address  # 如果searcher不可用，只返回IP地址
        
        try:
            # py-ip2region 返回的是字符串格式: '国家|省份|城市|ISP'
            result = searcher.search(ip_address)
            if result:
                # result格式: 国家|省份|城市|ISP
                # 例如: 中国|广东省|广州市|电信
                parts = result.split('|')
                location_parts = []
                
                # 国家
                if len(parts) > 0 and parts[0] and parts[0] != '0':
                    location_parts.append(parts[0])
                
                # 省份
                if len(parts) > 1 and parts[1] and parts[1] != '0':
                    location_parts.append(parts[1])
                
                # 城市
                if len(parts) > 2 and parts[2] and parts[2] != '0':
                    location_parts.append(parts[2])
                
                # ISP
                isp = ''
                if len(parts) > 3 and parts[3] and parts[3] != '0':
                    isp = parts[3]
                
                if location_parts:
                    location = ' '.join(location_parts)
                    # 格式：IP地址（地点（运营商））
                    if isp:
                        return f'{ip_address}（{location}（{isp}））'
                    else:
                        return f'{ip_address}（{location}）'
        except Exception as e:
            print(f"解析IP地址失败 {ip_address}: {e}")
        
        return ip_address  # 解析失败时只返回IP地址
    
    @staticmethod
    def log_operation(operation_type, operation_desc, result='success', error_msg=None):
        """
        记录操作日志
        
        Args:
            operation_type: 操作类型（login, submit, view, apply, create, update, delete等）
            operation_desc: 操作描述
            result: 操作结果（success, failed）
            error_msg: 错误信息
        """
        try:
            # 获取请求信息
            ip_address = request.remote_addr if request else None
            ip_location = None
            if ip_address:
                ip_location = LogService.get_ip_location(ip_address)
            
            user_agent = request.headers.get('User-Agent', '') if request else ''
            request_method = request.method if request else None
            request_path = request.path if request else None
            
            # 获取请求参数（排除敏感信息）
            request_params = None
            if request:
                params = {}
                if request.args:
                    params['query'] = dict(request.args)
                if request.form:
                    form_data = dict(request.form)
                    # 排除密码等敏感信息
                    if 'password' in form_data:
                        form_data['password'] = '***'
                    if 'new_password' in form_data:
                        form_data['new_password'] = '***'
                    if 'confirm_password' in form_data:
                        form_data['confirm_password'] = '***'
                    params['form'] = form_data
                
                if params:
                    request_params = json.dumps(params, ensure_ascii=False)
            
            # 获取用户信息
            user_id = None
            username = 'Anonymous'
            user_role = 'guest'
            
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
                username = current_user.username
                user_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
            
            # 创建日志记录
            log = OperationLog(
                user_id=user_id,
                username=username,
                user_role=user_role,
                operation_type=operation_type,
                operation_desc=operation_desc,
                ip_address=ip_address,
                ip_location=ip_location,
                user_agent=user_agent,
                request_method=request_method,
                request_path=request_path,
                request_params=request_params,
                result=result,
                error_msg=error_msg,
                created_at=datetime.utcnow()
            )
            
            db.session.add(log)
            db.session.commit()
            
        except Exception as e:
            print(f"记录日志失败: {e}")
            # 日志记录失败不应影响主业务
            try:
                db.session.rollback()
            except:
                pass
    
    @staticmethod
    def get_logs(page=1, per_page=50, user_id=None, operation_type=None, start_date=None, end_date=None):
        """
        获取日志列表
        
        Args:
            page: 页码
            per_page: 每页数量
            user_id: 用户ID过滤
            operation_type: 操作类型过滤
            start_date: 开始日期
            end_date: 结束日期
        """
        query = OperationLog.query
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        if operation_type:
            query = query.filter_by(operation_type=operation_type)
        
        if start_date:
            query = query.filter(OperationLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(OperationLog.created_at <= end_date)
        
        # 按时间倒序
        query = query.order_by(OperationLog.created_at.desc())
        
        return query.paginate(page=page, per_page=per_page, error_out=False)
    
    @staticmethod
    def get_operation_stats():
        """获取操作统计信息"""
        from sqlalchemy import func
        
        stats = {
            'total_logs': OperationLog.query.count(),
            'today_logs': OperationLog.query.filter(
                func.date(OperationLog.created_at) == datetime.utcnow().date()
            ).count(),
            'operation_type_stats': db.session.query(
                OperationLog.operation_type,
                func.count(OperationLog.id)
            ).group_by(OperationLog.operation_type).all(),
            'user_stats': db.session.query(
                OperationLog.username,
                func.count(OperationLog.id)
            ).filter(
                OperationLog.user_id.isnot(None)
            ).group_by(OperationLog.username).order_by(
                func.count(OperationLog.id).desc()
            ).limit(10).all()
        }
        
        return stats

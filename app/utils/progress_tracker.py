"""批量下载进度跟踪工具"""
import os
import json
import time
from threading import Lock

class ProgressTracker:
    """基于文件系统的进度跟踪器，支持多worker环境"""
    
    def __init__(self, storage_dir='/app/storage/data'):
        self.storage_dir = storage_dir
        self.lock = Lock()
        os.makedirs(storage_dir, exist_ok=True)
    
    def _get_progress_file(self, user_id, extra_key=None):
        """获取进度文件路径"""
        if extra_key:
            return os.path.join(self.storage_dir, f'download_progress_{user_id}_{extra_key}.json')
        return os.path.join(self.storage_dir, f'batch_download_progress_{user_id}.json')
    
    def set_progress(self, user_id, progress_data, extra_key=None):
        """设置进度数据"""
        import logging
        logger = logging.getLogger(__name__)
        
        progress_file = self._get_progress_file(user_id, extra_key)
        
        # 添加时间戳
        progress_data['updated_at'] = time.time()
        
        logger.warning(f"[进度跟踪器] 写入进度: 用户{user_id}, key={extra_key or 'batch'}, 状态={progress_data.get('status')}, 进度={progress_data.get('progress')}%")
        
        with self.lock:
            try:
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress_data, f, ensure_ascii=False)
                logger.warning(f"[进度跟踪器] 进度文件写入成功: {progress_file}")
            except Exception as e:
                logger.error(f'[进度跟踪器] 写入进度文件失败: {e}')
                import traceback
                logger.error(traceback.format_exc())
    
    def get_progress(self, user_id, extra_key=None):
        """获取进度数据"""
        import logging
        logger = logging.getLogger(__name__)
        
        progress_file = self._get_progress_file(user_id, extra_key)
        
        if not os.path.exists(progress_file):
            logger.warning(f"[进度跟踪器] 进度文件不存在: {progress_file}, 返回completed状态（可能已完成）")
            # 返回completed状态，而不是pending，因为文件不存在通常意味着任务已完成
            return {
                'status': 'completed',
                'progress': 100,
                'message': '下载已完成'
            }
        
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.warning(f"[进度跟踪器] 读取进度: 用户{user_id}, key={extra_key or 'batch'}, 状态={data.get('status')}, 进度={data.get('progress')}%")
                
            # 检查是否超时（5分钟）
            if 'updated_at' in data:
                elapsed = time.time() - data['updated_at']
                if elapsed > 300 and data.get('status') not in ['completed', 'error']:
                    logger.warning(f"[进度跟踪器] 检测到超时 ({elapsed:.1f}秒), 标记为完成")
                    data['status'] = 'completed'
                    data['progress'] = 100
                    data['message'] = '下载已完成（检测到超时）'
                    data['timeout'] = True
            
            return data
        except Exception as e:
            logger.error(f'[进度跟踪器] 读取进度文件失败: {e}')
            import traceback
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'progress': 0,
                'message': f'读取进度失败: {str(e)}'
            }
    
    def clear_progress(self, user_id, extra_key=None):
        """清理进度数据"""
        import logging
        logger = logging.getLogger(__name__)
        
        progress_file = self._get_progress_file(user_id, extra_key)
        
        logger.warning(f"[进度跟踪器] 清理进度文件: {progress_file}")
        
        with self.lock:
            try:
                if os.path.exists(progress_file):
                    os.remove(progress_file)
                    logger.warning(f"[进度跟踪器] 进度文件删除成功")
                else:
                    logger.warning(f"[进度跟踪器] 进度文件不存在，无需删除")
            except Exception as e:
                logger.error(f'[进度跟踪器] 删除进度文件失败: {e}')


# 全局实例
progress_tracker = ProgressTracker()

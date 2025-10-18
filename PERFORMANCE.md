# 性能优化说明

## 高并发优化措施

为了解决学生集中登录时系统无响应的问题，本系统进行了以下优化：

### 1. Gunicorn服务器配置优化

#### 使用Gevent异步Worker
- **原配置**：4个同步worker，最多支持4个并发请求
- **优化后**：8个gevent异步worker，每个支持1000个并发连接
- **提升效果**：理论最大并发从4提升到8000

#### Worker配置参数
```bash
--workers 8                    # worker进程数 (2 * CPU核心数 + 1)
--worker-class gevent          # 使用gevent异步worker
--worker-connections 1000      # 每个worker最大连接数
--timeout 120                  # 请求超时时间(秒)
--max-requests 1000           # worker处理请求数上限后自动重启
--max-requests-jitter 100     # 重启时间随机抖动，避免同时重启
```

### 2. SQLite数据库优化

#### 连接池配置
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 20,              # 连接池大小
    'pool_recycle': 3600,         # 连接回收时间(秒)
    'pool_pre_ping': True,        # 连接前检查
    'max_overflow': 10,           # 超出pool_size时最多创建的连接数
    'connect_args': {
        'timeout': 30,            # 数据库锁等待超时(秒)
        'check_same_thread': False # 允许多线程访问
    }
}
```

#### 锁等待优化
- 设置30秒的锁等待超时，避免长时间阻塞
- 启用WAL模式（Write-Ahead Logging）提高并发读写性能

### 3. 数据库查询优化

#### 首页查询优化
- **原查询**：`Assignment.query.order_by(...).all()` - 查询所有作业
- **优化后**：`Assignment.query.filter_by(is_active=True).limit(50).all()` - 只查询活跃作业，限制50条
- **提升效果**：减少数据库I/O，加快响应速度

#### 学生仪表板查询优化
- **原实现**：分两次查询班级作业和公共作业，再合并排序
- **优化后**：使用单次OR查询，减少数据库访问
- **限制记录数**：作业列表限制100条，提交记录限制50条

#### 会话管理优化
- 添加 `@app.teardown_appcontext` 自动关闭数据库会话
- 避免连接泄漏和资源占用

### 4. 依赖包更新

新增依赖：
- `gevent==23.9.1` - 高性能协程库，支持异步I/O

## 性能指标对比

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 最大并发连接 | 4 | 8000 | 2000倍 |
| Worker数量 | 4 (sync) | 8 (gevent) | 2倍 + 异步 |
| 请求超时时间 | 600秒 | 120秒 | 更快失败 |
| 数据库连接池 | 未配置 | 20+10 | 复用连接 |
| 首页查询记录数 | 全部 | 最多50条 | 减少I/O |
| 学生查询记录数 | 全部 | 最多150条 | 减少I/O |

## 测试建议

### 并发测试工具
使用Apache Bench进行压力测试：
```bash
# 测试100个并发用户，总共1000个请求
ab -n 1000 -c 100 http://localhost/

# 测试登录页面
ab -n 500 -c 50 http://localhost/login
```

### 预期性能
- **并发用户数**：支持100+学生同时在线
- **响应时间**：首页 < 1秒，登录 < 2秒
- **错误率**：< 1%

## 进一步优化建议

如果学生数量超过500人，建议考虑以下升级方案：

### 1. 数据库升级
- 迁移到PostgreSQL或MySQL
- 支持真正的并发读写
- 更好的锁机制

### 2. 缓存层
- 使用Redis缓存作业列表
- 减少数据库查询压力

### 3. 负载均衡
- 使用Nginx进行负载均衡
- 部署多个应用实例
- 水平扩展能力

### 4. 静态资源CDN
- 将CSS、JS、图片等静态资源放到CDN
- 减轻服务器负担

## 监控建议

### 关键指标监控
1. **响应时间**：平均响应时间应 < 2秒
2. **错误率**：HTTP 5xx错误率应 < 1%
3. **Worker状态**：监控worker重启频率
4. **数据库连接**：监控连接池使用率

### 日志查看
```bash
# 查看实时日志
docker-compose logs -f tg-edu-system

# 查看错误日志
docker-compose logs tg-edu-system | grep -i error

# 查看慢查询（超过2秒）
docker-compose logs tg-edu-system | grep -E "duration.*[2-9][0-9]{3}ms"
```

## 故障排查

### 问题：仍然出现超时
**原因**：并发数超过系统承载能力
**解决**：
1. 增加worker数量：`--workers 16`
2. 检查数据库文件是否在机械硬盘上（建议SSD）
3. 考虑升级到PostgreSQL

### 问题：数据库锁错误
**原因**：SQLite写入冲突
**解决**：
1. 启用WAL模式（已自动配置）
2. 减少写入操作
3. 考虑迁移到PostgreSQL

### 问题：内存占用过高
**原因**：Worker进程过多或内存泄漏
**解决**：
1. 降低worker数量
2. 启用max-requests自动重启
3. 监控内存使用情况

## 配置文件位置

- Gunicorn配置：`/root/Desktop/TG-EDU/start.sh`
- 数据库配置：`/root/Desktop/TG-EDU/app.py` (SQLALCHEMY_ENGINE_OPTIONS)
- 依赖包：`/root/Desktop/TG-EDU/requirements.txt`

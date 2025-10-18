# 作业收集系统

一个基于 Flask 的作业收集系统，支持学生在线提交作业，老师在线管理和下载作业。

## 功能特性

### 学生功能
- 查看当前可提交的作业列表
- 在线提交作业文件
- 支持多种文件格式（txt, pdf, doc, docx, zip, rar, py, java, cpp, c, html, css, js）
- 添加作业提交备注

### 教师功能
- 安全的管理员登录系统
- 创建和管理作业
- 设置作业截止时间
- 查看学生提交列表
- 下载学生提交的作业文件
- 查看作业提交统计

## 技术栈

- **后端**: Flask + SQLAlchemy + Flask-Login
- **前端**: Bootstrap 5 + Jinja2 模板
- **数据库**: SQLite
- **部署**: Docker + Docker Compose
- **基础镜像**: Ubuntu 20.04

## 快速开始

### 环境要求

- Docker
- Docker Compose

### 部署步骤

1. **克隆项目**
   ```bash
   git clone https://github.com/NUDTTAN91/TG-EDU.git
   cd TG-EDU
   ```

2. **配置环境变量**
   
   复制环境变量示例文件：
   ```bash
   cp .env.example .env
   ```
   
   编辑 `.env` 文件或直接修改 `docker-compose.yml` 中的环境变量：
   ```yaml
   environment:
     - ADMIN_USERNAME=admin          # 管理员用户名
     - ADMIN_PASSWORD=homework2024   # 管理员密码
     - SECRET_KEY=your-secret-key-change-in-production  # 安全密钥
   ```

3. **启动服务**
   ```bash
   docker-compose up -d
   ```

4. **访问系统**
   
   打开浏览器访问：`http://localhost:8080`
   
   - 学生访问首页即可查看和提交作业
   - 教师点击右上角"教师登录"进入管理后台

## 注意事项

### 数据持久化

**重要提示**: 当前版本为了确保在各种环境下的兼容性，数据库和上传文件存储在容器内部。这意味着：

- 重启容器不会丢失数据
- 删除容器会丢失所有数据
- 如需数据持久化，建议定期备份容器内的数据

如需启用数据持久化，可以在 `docker-compose.yml` 中添加卷挂载：

```yaml
volumes:
  - ./uploads:/app/uploads
  - ./data:/app/data
```

并将 `app.py` 中的数据库路径修改为：
```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data/homework.db'
```

### 默认管理员账户

- 用户名：`admin`（可通过环境变量 `ADMIN_USERNAME` 修改）
- 密码：`homework2024`（可通过环境变量 `ADMIN_PASSWORD` 修改）

## 目录结构

```
TG-EDU/
├── app.py                    # Flask 应用主文件
├── requirements.txt          # Python 依赖
├── Dockerfile               # Docker 镜像构建文件
├── docker-compose.yml       # Docker Compose 配置
├── init_db.py              # 数据库初始化脚本
├── .env.example            # 环境变量示例
├── app/
│   ├── static/
│   │   └── css/
│   │       └── style.css   # 样式文件
│   └── templates/          # HTML 模板
│       ├── base.html       # 基础模板
│       ├── index.html      # 首页
│       ├── login.html      # 登录页
│       ├── admin.html      # 管理后台
│       ├── create_assignment.html  # 创建作业
│       ├── submit.html     # 提交作业
│       └── submissions.html # 作业提交列表
├── uploads/                # 上传文件存储目录
└── data/                   # 数据库文件存储目录
```

## 使用说明

### 教师操作流程

1. **登录管理后台**
   - 点击右上角"教师登录"
   - 使用管理员账户登录

2. **创建作业**
   - 在管理后台点击"创建新作业"
   - 填写作业标题、描述和截止时间
   - 点击"创建作业"

3. **查看提交**
   - 在管理后台点击"查看提交"
   - 查看学生提交列表
   - 下载学生作业文件

### 学生操作流程

1. **查看作业**
   - 访问系统首页
   - 查看当前可提交的作业列表

2. **提交作业**
   - 点击"提交作业"按钮
   - 填写学生信息（姓名、学号）
   - 选择作业文件
   - 添加备注（可选）
   - 点击"提交作业"

## 配置说明

### 环境变量

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `ADMIN_USERNAME` | 管理员用户名 | `admin` | 否 |
| `ADMIN_PASSWORD` | 管理员密码 | `admin123` | 否 |
| `SECRET_KEY` | Flask 安全密钥 | `dev-secret-key-change-in-production` | 否 |

### 文件上传限制

- 最大文件大小：由教师设置（可设置范围：1MB - 10GB）
- 支持的文件格式：txt, pdf, doc, docx, zip, rar, py, java, cpp, c, html, css, js

### 端口配置

- 默认访问端口：8080
- 可在 `docker-compose.yml` 中修改端口映射

## 数据持久化

系统使用本地目录挂载方式实现数据持久化，确保即使容器重启或更新，数据也不会丢失：

- `./data/` - SQLite 数据库文件目录
- `./uploads/` - 学生提交的作业文件目录

### 数据存储位置

```bash
# 直接在项目目录中查看数据
ls -la ./data/           # 数据库文件
ls -la ./uploads/        # 上传文件
```

### 数据备份和恢复

```bash
# 备份数据（建议定期备份）
tar czf homework-backup-$(date +%Y%m%d).tar.gz data/ uploads/

# 恢复数据
tar xzf homework-backup-YYYYMMDD.tar.gz

# 只备份数据库
cp data/homework.db data/homework.db.backup

# 恢复数据库
cp data/homework.db.backup data/homework.db
```

### 数据管理优势

- ✅ **直接访问**：数据文件直接存储在项目目录中，便于查看和管理
- ✅ **简单备份**：可以直接复制目录进行备份
- ✅ **易于迁移**：只需要复制 `data/` 和 `uploads/` 目录即可迁移数据
- ✅ **容器重启后数据不丢失**：数据存储在宿主机上
- ✅ **系统更新后数据保持完整**：重新构建镜像后数据保留

## 安全特性

- 管理员密码哈希存储
- 文件名安全处理，防止路径遍历攻击
- 文件类型限制
- 登录状态管理
- CSRF 保护

## 故障排除

### 常见问题

1. **无法访问系统**
   - 检查 Docker 容器是否正常运行：`docker-compose ps`
   - 检查端口是否被占用

2. **文件上传失败**
   - 检查文件大小是否超过 50MB 限制
   - 检查文件格式是否在支持列表中

3. **无法登录管理后台**
   - 检查用户名和密码是否正确
   - 检查环境变量配置

### 查看日志

```bash
# 查看容器日志
docker-compose logs tg-edu-system

# 实时查看日志
docker-compose logs -f tg-edu-system
```

### 重置系统

```bash
# 停止并删除容器
docker-compose down

# 删除数据（注意：这会删除所有作业和提交）
rm -rf uploads/* data/*

# 重新启动
docker-compose up -d
```

## 开发说明

### 本地开发

1. 安装 Python 依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 设置环境变量：
   ```bash
   export ADMIN_USERNAME=admin
   export ADMIN_PASSWORD=admin123
   ```

3. 运行应用：
   ```bash
   python app.py
   ```

### 自定义开发

- 修改模板文件可以自定义界面
- 修改 `app.py` 可以添加新功能
- 修改 CSS 文件可以调整样式

## License

MIT License

## 支持

如有问题，请提交 Issue 或联系系统管理员。
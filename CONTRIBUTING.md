# 贡献指南

感谢您考虑为 TG-EDU 作业收集系统做出贡献！

## 行为准则

参与本项目即表示您同意遵守我们的行为准则：
- 尊重所有贡献者
- 接受建设性的批评
- 专注于对社区最有利的事情
- 对其他社区成员表示同理心

## 如何贡献

### 报告Bug

在报告Bug之前，请：
1. 检查[现有Issues](https://github.com/NUDTTAN91/TG-EDU/issues)，确保问题未被报告
2. 使用最新版本测试，确认问题仍然存在
3. 收集相关信息（错误日志、系统环境等）

提交Bug时请使用[Bug报告模板](.github/ISSUE_TEMPLATE/bug_report.md)

### 建议新功能

我们欢迎新功能建议！请：
1. 检查功能是否已存在或正在开发中
2. 详细描述功能的使用场景
3. 使用[功能请求模板](.github/ISSUE_TEMPLATE/feature_request.md)

### 提交代码

#### 开发流程

1. **Fork 项目**
   ```bash
   # 在GitHub上点击Fork按钮
   ```

2. **克隆仓库**
   ```bash
   git clone https://github.com/YOUR_USERNAME/TG-EDU.git
   cd TG-EDU
   ```

3. **创建分支**
   ```bash
   # 功能分支
   git checkout -b feature/amazing-feature
   
   # Bug修复分支
   git checkout -b fix/bug-description
   
   # 文档分支
   git checkout -b docs/update-readme
   ```

4. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

5. **进行修改**
   - 编写代码
   - 添加测试
   - 更新文档

6. **测试变更**
   ```bash
   # 本地测试
   python app.py
   
   # Docker测试
   docker-compose up -d --build
   docker-compose logs -f
   ```

7. **提交变更**
   ```bash
   git add .
   git commit -m "feat: 添加新功能描述"
   ```
   
   提交信息格式：
   - `feat:` 新功能
   - `fix:` Bug修复
   - `docs:` 文档更新
   - `style:` 代码格式调整
   - `refactor:` 代码重构
   - `perf:` 性能优化
   - `test:` 测试相关
   - `chore:` 构建/工具变更

8. **推送到GitHub**
   ```bash
   git push origin feature/amazing-feature
   ```

9. **创建Pull Request**
   - 在GitHub上打开PR
   - 填写[PR模板](.github/pull_request_template.md)
   - 等待审查

#### 代码规范

**Python代码规范**
- 遵循 PEP 8 规范
- 使用4个空格缩进
- 函数和类添加文档字符串
- 变量名使用有意义的英文单词

**示例：**
```python
def calculate_submission_statistics(assignment_id):
    """
    计算作业提交统计信息
    
    Args:
        assignment_id (int): 作业ID
        
    Returns:
        dict: 包含统计信息的字典
    """
    # 实现代码
    pass
```

**HTML/CSS规范**
- 使用2个空格缩进
- 语义化HTML标签
- CSS类名使用kebab-case

**Git提交规范**
- 使用英文编写提交信息
- 第一行不超过50个字符
- 详细描述从第三行开始

### 文档贡献

文档同样重要！您可以：
- 修正拼写/语法错误
- 改进说明的清晰度
- 添加缺失的文档
- 翻译文档

### 测试要求

提交代码时请确保：
- [ ] 新功能有对应的测试
- [ ] 所有测试通过
- [ ] 代码覆盖率不降低

## 项目结构

```
TG-EDU/
├── app.py                    # 主应用文件
├── requirements.txt          # Python依赖
├── Dockerfile               # Docker镜像
├── docker-compose.yml       # Docker编排
├── app/
│   ├── static/              # 静态资源
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   └── templates/           # HTML模板
├── storage/                 # 数据存储
│   ├── data/               # 数据库
│   ├── uploads/            # 学生作业
│   └── appendix/           # 教师附件
├── .github/                # GitHub配置
└── docs/                   # 文档
```

## 开发环境设置

### 方式1：Docker开发（推荐）
```bash
docker-compose up -d --build
docker-compose logs -f
```

### 方式2：本地开发
```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin123
export SECRET_KEY=dev-secret-key

# 运行应用
python app.py
```

访问：http://localhost:5000

## 性能优化指南

提交性能相关的改进前，请：
1. 阅读 [PERFORMANCE.md](PERFORMANCE.md)
2. 进行性能测试对比
3. 提供测试数据和结果

## 安全问题

**请勿公开报告安全漏洞！**

如发现安全问题，请：
1. 发送邮件到项目维护者（通过GitHub私信）
2. 描述漏洞详情和影响范围
3. 建议的修复方案

## 获得帮助

遇到问题？
- 📖 查看 [README.md](README.md)
- 🚀 阅读 [PERFORMANCE.md](PERFORMANCE.md)
- 💬 在 [Issues](https://github.com/NUDTTAN91/TG-EDU/issues) 中提问
- 📧 联系维护者

## 感谢

感谢所有贡献者的付出！您的贡献让TG-EDU变得更好。

### 核心贡献者
- [@NUDTTAN91](https://github.com/NUDTTAN91) - 项目创建者和维护者

---

再次感谢您的贡献！🎉

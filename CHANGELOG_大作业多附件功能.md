# 大作业多附件功能更新说明

## 更新时间
2025-10-21

## 功能描述
将大作业系统从原来的"单个附件或单个链接"升级为"支持多个附件和多个链接，且可以同时存在"。

## 主要修改

### 1. 数据模型 (`app/models/team.py`)
#### 新增模型：
- **MajorAssignmentAttachment**: 大作业附件模型（支持多个附件）
  - `id`: 主键
  - `major_assignment_id`: 关联的大作业ID
  - `file_path`: 文件存储路径
  - `original_filename`: 原始文件名
  - `file_size`: 文件大小
  - `file_type`: 文件类型（默认'file'）
  - `uploaded_at`: 上传时间
  - `uploaded_by`: 上传者ID

- **MajorAssignmentLink**: 大作业链接模型（支持多个链接）
  - `id`: 主键
  - `major_assignment_id`: 关联的大作业ID
  - `url`: 链接地址
  - `title`: 链接标题
  - `description`: 链接描述
  - `created_at`: 创建时间
  - `created_by`: 创建者ID

#### 修改模型：
- **MajorAssignment**: 添加新的关系和辅助方法
  - 保留旧字段`requirement_file_path`和`requirement_url`以兼容旧数据
  - 新增`attachments`关系（一对多）
  - 新增`links`关系（一对多）
  - 新增`get_all_attachments()`方法：获取所有附件（包括新旧系统）
  - 新增`get_all_links()`方法：获取所有链接（包括新旧系统）

### 2. 路由修改 (`app/routes/major_assignment.py`)

#### 创建大作业功能：
- 支持通过`requirement_files`（多个）上传多个附件
- 支持通过`requirement_urls`和`requirement_url_titles`添加多个链接
- 保留旧的单文件/单链接方式以兼容现有前端

#### 编辑大作业功能：
- 支持添加新的附件和链接
- 支持删除已有的附件（通过`delete_attachments`）
- 支持删除已有的链接（通过`delete_links`）
- 删除附件时会同时删除物理文件

#### 新增路由：
- `GET /major_assignments/attachment/<int:attachment_id>/download`: 下载指定附件

### 3. 数据库迁移 (`migrate_major_assignment_attachments.py`)
自动创建两个新表：
- `major_assignment_attachment`
- `major_assignment_link`

### 4. Docker部署更新
- 更新`Dockerfile`：添加迁移脚本到镜像
- 更新`start.sh`：在启动时自动执行迁移

## 兼容性
- ✅ **向后兼容**：保留了旧的`requirement_file_path`和`requirement_url`字段
- ✅ **数据迁移**：旧数据会通过`get_all_attachments()`和`get_all_links()`方法自动包含
- ✅ **前端兼容**：同时支持新旧两种提交方式

## 前端需要的修改（待实现）

### 创建大作业页面：
```html
<!-- 多个附件上传 -->
<input type="file" name="requirement_files" multiple>

<!-- 多个链接输入 -->
<div id="links-container">
  <div class="link-item">
    <input type="text" name="requirement_url_titles[]" placeholder="链接标题">
    <input type="url" name="requirement_urls[]" placeholder="链接地址">
  </div>
</div>
<button type="button" onclick="addLinkInput()">+ 添加链接</button>
```

### 编辑大作业页面：
```html
<!-- 显示现有附件列表 -->
{% for attachment in major_assignment.get_all_attachments() %}
<div class="attachment-item">
  <a href="{{ url_for('major_assignment.download_major_assignment_attachment', attachment_id=attachment.id) }}">
    {{ attachment.original_filename }}
  </a>
  <input type="checkbox" name="delete_attachments" value="{{ attachment.id }}"> 删除
</div>
{% endfor %}

<!-- 显示现有链接列表 -->
{% for link in major_assignment.get_all_links() %}
<div class="link-item">
  <a href="{{ link.url }}" target="_blank">{{ link.title }}</a>
  <input type="checkbox" name="delete_links" value="{{ link.id }}"> 删除
</div>
{% endfor %}

<!-- 添加新附件和链接的表单与创建页面相同 -->
```

### 查看大作业详情页面：
```html
<!-- 附件列表 -->
<h4>附件资料：</h4>
{% for attachment in major_assignment.get_all_attachments() %}
<div class="attachment">
  <a href="{{ url_for('major_assignment.download_major_assignment_attachment', attachment_id=attachment.id) }}">
    <i class="icon-file"></i> {{ attachment.original_filename }}
    <span class="file-size">({{ attachment.file_size|filesizeformat }})</span>
  </a>
</div>
{% endfor %}

<!-- 链接列表 -->
<h4>参考链接：</h4>
{% for link in major_assignment.get_all_links() %}
<div class="link">
  <a href="{{ link.url }}" target="_blank">
    <i class="icon-link"></i> {{ link.title }}
  </a>
  {% if link.description %}
  <p class="link-desc">{{ link.description }}</p>
  {% endif %}
</div>
{% endfor %}
```

## 测试清单
- [x] Docker构建成功
- [x] 数据库迁移执行成功
- [x] 服务启动成功
- [x] 代码无语法错误
- [ ] 前端页面更新（需要根据实际模板调整）
- [ ] 功能测试：
  - [ ] 创建大作业时上传多个附件
  - [ ] 创建大作业时添加多个链接
  - [ ] 编辑大作业时添加新附件/链接
  - [ ] 编辑大作业时删除已有附件/链接
  - [ ] 下载附件功能测试
  - [ ] 查看附件和链接列表

## 升级步骤
1. 停止当前服务：`docker-compose down`
2. 重新构建镜像：`docker-compose build`
3. 启动服务：`docker-compose up -d`
4. 查看日志确认迁移成功：`docker logs tg-edu-system`

## 注意事项
1. 旧的大作业数据会自动通过辅助方法展示，无需手动迁移
2. 附件文件存储在`/app/storage/appendix`目录
3. 删除附件时会同时删除物理文件
4. 支持通过Docker挂载的volume持久化存储

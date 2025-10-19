# 大作业多教师管理功能实现总结

## 功能概述
实现了大作业可以由超级管理员直接管理，也可以指定一个或多个教师进行管理的功能。

## 主要变更

### 1. 数据库模型变更 (`app/models/team.py`)

- **新增关联表** `major_assignment_teachers`：支持大作业与教师的多对多关系
  - `major_assignment_id`: 大作业ID
  - `teacher_id`: 教师ID  
  - `created_at`: 创建时间

- **MajorAssignment模型修改**：
  - `teacher_id` → `creator_id`: 字段重命名，表示创建者
  - 新增 `creator` 关系：指向创建者
  - 新增 `teachers` 关系：多对多关系，表示管理教师列表
  - 新增 `can_manage(user)` 方法：检查用户是否有权限管理此大作业

### 2. 路由变更 (`app/routes/major_assignment.py`)

#### major_assignment_dashboard
- 查询逻辑更新：教师可以看到自己创建的、被指定管理的以及所教班级的大作业

#### create_major_assignment  
- 支持选择多个管理教师（超级管理员可选所有教师）
- 如果未指定教师，默认将创建者加入管理列表

#### edit_major_assignment
- 支持编辑管理教师列表（仅超级管理员和创建者可修改）
- 使用 `can_manage()` 方法检查权限

#### view_major_assignment_teams
- 使用 `can_manage()` 方法检查权限

#### confirm_team / reject_team
- 使用 `can_manage()` 方法检查权限

#### approve_leave_request_by_teacher / reject_leave_request_by_teacher
- 使用 `can_manage()` 方法检查权限

#### escalate_leave_request
- 通知所有管理教师（而不是单个教师）

### 3. 模板变更

#### `create_major_assignment.html`
- 新增管理教师多选区域（仅超级管理员可见）
- 使用复选框形式选择多个教师

#### `edit_major_assignment.html`
- 新增管理教师编辑区域（仅超级管理员和创建者可见）
- 显示当前已选择的管理教师
- 班级字段设置为只读（不可修改）
- 修复截止时间显示为北京时间

### 4. 数据库迁移

#### `migrate_db.py` (新增)
专门的数据库迁移脚本，执行以下操作：
1. 创建 `major_assignment_teachers` 关联表
2. 添加 `creator_id` 字段到 `major_assignment` 表
3. 将旧的 `teacher_id` 数据迁移到 `creator_id`
4. 将旧的教师关系迁移到关联表

#### `start.sh` 修改
- 在启动时先运行 `migrate_db.py` 进行数据库迁移
- 简化了初始化脚本，避免bash解析Python代码的问题

#### `Dockerfile` 修改
- 添加 `migrate_db.py` 到镜像

## 权限设计

### 超级管理员
- 可以管理所有大作业
- 可以选择任意教师作为管理者
- 可以修改任何大作业的管理教师列表

### 创建者
- 可以管理自己创建的大作业
- 可以修改自己创建的大作业的管理教师列表

### 管理教师
- 可以管理被指定管理的大作业
- 可以查看、确认/拒绝团队
- 可以处理退组申请
- 不能修改管理教师列表（除非是创建者）

### 普通教师
- 可以看到自己所教班级的大作业
- 创建大作业时只能选择自己作为管理者

## 测试要点

1. **创建大作业**
   - 超级管理员可以选择多个教师
   - 普通教师只能选择自己
   - 未选择教师时，创建者自动成为管理者

2. **编辑大作业**
   - 超级管理员和创建者可以修改管理教师
   - 普通管理教师不能修改管理教师列表

3. **权限检查**
   - 所有管理教师都能查看团队列表
   - 所有管理教师都能确认/拒绝团队
   - 所有管理教师都能处理退组申请

4. **数据迁移**
   - 旧数据的teacher_id正确迁移到creator_id
   - 旧数据的教师关系正确迁移到关联表

## 文件清单

### 修改的文件
- `app/models/team.py`
- `app/routes/major_assignment.py`
- `app/templates/create_major_assignment.html`
- `app/templates/edit_major_assignment.html`
- `start.sh`
- `Dockerfile`

### 新增的文件
- `migrate_db.py`

## 部署说明

1. 停止现有容器：`docker-compose down`
2. 重新构建镜像：`docker-compose up --build -d`
3. 检查迁移日志：`docker logs tg-edu-system`
4. 确认看到以下消息：
   - "数据库表创建完成"
   - "已将teacher_id数据迁移到creator_id"
   - "已将教师关系迁移到major_assignment_teachers表"
   - "数据库迁移完成！"

## 注意事项

1. 数据库迁移是自动执行的，不需要手动干预
2. 旧的大作业数据会自动迁移，原教师成为创建者和管理者
3. 迁移是幂等的，多次执行不会重复插入数据
4. 建议在生产环境部署前先备份数据库

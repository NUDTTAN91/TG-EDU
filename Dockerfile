# 使用Ubuntu 20.04作为基础镜像
FROM ubuntu:20.04

# 作者信息
LABEL Author="tan91"
LABEL GitHub="https://github.com/NUDTTAN91"
LABEL Blog="https://blog.csdn.net/ZXW_NUDT"

# 设置环境变量，避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 设置时区
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 创建应用目录
WORKDIR /app

# 复制requirements文件
COPY requirements.txt .

# 配置pip使用清华源并安装Python依赖
RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip3 config set global.trusted-host pypi.tuna.tsinghua.edu.cn && \
    pip3 install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .
COPY wsgi.py .
COPY config.py .
COPY init_db.py .
COPY migrate_db.py .
COPY migrate_stage_system.py .
COPY migrate_remove_teacher_id.py .
COPY migrate_team_division_free_roles.py .
COPY migrate_task_stage.py .
COPY migrate_task_stage_nullable.py .
COPY migrate_major_assignment_attachments.py .
COPY migrate_team_confirmation_reason.py .
COPY migrate_remove_due_date.py .
COPY update_stage_status.py .
COPY start.sh .
COPY app/ ./app/
RUN find /app -name "*.pyc" -delete && \
    find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 创建必要的目录
RUN mkdir -p storage/uploads storage/data storage/appendix

# 设置权限
RUN chmod 755 /app && \
    chmod 777 /app/storage/uploads && \
    chmod 777 /app/storage/data && \
    chmod 777 /app/storage/appendix && \
    chmod +x /app/start.sh

# 暴露端口
EXPOSE 5000

# 设置启动命令
CMD ["/app/start.sh"]
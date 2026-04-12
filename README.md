# 局域网文件共享系统

一个运行在本地局域网内的文件共享管理系统，支持文件上传下载、权限控制、审计日志等功能。

## 技术栈

| 层级 | 技术方案 |
|------|----------|
| 前端 | Vue 3 + Vite + Element Plus |
| 后端 | FastAPI (Python) |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |
| 认证 | JWT |

## 功能特性

- 用户登录/注册
- 文件夹分级管理
- 文件上传/下载
- 文件在线预览 (图片、PDF、文本)
- 权限控制 (RBAC)
- 操作日志审计
- 支持多人同时访问
- 数据完全保存在本地

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 或 yarn

### Windows 一键启动

双击运行 `start.bat` 即可自动安装依赖并启动服务。

### 手动启动

#### 1. 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 复制配置文件
copy .env.example .env

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 访问地址

- 前端界面: http://localhost:3088
- 后端 API: http://localhost:8088
- API 文档: http://localhost:8088/api/docs

### 默认账号

- 用户名: `admin`
- 密码: `admin123`

## 项目结构

```
共享文件/
├── backend/                # 后端代码
│   ├── app/
│   │   ├── api/           # API 路由
│   │   ├── core/          # 核心配置
│   │   ├── db/            # 数据库
│   │   ├── models/        # 数据模型
│   │   ├── schemas/       # Pydantic 模型
│   │   └── main.py        # 应用入口
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── layouts/       # 布局组件
│   │   ├── views/         # 页面组件
│   │   ├── stores/        # Pinia 状态
│   │   ├── router/        # 路由配置
│   │   ├── utils/         # 工具函数
│   │   └── styles/        # 样式文件
│   ├── package.json
│   └── vite.config.js
│
└── start.bat              # Windows 启动脚本
```

## 生产部署

### 后端部署

```bash
# 使用 gunicorn + uvicorn
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 前端构建

```bash
cd frontend
npm run build
```

构建产物在 `frontend/dist` 目录，可使用 Nginx 托管。

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.local;

    # 前端静态文件
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 安全建议

1. 修改 `.env` 中的 `SECRET_KEY`
2. 修改默认管理员密码
3. 根据需要调整 `ALLOWED_EXTENSIONS` 文件白名单
4. 生产环境使用 PostgreSQL 数据库
5. 启用 HTTPS (通过 Nginx)

## License

MIT

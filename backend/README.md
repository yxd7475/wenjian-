# 局域网文件共享系统 - 后端

## 技术栈
- FastAPI (Web框架)
- SQLAlchemy (ORM)
- SQLite/PostgreSQL (数据库)
- JWT (认证)

## 启动方式

```bash
# 安装依赖
pip install -r requirements.txt

# 复制配置文件
cp .env.example .env

# 初始化数据库
python -m app.db.init_db

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8088
```

## 目录结构
```
backend/
├── app/
│   ├── api/          # API路由
│   ├── core/         # 核心配置
│   ├── db/           # 数据库相关
│   ├── models/       # 数据模型
│   ├── schemas/      # Pydantic模型
│   ├── services/     # 业务逻辑
│   └── utils/        # 工具函数
├── data/             # 数据存储
├── logs/             # 日志文件
└── tests/            # 测试文件
```

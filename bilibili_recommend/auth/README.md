# Auth Backend

FastAPI 登录后端。

## 安装依赖

```powershell
cd C:\course\data\bilibili_recommend\auth
pip install -r requirements.txt
```

## 运行

```powershell
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

## 接口

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/user/profile
PUT  /api/user/profile
```

启动时自动创建 `users` 和 `login_attempts` 表。


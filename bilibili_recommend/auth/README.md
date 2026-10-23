# Auth Backend

FastAPI 登录后端。

## 安装依赖

```powershell
cd C:\course\data\bilibili_recommend\auth
pip install -r requirements.txt
```

## 配置

复制 `.env.example` 为 `.env`，并填写真实密码和密钥：

```powershell
cd C:\course\data\bilibili_recommend\database
Copy-Item .env.example .env
```

然后编辑 `.env`，至少修改：

```text
MYSQL_PASSWORD=你的数据库密码
JWT_SECRET_KEY=随机密钥
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


# Bilibili Crawler Web

基于 Vue 3、Vite 和 Vue Router 的 Web 前端，用于展示 Bilibili 数据采集
工具的界面与交互流程。

## 环境要求

- Node.js 22.18+ 或 24.12+
- npm

## 安装与启动

```sh
npm ci
npm run dev
```

## 生产构建

```sh
npm run build
```

当前登录状态由浏览器本地存储模拟，仅用于前端流程演示，不是实际安全边界。
接入后端时，需要在服务端完成用户认证和数据归属校验。

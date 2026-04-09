# iDeer Client Prototype

这是 `iDeer` 的桌面客户端开发目录，当前包含：

- 桌面工作台式前端
- `Tauri 2` 壳工程
- 与现有 Python `FastAPI` 后端的联动

## 本地开发

1. 启动现有 Python 后端：

```bash
python web_server.py
```

2. 安装依赖并启动前端：

```bash
cd client
npm install
npm run dev
```

Vite 已将 `/api`、`/ws`、`/health` 代理到 `http://127.0.0.1:8090`。

## 运行桌面客户端

先确保 Python 后端可用，然后在本目录执行：

```bash
npm install
npm run desktop:dev
```

当前桌面原型也支持在 Tauri 窗口里尝试拉起本地 `python web_server.py`。

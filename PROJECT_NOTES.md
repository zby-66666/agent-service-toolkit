# 企业知识库与工单智能 Agent：项目学习记录

## 当前项目进度

```text
Phase 1：✅ 已完成（2026-08-18）
Phase 2：未开始
Phase 3～14：未开始
```

当前阶段边界：只运行和验证原项目，尚未修改核心业务代码。

## 项目基线

- 上游项目：`JoshuaC215/agent-service-toolkit`
- 个人 Fork：`zby-66666/agent-service-toolkit`
- Phase 1 基线提交：`d4147ac`
- 本地目录：`D:\ai-learning\projects\agent-service-toolkit`

## 当前运行环境

- Windows + PowerShell
- Python 3.12.2
- uv 0.12.5
- Ollama 0.32.9
- 聊天模型：`qwen3:4b`
- 状态存储：SQLite（`checkpoints.db`，已被 Git 忽略）
- FastAPI：http://localhost:8080
- Streamlit：http://localhost:8501

## 已掌握与已验证内容

- `uv sync --frozen --python 3.12` 可以根据 `uv.lock` 创建项目虚拟环境。
- `origin` 指向个人 Fork，`upstream` 指向原作者仓库。
- `sync` 让 `.venv` 中安装的包与项目依赖一致；`--frozen` 要求严格使用现有 `uv.lock`。
- 开发模式下需等待 `Application startup complete`，不能只看到重载监控进程启动就访问接口。
- FastAPI 和 LangGraph 可以正常导入。
- `GET /health` 返回 `status=ok`。
- `GET /info` 能返回默认模型和 Agent 列表。
- Python `httpx` 能通过 `/chatbot/invoke` 调用 `qwen3:4b`。
- Streamlit 能通过 FastAPI 获得正常中文回答。

## 当前调用链

```text
浏览器
↓
Streamlit（8501）
↓
AgentClient / HTTP
↓
FastAPI（8080）
↓
service.py
↓
根据 agent_id 取得 LangGraph Agent
↓
Ollama qwen3:4b
↓
FastAPI Response
↓
Streamlit 展示答案
```

更细的源码函数调用链留到 Phase 2 阅读和验收。

## Debug 记录与已解决问题

### 1. FastAPI 启动后立即访问失败

- 现象：终端只出现 `Started reloader process`，访问 `/health` 被拒绝。
- 原因：开发模式先启动重载监控进程，服务子进程和应用生命周期尚未初始化完成。
- 判断依据：8080 当时没有监听进程；稍后应用完成启动后 `/health` 正常。
- 处理：等待 `Application startup complete` 后再进行健康检查。

### 2. PowerShell 发送中文后模型认为输入乱码

- 现象：英文请求正常，`Invoke-RestMethod` 发送中文时回答异常。
- 对照实验：直接调用 Ollama 中文正常；Python `httpx` 调用 FastAPI 中文也正常。
- 结论：问题位于当前 PowerShell HTTP 客户端的中文编码层，不在 FastAPI、Agent 或模型层。
- 处理：中文接口测试优先使用 Python `httpx`、Swagger、Streamlit 或 PowerShell 7，不为客户端特例修改服务端业务代码。

## Phase 1 四关验收

- 看得懂：能识别项目启动入口、环境配置以及前后端端口。
- 讲得清：能说明 `origin` / `upstream`、`uv sync --frozen` 和 Uvicorn 开发模式启动过程。
- 改得动：能配置 `.env`，选择 Ollama 模型和 SQLite。
- 会排错：能通过“保持服务端不变、替换客户端”的对照实验定位中文乱码层级。

## 我仍然需要理解的内容

- `run_service.py` 如何加载 `.env` 并启动 `service:app`。
- `/invoke` 和 `/stream` 的请求模型及返回模型。
- `agents.py` 如何按 `agent_id` 取得 Agent。
- `chatbot` 与 `research-assistant` 的 LangGraph 结构差异。
- 普通响应与 SSE 流式响应的代码位置。

以上内容属于 Phase 2，本阶段不提前展开。

## 面试问题

1. `origin` 和 `upstream` 分别指向哪里，为什么需要两个远程仓库？
2. `uv sync --frozen` 中 `sync` 和 `--frozen` 分别有什么作用？
3. 为什么看到 `Uvicorn running` 后，第一次访问 `/health` 仍可能失败？
4. 这次如何通过对照实验证明中文乱码不在 FastAPI 或 Qwen3？

Phase 1 已逐题回答通过。

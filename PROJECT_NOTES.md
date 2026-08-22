# 企业知识库与工单智能 Agent：项目学习记录

## 当前项目进度

```text
Phase 1：✅ 已完成（2026-08-18）
Phase 2：✅ 已完成（2026-08-23）
Phase 3～14：未开始
```

当前阶段边界：已经完成原项目运行验证和核心调用链阅读，尚未修改核心业务代码，也尚未开始研究或改造 RAG。

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

## Phase 1：运行与环境验证

### 已掌握与已验证内容

- `uv sync --frozen --python 3.12` 可以根据 `uv.lock` 创建项目虚拟环境。
- `origin` 指向个人 Fork，`upstream` 指向原作者仓库。
- `sync` 让 `.venv` 中安装的包与项目依赖一致；`--frozen` 要求严格使用现有 `uv.lock`。
- 开发模式下需等待 `Application startup complete`，不能只看到重载监控进程启动就访问接口。
- FastAPI 和 LangGraph 可以正常导入。
- `GET /health` 返回 `status=ok`。
- `GET /info` 能返回默认模型和 Agent 列表。
- Python `httpx` 能通过 `/chatbot/invoke` 调用 `qwen3:4b`。
- Streamlit 能通过 FastAPI 获得正常中文回答。

### Phase 1 四关验收

- 看得懂：能识别项目启动入口、环境配置以及前后端端口。
- 讲得清：能说明 `origin` / `upstream`、`uv sync --frozen` 和 Uvicorn 开发模式启动过程。
- 改得动：能配置 `.env`，选择 Ollama 模型和 SQLite。
- 会排错：能通过“保持服务端不变、替换客户端”的对照实验定位中文乱码层级。

## Phase 2：原项目核心调用链

### 1. 启动与 FastAPI 应用

```text
uv run python src/run_service.py
↓
uvicorn.run("service:app")
↓
src/service/__init__.py 对外导出 app
↓
src/service/service.py 创建 FastAPI 应用
```

- `/health` 直接注册在 `app` 上。
- `/info`、`/invoke`、`/stream` 等接口注册在 `router` 上。
- `app.include_router(router)` 将路由真正挂载到 FastAPI 应用。

### 2. 请求解析与 Service 编排

- `service.py` 负责接收请求、调用 Agent、组织响应，是 HTTP 编排层。
- FastAPI 根据路径取得 `agent_id`。
- Pydantic 将 JSON 请求体校验并转换成 `UserInput` 或 `StreamInput`。
- `_handle_input()` 将用户文本包装成 `HumanMessage`，放进 `input["messages"]`。
- `_handle_input()` 同时创建包含 `thread_id`、`user_id`、模型配置等信息的 `RunnableConfig`，并生成 `run_id`。

### 3. Agent 注册与选择

- `src/agents/agents.py` 保存 Agent 注册表。
- `get_agent(agent_id)` 根据 `agent_id` 取得真正可执行的 LangGraph 对象。
- `get_agent()` 负责选择 Agent；`agent.ainvoke()` / `agent.astream()` 负责执行 Agent。

### 4. 模型选择与实际调用

- `src/core/llm.py` 中的 `get_model()` 根据逻辑模型名选择供应商分支并创建模型对象。
- `/info` 中的 `ollama` 是逻辑模型/供应商分支。
- `.env` 中的 `OLLAMA_MODEL=qwen3:4b` 是 Ollama 实际加载的模型标签。
- `get_model("ollama")` 最终创建 `ChatOllama(model="qwen3:4b")`。
- `get_model()` 负责选择模型；`model.ainvoke()` 负责真正调用模型。

### 5. chatbot 调用链

`chatbot` 使用 LangGraph Functional API，流程较简单：

```text
HumanMessage
↓
chatbot LangGraph
↓
get_model()
↓
model.ainvoke(messages)
↓
AIMessage
```

### 6. research-assistant StateGraph

`research-assistant` 使用显式 `StateGraph`，主要节点为：

- `guard_input`：检查输入安全性。
- `block_unsafe_content`：生成拦截消息并结束不安全请求。
- `model`：调用模型，直接回答或生成工具请求。
- `tools`：通过 `ToolNode(tools)` 真正执行工具。

安全且需要工具时的节点顺序：

```text
guard_input
↓
model
↓
tools
↓
model
↓
END
```

不安全输入的节点顺序：

```text
guard_input
↓
block_unsafe_content
↓
END
```

当前没有配置 `GROQ_API_KEY`，所以 `Safeguard` 不调用安全模型，而是返回 `SAFE`；`guard_input` 节点仍然存在并会执行。

### 7. State 与消息合并

- `AgentState` 继承 `MessagesState`，获得标准 `messages` 字段和 `add_messages` reducer。
- 节点返回 `{"messages": [response]}` 表示增量更新，不会直接覆盖已有消息历史。
- `AgentState` 额外保存 `safety` 和 `remaining_steps`。
- `remaining_steps` 在剩余步骤不足时阻止新的工具调用，避免 `model → tools → model` 无限循环。

工具调用中的消息顺序：

```text
HumanMessage
↓
AIMessage(tool_calls)
↓
ToolMessage
↓
最终 AIMessage
```

### 8. Tool Calling

- `model.bind_tools(tools)` 将工具名称、说明和参数结构提供给模型，不执行工具。
- `AIMessage.tool_calls` 是模型生成的结构化工具调用请求，也不执行工具。
- `ToolNode(tools)` 根据工具名和参数真正执行工具，并产生 `ToolMessage`。
- `pending_tool_calls()` 检查最后一条 `AIMessage.tool_calls`：有值则进入 `tools`，无值则进入 `END`。
- Calculator 工具通过 `tool(calculator_func)` 将普通 Python 函数转换成 LangChain 工具。
- 工具用途来自 docstring，参数结构来自函数签名，模型看到的名称被设置为 `Calculator`。

已通过真实请求验证：

```text
AIMessage(tool_calls=[Calculator("300 * 200")])
↓
ToolMessage("60000")
↓
AIMessage("The result of 300 * 200 is 60000.")
```

### 9. ID 的职责

- `run_id` 标识整次 Agent 执行，由 Service 层生成，并附加到返回消息。
- `tool_call_id` 标识某一次具体工具调用。
- `AIMessage.tool_calls[i].id` 必须与对应 `ToolMessage.tool_call_id` 相同，以便模型匹配工具请求和结果。

### 10. 非流式返回

```text
POST /{agent_id}/invoke
↓
UserInput
↓
get_agent()
↓
_handle_input()
↓
agent.ainvoke()
↓
取得最终 AIMessage
↓
langchain_to_chat_message()
↓
手工附加 run_id
↓
FastAPI 返回 ChatMessage JSON
```

### 11. SSE 流式返回

```text
POST /{agent_id}/stream
↓
StreamInput
↓
stream() 创建 StreamingResponse
↓
StreamingResponse 迭代 message_generator()
↓
get_agent() + _handle_input()
↓
agent.astream() 执行 Graph 并产生事件
↓
message_generator() 分类和包装事件
├─ AIMessageChunk → type=token
└─ AIMessage / ToolMessage → ChatMessage → type=message
↓
StreamingResponse 通过 HTTP 逐条发送 SSE
↓
data: [DONE]
```

三层职责：

- `agent.astream()`：产生 LangGraph 流式事件。
- `message_generator()`：筛选事件并包装成 `token` / `message` SSE。
- `StreamingResponse`：通过 HTTP 把 SSE 逐条发送给客户端。

## 当前完整架构

```text
客户端（Streamlit / Python httpx）
↓
FastAPI：解析路径和请求体
↓
Service：选择 Agent、包装输入和配置、组织响应
↓
Agent 注册表：get_agent(agent_id)
↓
LangGraph：State、节点、条件边和工具循环
↓
LLM：get_model() → ChatOllama(qwen3:4b)
↕
Tools：ToolNode 执行 Calculator / WebSearch 等工具
↓
LangChain 消息：AIMessage / ToolMessage / AIMessageChunk
↓
ChatMessage JSON 或 SSE
↓
客户端展示
```

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

### 3. 流式接口返回 HTTP 200 后又返回 error

- 现象：客户端先收到 HTTP 200，随后收到 `type=error` 和 `[DONE]`。
- 原因：Ollama 未启动。HTTP 200 只表示 SSE 连接已建立；连接建立后，Agent 或模型仍可能执行失败。
- 处理：启动 Ollama 后重新测试，成功收到 token、完整消息和 `[DONE]`。
- 结论：响应头发送后不能再把状态码改成 500，因此流式执行错误通过 SSE `type=error` 表达。

### 4. 在 CMD 中粘贴 PowerShell Here-String 失败

- 现象：CMD 将 `@'`、`import`、`with` 等每一行当成独立命令。
- 原因：`@' ... '@` 是 PowerShell 多行字符串语法，CMD 不支持。
- 处理：先进入 PowerShell，确认提示符以 `PS` 开头，再执行测试脚本。

## Phase 2 四关验收

- 看得懂：能定位 API 入口、Agent 注册、Graph 定义、State、Tool、模型初始化和 Streaming 返回位置。
- 讲得清：能分段说明“请求进入 Graph、Graph 内部执行、流式结果返回客户端”的完整调用链。
- 改得动：能判断不同需求应修改 Service、Agent Graph、模型选择还是 Tool 定义；本阶段按计划未修改核心业务代码。
- 会排错：能区分 FastAPI 健康状态、SSE 连接状态和 Ollama 模型执行状态，并能识别 CMD / PowerShell 语法环境差异。

## 下一阶段需要理解的内容

Phase 3 只研究原项目 RAG，暂时不重写：

- Document 从哪里进入。
- Chunk 在哪里完成。
- Embedding 在哪里调用。
- Vector Store 是什么。
- Retriever 在哪里。
- Agent 如何调用 Retriever。

## 面试问题

### Phase 1

1. `origin` 和 `upstream` 分别指向哪里，为什么需要两个远程仓库？
2. `uv sync --frozen` 中 `sync` 和 `--frozen` 分别有什么作用？
3. 为什么看到 `Uvicorn running` 后，第一次访问 `/health` 仍可能失败？
4. 如何通过对照实验证明中文乱码不在 FastAPI 或 Qwen3？

### Phase 2

1. `service.py`、`agents.py`、Agent Graph、`llm.py` 和 `tools.py` 分别承担什么职责？
2. `model.bind_tools()`、`AIMessage.tool_calls` 和 `ToolNode` 的区别是什么？
3. `MessagesState` 为什么能保留用户消息、工具请求、工具结果和最终回答？
4. `research-assistant` 如何通过条件边完成 `model → tools → model` 循环并最终进入 `END`？
5. `agent.astream()`、`message_generator()` 和 `StreamingResponse` 在 SSE 流程中分别负责什么？

Phase 1 和 Phase 2 均已逐项学习并验收通过。

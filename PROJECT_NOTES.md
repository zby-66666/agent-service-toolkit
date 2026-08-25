# 企业知识库与工单智能 Agent：项目学习记录

## 当前项目进度

```text
Phase 1：✅ 已完成（2026-08-18）
Phase 2：✅ 已完成（2026-08-23）
Phase 3：✅ 已完成（2026-08-24）
Phase 4：✅ 已完成（2026-08-25）
Phase 5：✅ 已完成（2026-08-26）
Phase 6～14：未开始
```

当前阶段边界：已经完成原项目运行验证、核心调用链、原版 RAG 阅读、Qdrant / bge-m3 迁移，以及 Embedding 与相似度检索实验。下一阶段只增加 Reranker，不提前开发工单模块。

## 项目基线

- 上游项目：`JoshuaC215/agent-service-toolkit`
- 个人 Fork：`zby-66666/agent-service-toolkit`
- Phase 1 基线提交：`d4147ac`
- Phase 4 Qdrant 依赖提交：`2f43bb1`
- Phase 4 建库脚本提交：`c30f1b3`
- Phase 4 在线检索提交：`6062a2d`
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

## Phase 3：原项目 RAG 调用链

### 1. 核心文件与职责

- `scripts/create_chroma_db.py`：离线读取文档、切块、生成向量并建立 Chroma。
- `src/agents/tools.py`：在线加载 Chroma、创建 Retriever 并真正执行检索。
- `src/agents/rag_assistant.py`：定义 RAG Agent Graph，让模型决定是否调用检索工具，并根据检索结果回答。
- 当前版本没有计划中提到的 `src/core/vector_store.py`，应以实际项目结构为准。

### 2. 离线建库

```text
./data 中的 PDF / DOCX
↓
根据扩展名选择 PyPDFLoader / Docx2txtLoader
↓
loader.load()
↓
list[Document]
↓
RecursiveCharacterTextSplitter
↓
list[Document]（Chunk）
↓
Chroma.add_documents()
↓
OpenAIEmbeddings 在内部生成文档向量
↓
保存向量、page_content 和 metadata 到 ./chroma_db
```

- `Document` 主要包含正文 `page_content` 和来源、页码等 `metadata`。
- 当前默认 `chunk_size=2000`、`chunk_overlap=500`。
- overlap 用于减少语义在 Chunk 边界处被切断的问题，但过大会增加重复内容、Embedding 成本和存储。
- 当前源文档 `data/AcmeTech_Employee_Handbook.pdf` 已存在，但还没有生成 `chroma_db`。

### 3. Embedding、Vector Store 与 Chat Model

- Chat Model：`qwen3:4b`，负责理解问题、决定是否调用工具、读取检索结果并生成答案。
- Embedding Model：原项目使用 `OpenAIEmbeddings`，负责将 Chunk 和查询转换成向量，不生成答案。
- Vector Store：Chroma，负责保存文档向量、正文和 metadata，并执行相似度检索。
- 文档和查询必须使用兼容的同一个 Embedding 模型，才能处于可比较的向量空间。
- 将员工手册写入 Chroma 不会训练或修改 Qwen3；RAG 只是把检索内容临时放入本次模型上下文。

### 4. 在线检索

```text
第一次 model 生成 AIMessage(tool_calls=[Database_Search])
↓
pending_tool_calls() 路由到 tools
↓
ToolNode 调用 database_search_func(query)
↓
load_chroma_db()
↓
创建 OpenAIEmbeddings、Chroma 和 Retriever（k=5）
↓
retriever.invoke(query)
↓
list[Document]
↓
format_contexts(documents)
↓
context_str
↓
ToolNode 包装成 ToolMessage
↓
第二次 model 根据检索内容生成最终 AIMessage
↓
END
```

- `k=5` 表示最多返回相似度排名最高的 5 个 Chunk，不是返回 5 个答案。
- `database_search_func()` 返回普通字符串；`ToolNode` 负责包装成 `ToolMessage` 并关联 `tool_call_id`。
- 当前流程由模型决定是否调用 `Database_Search`，因此属于 Agentic RAG，而不是程序强制每次检索。

### 5. 当前运行条件

只读检查结果：

```text
data_exists=True
chroma_db_exists=False
openai_key_configured=False
```

因此原版 RAG 当前不能直接运行：已有员工手册 PDF，但没有 `OPENAI_API_KEY`，也没有完成向量化后的 `chroma_db`。Phase 3 的目标是理解原项目，所以没有提前修改为本地 `bge-m3`。

### 6. 原实现的主要限制

- 离线和在线都写死为 `OpenAIEmbeddings`，无法直接使用本地 `bge-m3`。
- `format_contexts()` 只拼接 `page_content`，丢弃来源文件和页码等 metadata，不利于可靠引用。
- Retriever 只设置 `top k`，没有最低相似度阈值、分数判断或 Reranker，最相似的结果不一定真正相关。
- 建库参数 `delete_chroma_db=True`，重新建库默认先删除旧数据库，失败时缺少可用旧版本和回滚切换机制。
- 离线代码逐个 Chunk 调用 `add_documents()`，批次较小，效率有限。
- 在线每次工具调用都会重新创建 Embedding、Chroma 和 Retriever 对象，存在重复初始化开销。

## Phase 4：Qdrant Vector Store 改造

### 1. 本阶段修改范围

- 新增 `langchain-qdrant~=1.1.0`，由 uv 同步更新 `pyproject.toml` 和 `uv.lock`。
- 保留 `scripts/create_chroma_db.py`，用于对比原实现和必要时回退。
- 新增 `scripts/create_qdrant_db.py`，负责使用本地 `bge-m3` 建立持久化 Qdrant Collection。
- 修改 `src/agents/tools.py`，将在线检索从 `OpenAIEmbeddings + Chroma` 切换为 `OllamaEmbeddings + QdrantVectorStore`。
- `src/agents/rag_assistant.py`、Tool 名称、Graph、`k=5` 和 `format_contexts()` 均保持不变。

### 2. 物理存储与逻辑 Collection

- `./qdrant_data` 是本地 Qdrant 数据在磁盘上的物理存储目录，已加入 `.gitignore`，不会推送到 Git。
- `employee_handbook` 是 Qdrant 内部的逻辑 Collection，可以类比关系数据库中的表。
- Collection 中的 Point 保存向量和 payload；LangChain 将 Chunk 的 `page_content` 与 `metadata` 写入 payload。
- 不同业务数据可以使用同一个 Qdrant 实例中的不同 Collection，不要求每个 Collection 使用单独的磁盘目录。

### 3. 离线建库调用链

```text
./data 中的 PDF / DOCX
↓
PyPDFLoader / Docx2txtLoader
↓
list[Document]
↓
RecursiveCharacterTextSplitter（chunk_size=2000，chunk_overlap=500）
↓
list[Document]（Chunk）
↓
OllamaEmbeddings(model="bge-m3")
↓
探测向量维度：1024
↓
创建 ./qdrant_data
↓
创建 employee_handbook Collection（Cosine）
↓
QdrantVectorStore.add_documents(chunks)
↓
保存向量、page_content 和 metadata
```

建库脚本发现 `employee_handbook` 已存在时会拒绝覆盖，避免重复运行产生重复 Chunk。只有本次运行新建 Collection 后又写入失败，才会回滚删除本次创建的不完整 Collection，不会删除已有知识库。

### 4. 在线检索调用链

```text
第一次 model 生成 AIMessage(tool_calls=[Database_Search])
↓
ToolNode 调用 database_search_func(query)
↓
load_qdrant_db()
↓
OllamaEmbeddings(model="bge-m3")
↓
QdrantClient(path="./qdrant_data")
↓
选择 employee_handbook Collection
↓
QdrantVectorStore.as_retriever(k=5)
↓
retriever.invoke(query)
↓
list[Document]
↓
format_contexts(documents)
↓
context_str
↓
ToolNode 包装成 ToolMessage
↓
第二次 model 生成最终 AIMessage
↓
client.close() 释放本地数据库资源和文件锁
```

- `retriever` 是配置好的检索器，不是检索结果；真正的查询发生在 `retriever.invoke(query)`。
- 查询执行期间 Qdrant 客户端必须保持打开，因此 `load_qdrant_db()` 同时返回 `client` 和 `retriever`。
- `database_search_func()` 使用 `finally`，确保检索成功或失败后都会关闭客户端。
- 离线文档和在线查询必须使用相同的 Embedding 模型，才能位于同一个向量空间。即使两个模型输出维度相同，也不代表它们的向量可以直接比较。

### 5. 验证结果

- `bge-m3` 本地向量输出类型为 `list`，维度为 1024。
- 建库读取 3 个 PDF Document，最终保存 3 个 Chunk。
- 持久化重开 Qdrant 后，问题能够命中 `Paid Time Off (PTO): 15 days per year`。
- metadata 中保留了源文件和页码。
- 连续两次直接调用 `database_search_func()` 均命中正确内容，证明检索和客户端关闭流程正常。
- `/rag-assistant/stream` 完整返回 `Database_Search` 工具请求、ToolMessage、最终答案和 `[DONE]`。
- 工具请求 `id` 与 ToolMessage 的 `tool_call_id` 一致，最终回答正确说明第二次模型调用成功使用了检索上下文。
- Ruff 检查和格式检查通过；`tests/core/test_llm.py` 共 9 项测试通过。

### 6. 当前保留的限制

- `k=5` 只表示最多返回 5 个 Chunk，不保证每个 Chunk 真正相关；当前 Collection 只有 3 个 Chunk，因此最多返回 3 个。
- 尚未设置最低相似度阈值，也没有 Reranker。
- `format_contexts()` 仍然只拼接 `page_content`，metadata 虽保存在 Qdrant 中，但不会进入模型上下文。
- Qdrant 路径、Collection 名称和 Embedding 模型在离线、在线文件中重复配置，未来可能出现配置不一致。
- `./qdrant_data` 是相对于当前工作目录的路径；从其他目录启动程序可能找错数据库。
- 本地嵌入式 Qdrant 适合学习和单机开发；生产环境的并发和部署方案以后在工程化阶段处理。
- Loader 使用的 `langchain-community` 已出现弃用警告，本阶段不扩大范围迁移 Loader。

## Phase 5：Embedding 与相似度检索

### 1. 文档 Embedding 与 Query Embedding

- `OllamaEmbeddings(model="bge-m3")` 只是创建 Embedding 对象，本身不代表已经生成向量。
- 离线建库时，`QdrantVectorStore.add_documents(chunks)` 在内部调用文档 Embedding，将每个 Chunk 转换成向量并长期保存到 Qdrant。
- `embed_documents()` 接收 `list[str]`，返回 `list[list[float]]`；3 个 Chunk 会得到 3 个向量。
- 在线查询时，`retriever.invoke(query)` 在内部调用 Query Embedding，将本次问题转换成一个向量后交给 Qdrant 检索。
- `embed_query()` 接收一个 `str`，返回一个 `list[float]`；Query Vector 通常只用于本次查询，不作为知识文档长期保存。
- 当前 `bge-m3` 的文档向量和查询向量都是 1024 维。

### 2. 向量空间与维度

- 文档和问题必须由兼容的同一个 Embedding 模型生成，才能位于同一个向量空间并进行有意义的比较。
- 向量维度相同只是数据结构兼容，不代表语义空间相同；两个不同模型即使都输出 1024 维，也不能因此直接混用。
- 1024 维向量是 1024 个浮点数组成的整体表示，单个维度通常没有适合人类直接解释的固定含义。
- `qwen3:4b` 不读取这些浮点向量，也不负责计算相似度；它最终读取的是 ToolMessage 中的检索文本。

### 3. Cosine Similarity 实验

本阶段直接使用 `bge-m3` 生成向量并手工计算 Cosine Similarity：

```text
vector_size: 1024
PTO vs vacation: 0.6394
PTO vs cake: 0.2993
```

- `paid time off` 与 `vacation days` 表达不同但语义接近，因此分数较高。
- `paid time off` 与 `chocolate cake` 语义不相关，因此分数较低。
- 相似度分数应结合当前模型、领域、Chunk 和测试集观察，不能脱离项目规定一个通用及格线。

### 4. 真实 Qdrant 排名实验

使用 `similarity_search_with_score()` 查询真实员工手册的 3 个 Chunk：

```text
rank=1, score=0.5956, page=1
rank=2, score=0.4538, page=2
rank=3, score=0.4409, page=0
```

- 第 1 个 Chunk 包含 `Paid Time Off (PTO): 15 days per year`，因此排名最高。
- 预览只显示 Chunk 开头，不能仅根据前 180 个字符判断整个 Chunk 是否相关；Qdrant 比较的是完整 Chunk。
- 查询与长 Chunk 的分数低于短句实验，是因为长 Chunk 同时包含远程办公、行为规范和安全指南等信息，目标语义被其他内容稀释。
- Top-K 只负责相对排序，不负责判断结果是否达到最低相关性。
- 当前只有 3 个 Chunk 且查询 `k=3`，所以即使第 2、3 名不够相关，也会全部返回；原因是没有最低相似度阈值。

### 5. 当前可用的优化方向

- 调整 Chunk 大小和切分方式，减少一个 Chunk 混入过多主题。
- 根据验证集调整 Top-K，而不是盲目增加返回数量。
- 增加经过数据验证的最低相似度阈值，过滤明显不相关结果。
- Phase 6 再增加 Reranker，对 Qdrant 候选结果进行二次精排。

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
↕
RAG Tool：Database_Search → bge-m3 → Retriever → Qdrant（employee_handbook）
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

### 5. `python -c` 无法导入 `agents`

- 现象：在项目根目录执行 `uv run python -c "from agents.tools ..."` 返回 `ModuleNotFoundError: No module named 'agents'`。
- 原因：项目采用 `src` 目录结构；执行 `python -c` 时，`src` 不会像执行 `src/run_service.py` 那样自动进入模块搜索路径。
- 处理：测试命令先执行 `sys.path.insert(0, "src")`，同时保持当前工作目录为项目根目录，避免相对路径 `./qdrant_data` 指向错误位置。

### 6. QdrantVectorStore 初始化时 Ollama 返回 502

- 现象：创建 `QdrantVectorStore` 时，在 `embed_documents(["dummy_text"])` 阶段收到 Ollama HTTP 502。
- 原因：Ollama 服务没有启动；LangChain-Qdrant 初始化时会先调用 Embedding 模型生成测试向量，校验 Collection 的向量维度。
- 判断：错误发生在测试向量生成阶段，尚未进入 `retriever.invoke(query)`，因此不是 Qdrant 检索结果错误。
- 处理：启动 Ollama 后重新测试，连续两次检索均成功。

## Phase 2 四关验收

- 看得懂：能定位 API 入口、Agent 注册、Graph 定义、State、Tool、模型初始化和 Streaming 返回位置。
- 讲得清：能分段说明“请求进入 Graph、Graph 内部执行、流式结果返回客户端”的完整调用链。
- 改得动：能判断不同需求应修改 Service、Agent Graph、模型选择还是 Tool 定义；本阶段按计划未修改核心业务代码。
- 会排错：能区分 FastAPI 健康状态、SSE 连接状态和 Ollama 模型执行状态，并能识别 CMD / PowerShell 语法环境差异。

## Phase 3 四关验收

- 看得懂：能定位 Document、Chunk、Embedding、Chroma、Retriever 和 Agent 调用检索工具的位置。
- 讲得清：能分别说明离线建库与在线检索两条调用链，以及 Qwen3、Embedding 和 Chroma 的职责边界。
- 改得动：能判断本地 Embedding、来源 metadata、阈值检索和初始化方式分别应修改哪里；本阶段按计划未改 RAG。
- 会排错：能根据源文档、Embedding 配置和 `chroma_db` 三项状态判断原版 RAG 为什么不能运行，并识别原实现的主要风险。

## Phase 4 四关验收

- 看得懂：能区分 `qdrant_data` 物理目录、`employee_handbook` Collection、Qdrant Client、Vector Store 和 Retriever。
- 讲得清：能分别说明“文档 → bge-m3 → Qdrant”和“查询 → bge-m3 → Qdrant Search”的完整调用链。
- 改得动：能够在保留 Agent Graph 的前提下，定位并替换在线 Vector Store 与 Embedding 初始化代码。
- 会排错：能区分 Python 导入路径、Ollama 服务、Embedding 维度、Qdrant Collection 和 Agent Tool Calling 各层问题。

## Phase 5 四关验收

- 看得懂：能定位文档 Embedding、Query Embedding 和 Qdrant 相似度检索的实际执行位置。
- 讲得清：能说明 `embed_documents()` / `embed_query()` 的输入输出、1024 维向量和同一向量空间的含义。
- 改得动：能通过独立实验替换测试文本、调整 Top-K，并观察相似度分数与结果排名。
- 会排错：能根据模型服务、向量维度、Chunk 内容、相似度分数、Top-K 和阈值判断检索问题所在层级。

## 下一阶段需要理解的内容

Phase 6 增加 Reranker，只完成“候选召回 → 二次精排”的最小闭环：

- 先明确 Qdrant Top-K 负责召回、Reranker Top-N 负责精排的职责边界。
- 根据当前 Windows + Ollama 环境选择一个可运行的本地 Reranker。
- 先独立测试 Reranker，再接入 `Database_Search`，不同时修改 Agent Graph。
- 对比接入前后的排序、上下文长度和最终答案。

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

### Phase 3

1. 原项目为什么要把离线建库和在线检索拆成两条流程？
2. Chat Model、Embedding Model、Vector Store 和 Retriever 分别承担什么职责？
3. 从 PDF 进入 `./data` 到 Chunk 写入 Chroma，完整调用链是什么？
4. `rag-assistant` 如何通过 `Database_Search`、ToolNode 和 Retriever 得到知识库内容并生成答案？
5. 原版 RAG 在 Embedding、metadata、相关性过滤和数据库更新方面有哪些限制？

### Phase 4

1. `qwen3:4b` 和 `bge-m3` 在当前 RAG 中分别承担什么职责？
2. `qdrant_data` 与 `employee_handbook` 有什么区别？
3. 为什么文档和查询必须使用相同的 Embedding 模型，而不能只保证向量维度相同？
4. 为什么在线检索需要同时管理 Qdrant Client 和 Retriever 的生命周期？
5. `k=5` 是否代表一定返回 5 个相关答案？当前实现还缺少哪些相关性控制？

### Phase 5

1. 文档 Embedding 与 Query Embedding 分别在什么时候执行，哪一种向量会长期保存到 Qdrant？
2. 为什么两个 Embedding 模型即使都输出 1024 维，也不代表它们能够混用？
3. Cosine Similarity 在当前检索链路中由谁计算，`qwen3:4b` 最终能看到什么？
4. 为什么查询与长 Chunk 的分数可能低于语义接近的两个短句？
5. Top-K 与最低相似度阈值分别解决什么问题？

Phase 1、Phase 2、Phase 3、Phase 4 和 Phase 5 均已逐项学习并验收通过。

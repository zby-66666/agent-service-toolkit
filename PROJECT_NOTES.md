# 企业知识库与工单智能 Agent：项目学习记录

## 当前项目进度

```text
Phase 1：✅ 已完成（2026-08-18）
Phase 2：✅ 已完成（2026-08-23）
Phase 3：✅ 已完成（2026-08-24）
Phase 4：✅ 已完成（2026-08-25）
Phase 5：✅ 已完成（2026-08-26）
Phase 6：✅ 已完成（2026-08-27）
Phase 7：✅ 已完成（2026-08-28）
Phase 8：✅ 已完成（2026-08-30）
Phase 9：✅ 已完成（2026-08-30）
Phase 10：✅ 已完成（2026-08-30）
Phase 11：✅ 已完成（2026-08-31）
Phase 12：✅ 已完成（2026-09-01）
Phase 13～14：未开始
```

当前阶段边界：已经完成原项目运行验证、核心调用链、原版 RAG 阅读、Qdrant / bge-m3 迁移、Embedding 实验、本地 Cross-Encoder Reranker、独立企业工单数据层、Ticket Tools、Ticket Agent Graph、Service / FastAPI 接入、Streamlit 端到端验证，以及基于 SQLite Checkpointer 的多轮对话 Memory 验证。下一阶段再开始 MCP。

## 项目基线

- 上游项目：`JoshuaC215/agent-service-toolkit`
- 个人 Fork：`zby-66666/agent-service-toolkit`
- Phase 1 基线提交：`d4147ac`
- Phase 4 Qdrant 依赖提交：`2f43bb1`
- Phase 4 建库脚本提交：`c30f1b3`
- Phase 4 在线检索提交：`6062a2d`
- Phase 6 Reranker 依赖提交：`ff39e88`
- Phase 6 Reranker 接入提交：`11f4905`
- 本地目录：`D:\ai-learning\projects\agent-service-toolkit`

## 当前运行环境

- Windows + PowerShell
- Python 3.12.2
- uv 0.12.5
- Ollama 0.32.9
- 聊天模型：`qwen3:4b`
- 状态存储：SQLite（`checkpoints.db`，已被 Git 忽略）
- 业务数据：SQLite（`data/business.db`，已被 Git 忽略）
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

## Phase 6：本地 Cross-Encoder Reranker

### 1. 为什么需要两级检索

- Embedding 分别将 Query 和 Document 转换成向量；Qdrant 使用向量相似度快速从大量 Chunk 中召回候选。
- Cross-Encoder 同时读取 `(Query, Document)` 文本对，直接输出相关性分数，排序通常更精确，但每个候选都需要单独计算，成本更高。
- 因此不能用 Reranker 逐个检查整个知识库，而应由 Qdrant 先缩小候选范围，再对少量候选进行精排。

职责边界：

```text
Embedding → 输出向量
Qdrant → 输出候选 Document / Chunk
Reranker → 输出每个候选的相关性分数和新排序
Qwen → 输出最终自然语言答案
```

### 2. 模型与运行方案

- 使用 `fastembed~=0.8.0` 和 `BAAI/bge-reranker-base`。
- FastEmbed 使用 ONNX Runtime，不需要为本阶段引入完整 PyTorch / Transformers 技术栈。
- 模型支持当前需要的中文、英文和最小跨语言场景，使用 CPU 推理，避免 4GB 显存上的 CUDA 兼容与资源风险。
- 模型约 1.13GB，缓存到用户目录 `AppData/Local/fastembed_cache`，不会提交到 Git。
- 没有选择许可证不适合商业项目的候选模型，也没有为了更强模型提前增加过重部署复杂度。

### 3. 独立模型验证

英文测试中，正确 PTO 文档得到明显更高的分数：

```text
PTO: 4.0273
两个无关文档: 约 -10.19
```

使用纯 ASCII Unicode 转义排除 PowerShell 中文编码影响后，跨语言测试结果为：

```text
中文正确 PTO: 6.7419
英文正确 PTO: 2.0063
中文无关保险: -10.1870
中文无关蛋糕: -10.1950
```

- Reranker 返回的是原始相关性分数，不要求位于 `0～1`，当前按“分数越高越相关”进行排序。
- 不应过度解释两个无关候选之间极小的分数差异，重点是正确候选是否稳定排在前面。

### 4. 接入后的调用链

```text
第一次 Qwen 生成 Database_Search 工具请求
↓
Qdrant 使用 bge-m3 召回 Top-K
↓
最多 5 个 Document
↓
关闭 QdrantClient
↓
BGE Cross-Encoder 评估全部候选
↓
按 Reranker 分数降序排列
↓
截取 Top-2 Document
↓
format_contexts()
↓
ToolNode 包装成 ToolMessage
↓
第二次 Qwen 生成最终答案
```

- `RETRIEVAL_K=5` 控制 Qdrant 候选数量，也是 Reranker 最多需要评分的数量。
- `RERANK_TOP_N=2` 控制精排后交给 Qwen 的 Chunk 数量。
- 如果 Qdrant 返回 5 个候选，Reranker 必须先评估全部 5 个，再截取最高的 2 个；不能只评估前 2 个。
- Qdrant 查询结束后 Document 已进入内存，Reranker 不需要数据库连接，因此先关闭 Client，减少本地文件锁占用时间。

### 5. 模型缓存

- 磁盘缓存保存下载的 ONNX 模型文件，解决“服务或电脑重启后不要重新下载”。
- `@lru_cache(maxsize=1)` 保存当前 Python 进程中已初始化的 `TextCrossEncoder`，解决“每个请求不要重新初始化模型”。
- 服务进程重启后 `lru_cache` 会消失，但磁盘缓存仍存在；新进程从磁盘重新初始化，不需要重新下载。
- 连续两次调用验证结果为 `hits=1, misses=1`，说明第一次初始化、第二次复用。

### 6. 验证与测试

- 真实检索连续两次均保留 `15 days per year`。
- 上下文长度从 3898 降到 3096，减少 802 个字符，约 20.6%。
- `/rag-assistant/stream` 完整返回 Database_Search 工具调用、精排后的 ToolMessage、正确最终答案和 `[DONE]`。
- 新增 3 个不加载真实模型的单元测试：排序与 Top-N、空候选不加载模型、文档和分数数量不匹配时报错。
- `monkeypatch` 只在测试期间将 `get_reranker()` 替换为可控制分数的 FakeReranker，测试结束后自动恢复。
- Ruff 检查通过；Reranker 测试 3 项通过；与模型测试组合共 12 项通过。

### 7. 当前限制

- Reranker 只能重排 Qdrant 已召回的候选；如果正确 Chunk 没进入 Top-K，它无法补回。
- 固定 Top-2 仍可能保留一个分数很低的候选，因为尚未增加 Reranker 最低分数阈值。
- Chunk 过长、Query 表达不清或模型领域能力不足仍可能影响排序。
- FastEmbed 使用 CPU，第一条请求需要初始化 ONNX 模型，延迟高于后续请求。
- 当前 `format_contexts()` 仍未把来源 metadata 和 Reranker 分数交给 Qwen。

## Phase 7：企业工单数据层

### 1. 状态数据与业务数据分离

- `checkpoints.db` 保存 LangGraph Checkpoint，是对话和 Graph 运行状态。
- `data/business.db` 保存客户、设备、工单和维修记录，是企业业务数据。
- 两类数据的结构、生命周期和查询方式不同，因此不混入同一个数据库文件。
- `*.db` 已在 `.gitignore` 中忽略；Git 只记录建库、种子和查询脚本，不记录本地数据库文件。

### 2. 最小表关系

```text
customer
  1
  ↓
  N
device
  1
  ↓
  N
ticket
  1
  ↓
  N
repair_record
```

- `device.customer_id → customer.id`
- `ticket.device_id → device.id`
- `repair_record.ticket_id → ticket.id`
- `ticket` 不重复保存 `customer_id`，因为可以通过 `ticket → device → customer` 得到客户，避免两份客户关系互相矛盾。

### 3. 约束与索引

- `PRIMARY KEY` 唯一标识每条记录。
- `NOT NULL` 阻止必要字段为空。
- `UNIQUE` 防止邮箱和设备序列号重复。
- `CHECK` 将工单状态和优先级限制在允许的取值范围。
- `FOREIGN KEY` 保证父子记录关系有效；每次 SQLite 连接都执行 `PRAGMA foreign_keys = ON`。
- 在 `device.customer_id`、`ticket.device_id`、`repair_record.ticket_id` 上创建索引，加快关联查询。
- `ON DELETE RESTRICT` 防止仍有子记录时直接删除父记录。

### 4. 建库与种子数据

```text
scripts/create_business_db.py
↓
拒绝覆盖已存在的 business.db
↓
创建四张表、约束和索引
```

```text
scripts/seed_business_db.py
↓
确认数据库和四张表存在
↓
确认表为空，防止重复写入
↓
BEGIN
↓
customer → device → ticket → repair_record
↓
全部成功 commit()；任一步失败 rollback()
```

种子数据包含 2 个客户、3 台设备、4 张工单和 2 条维修记录，能够验证已解决、处理中、未维修和跨工单累计维修次数等场景。

### 5. 结构化查询

- `get_customer_tickets(customer_id)` 通过 `customer → device → ticket` 查询客户全部工单。
- 工单与维修记录使用 `LEFT JOIN`，因此没有维修记录的工单仍会保留，`COUNT(repair_record.id)` 返回 `0`。
- `get_device_repair_count(serial_number)` 通过 `device → ticket → repair_record` 累计一台设备跨多张工单的维修记录。
- SQL 使用 `?` 参数占位符，不把用户值直接拼接进 SQL。
- 查询完成后在 `finally` 中关闭 SQLite 连接。

### 6. 自动化测试

- `tests/business/test_business_db.py` 使用 `tmp_path` 为测试创建临时数据库。
- `monkeypatch` 只在测试期间把三个脚本的 `DATABASE_PATH` 替换为临时路径，避免修改真实业务数据。
- 6 项测试覆盖表和数据数量、未维修工单保留、设备维修次数、不存在设备、外键约束以及防重复种子数据。
- `pyproject.toml` 的 pytest `pythonpath` 增加项目根目录，`scripts/__init__.py` 将本地脚本声明为可导入包。
- Phase 7 测试 6 项通过；与 LLM 和 RAG Tool 测试组合共 18 项通过。

### 7. 当前限制

- 当前使用同步 `sqlite3` 和本地 SQLite，只适合学习、开发和小规模单机验证。
- 当前没有数据库迁移工具；表结构变化仍需后续设计迁移方案。
- 数据为固定模拟数据，不包含生产级权限、审计、分页和并发写入能力。
- 结构化查询尚未封装成 LangChain Tool，也尚未接入 Agent Graph 或 FastAPI。

## Phase 8：Ticket Tools

### 1. 三层职责

```text
src/business/queries.py
↓
连接 SQLite、执行参数化 SQL、返回 list[dict]
↓
src/agents/ticket_tools.py 中的普通工具函数
↓
统计并组织业务结果、json.dumps() 转成 JSON 字符串
↓
LangChain BaseTool
↓
提供工具名称、说明、args_schema、参数校验和 invoke() 接口
```

- 数据访问层不依赖 LangChain，可以被 Tool、API、后台任务和测试复用。
- 普通工具函数不直接写 SQL，只调用数据访问层并整理模型容易理解的结果。
- `tool(function)` 只创建 Tool 对象，不会立即执行查询。
- `BaseTool.invoke()` 可以由测试代码手工调用，也可以在未来由 ToolNode 调用。

### 2. 应用数据访问层

- `PROJECT_ROOT = Path(__file__).resolve().parents[2]` 从源文件位置定位项目根目录，避免数据库路径依赖当前终端目录。
- `connect_business_db()` 检查 `business.db` 是否存在，启用外键检查，并设置 `sqlite3.Row`。
- `get_customer_tickets(customer_id)` 查询客户、设备、工单状态、优先级和维修记录数量。
- `get_device_repair_history(serial_number)` 查询设备所属客户、历史工单、诊断、维修操作、维修人员和维修时间。
- `sqlite3.Row → dict(row)` 将无字段名元组转换成带字段名的字典。

### 3. 两个 Ticket Tools

`Customer_Tickets`：

```text
输入：customer_id: int
输出：customer_id、ticket_count、tickets 的 JSON 字符串
```

`Device_Repair_History`：

```text
输入：serial_number: str
输出：设备、客户、ticket_count、repair_record_count、history 的 JSON 字符串
```

- Python 类型注解和 docstring 用于生成工具的 `args_schema` 与 description。
- JSON 具有稳定字段名，比位置依赖的 tuple 更容易被模型和程序正确理解。
- 集合推导式去重 `ticket_id`，避免同一工单的多条维修记录导致工单数重复。
- 布尔表达式求和统计非空的 `repair_record_id` 数量。
- 找不到设备时返回 `found: false` 和空历史；空序列号与非正客户 ID 会返回明确错误。

### 4. 手工 Tool 测试与未来 Agent 调用

当前独立测试：

```text
测试代码
↓
BaseTool.invoke()
↓
参数校验 → 普通工具函数 → business.queries → SQLite
↓
JSON 字符串
```

未来 Agent 调用：

```text
Qwen 生成 AIMessage.tool_calls（工具名、参数、调用 ID）
↓
ToolNode 找到并执行 BaseTool
↓
Ticket Tool 查询 SQLite 并返回 JSON
↓
ToolNode 包装成匹配调用 ID 的 ToolMessage
↓
第二次 model 组织最终回答
```

手工 `.invoke()` 不代表模型选择了工具，也不会自动产生 `AIMessage.tool_calls` 或 `ToolMessage`。

### 5. 自动化测试

- `tests/agents/test_ticket_tools.py` 包含 6 项测试。
- `tmp_path` 创建临时目录和临时 `business.db`，不接触真实业务数据库。
- `monkeypatch` 在测试期间将数据访问层的 `BUSINESS_DATABASE_PATH` 替换为临时文件，测试结束后自动恢复。
- 测试覆盖 Tool 名称和 Schema、客户工单 JSON、非法客户 ID、设备维修统计、不存在设备和空序列号。
- 测试使用真实临时 SQLite 和真实 SQL，但不调用 Qwen，也不生成 ToolMessage。
- Phase 8 Ticket Tool 测试 6 项通过；与 LLM、RAG Tool 和业务数据库测试组合共 24 项通过。

### 6. 当前限制

- Ticket Tools 尚未传给 `model.bind_tools()`，也尚未加入 ToolNode。
- 当前没有独立 Ticket Agent Graph，Qwen 不会自动选择这两个工具。
- 工具输出尚未经过真实小模型的 Tool Calling 兼容性和自然语言回答验证。
- 数据库仍是本地同步 SQLite，路径和业务错误还没有统一配置与异常类型。

## Phase 9：独立 Ticket Agent Graph

### 1. State 与 Graph 结构

`AgentState` 继承 `MessagesState`，并增加：

- `safety`：保存 Safeguard 结果。
- `remaining_steps`：LangGraph 管理的剩余执行步数。

Graph 节点与路由：

```text
guard_input
├─ unsafe → block_unsafe_content → END
└─ safe → model
              ↓
      pending_tool_calls()
       ├─ done → END
       └─ tools → ToolNode
                      ↓
                    model
```

- `builder = StateGraph(AgentState)` 是可继续增加节点和边的设计阶段对象。
- `ticket_assistant = builder.compile()` 是可以执行 `ainvoke()` 与 `astream()` 的 `CompiledStateGraph`。
- `MessagesState` 使用 `add_messages` 合并消息，节点返回 `{"messages": [response]}` 时会追加而不是覆盖历史。

### 2. 模型与工具绑定

- `model.bind_tools(tools)` 把两个 Ticket Tools 的名称、说明和参数 Schema 告诉 Qwen。
- `ToolNode(tools)` 保存并执行真正的 BaseTool。
- 两处必须使用同一组工具；否则模型可能请求 ToolNode 不具备的工具，或 ToolNode 有工具但模型从未看到。
- `RunnableLambda` 在每次模型调用前将 SystemMessage 与 State 中的消息组合，不把系统提示永久写入 Graph State。

### 3. 工具循环与消息对应

```text
HumanMessage
↓
AIMessage(tool_calls=[name, args, id])
↓
ToolMessage(tool_call_id=同一个 id, content=工具 JSON)
↓
AIMessage(content=最终回答, tool_calls=[])
↓
END
```

- `pending_tool_calls()` 检查最后一条消息必须是 AIMessage。
- `tool_calls` 有值时进入 tools，无值时进入 END。
- 工具请求 ID 与 `ToolMessage.tool_call_id` 必须一致，使模型能把每个结果对应到具体请求，尤其是一次请求多个工具时。
- tools 节点执行后固定回到 model，让模型根据原问题和 ToolMessage 生成用户可读答案。
- 当 `remaining_steps < 2` 且模型仍请求工具时，Graph 返回不带工具调用的普通 AIMessage，防止工具循环耗尽递归步数。

### 4. Fake Model Graph 测试

`tests/agents/test_ticket_assistant.py` 使用固定消息响应验证三条路由：

1. 模型返回普通 AIMessage：`model → END`。
2. 模型先返回 `Customer_Tickets` 工具调用，再返回最终回答：`model → tools → ToolMessage → model → END`。
3. Safeguard 返回 UNSAFE：`guard_input → block_unsafe_content → END`，模型不会执行。

- Fake Model 支持 `bind_tools()`，但不会自行推理；测试预先规定 `AIMessage.tool_calls`。
- Graph 测试临时替换 Tool 的执行函数，只验证节点、边、消息顺序和调用 ID；真实 SQL 已在 Phase 8 单独验证。
- Fake 测试稳定、快速，不依赖 Ollama，适合作为自动化回归测试。

### 5. 真实 Qwen 端到端验证

`qwen3:4b` 已分别成功完成两个真实工具循环：

```text
客户 1 工单问题
→ Customer_Tickets(customer_id=1)
→ ToolMessage 返回 3 张工单
→ 最终回答正确列出 1001 / 1002 / 1003 及状态
```

```text
SN-ACME-1001 维修历史问题
→ Device_Repair_History(serial_number="SN-ACME-1001")
→ ToolMessage 返回 2 条维修记录
→ 最终回答正确总结两次诊断和维修操作
```

两次真实测试均验证：

- Qwen 自主选择正确工具并生成正确参数。
- AIMessage 的工具调用 ID 与 ToolMessage 的 `tool_call_id` 一致。
- ToolNode 执行真实 BaseTool，读取真实 `business.db`。
- 第二次模型调用能根据 JSON 工具结果生成正确自然语言答案。
- 最终 AIMessage 的 `tool_calls` 为空，Graph 正常进入 END。

### 6. 测试与当前限制

- Ticket Agent Graph 测试 3 项通过；与 LLM、RAG、业务库和 Ticket Tool 测试组合共 27 项通过。
- 现有 4 个 warning 来自项目原有 LangGraph / `langchain-community` 弃用提示，不是本阶段回归。
- 当前没有 `GROQ_API_KEY` 时 Safeguard 会跳过真实安全模型并直接返回 SAFE；这不代表输入完成了真实安全检查。
- Ticket Agent 尚未加入 `src/agents/agents.py` 注册表，因此可以直接 `ticket_assistant.ainvoke()`，但 Service 尚不能根据 `ticket-assistant` 找到它。
- 当前尚未通过非流式或 SSE FastAPI 路径验证，也未接入 Streamlit。

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
RAG Tool：Database_Search → bge-m3 → Qdrant Top-K → BGE Reranker Top-N
↓
LangChain 消息：AIMessage / ToolMessage / AIMessageChunk
↓
ChatMessage JSON 或 SSE
↓
客户端展示

独立业务数据层（尚未接入 Agent）：
管理脚本 → SQLite business.db → customer / device / ticket / repair_record
↓
business.queries → Customer_Tickets / Device_Repair_History（可独立 invoke，也已绑定独立 Agent）
↓
独立 Ticket Agent：guard_input → model ↔ ToolNode → END（尚未注册到 Service）
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

### 7. 中文 Reranker 测试出现相反排序

- 现象：中文候选在终端显示为 `????`，两个无关中文文档得分很高，正确英文 PTO 文档得分很低。
- 初步风险：可能误判为 Reranker 不支持跨语言排序。
- 定位方法：将所有中文测试文本改成纯 ASCII 的 `\uXXXX` 转义，并打印 `unicode_escape`，验证 Python 实际收到的字符。
- 结果：正确中文 PTO 排第一、正确英文 PTO 排第二、两个无关中文文档得分很低，证明模型满足最小跨语言需求。
- 结论：第一次异常来自 PowerShell 管道中文编码，不是模型能力；评价模型前必须先验证实际输入。

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

## Phase 6 四关验收

- 看得懂：能定位 Qdrant 召回、Reranker 加载、候选评分、降序排序、Top-N 截取和上下文格式化的位置。
- 讲得清：能区分 Embedding、Qdrant、Reranker 和 Qwen 的输入输出，并说明为什么采用两级检索。
- 改得动：能够调整候选 K、最终 N、缓存配置，并用 FakeReranker 编写不依赖真实模型的排序测试。
- 会排错：能区分候选召回不足、Reranker 排序、固定 Top-N、Chunk 质量、模型缓存和 PowerShell 中文编码问题。

## Phase 7 四关验收

- 看得懂：能区分 LangGraph 状态库与业务库，并能说明四张业务表、主键、外键、约束和索引。
- 讲得清：能说明建库、按外键顺序插入、事务提交与回滚，以及两条结构化查询调用链。
- 改得动：能够增加查询函数、使用参数化 SQL，并通过 `JOIN`、`LEFT JOIN`、`GROUP BY` 和 `COUNT` 得到业务结果。
- 会排错：能区分导入路径、外键约束、重复种子数据、导入副作用和真实数据库被测试污染等问题。

## Phase 8 四关验收

- 看得懂：能区分数据访问函数、普通工具函数、BaseTool、模型工具请求、ToolNode 和 ToolMessage。
- 讲得清：能分别说明手工 `BaseTool.invoke()` 与未来 `model → ToolNode → ToolMessage → model` 的调用链。
- 改得动：能够增加带类型注解和 docstring 的 Ticket Tool，并将业务数据组织为稳定 JSON 输出。
- 会排错：能判断问题发生在参数 Schema、工具函数、SQL、数据库路径、JSON 序列化还是尚未接入 Agent 的边界。

## Phase 9 四关验收

- 看得懂：能区分 StateGraph builder、CompiledStateGraph、节点、普通边、条件边、MessagesState 和 RemainingSteps。
- 讲得清：能完整说明 `guard_input → model → tools → ToolMessage → model → END` 及工具调用 ID 的作用。
- 改得动：能够绑定新的 BaseTool、配置 ToolNode、增加路由测试，并用 Fake Model 控制不同 Graph 分支。
- 会排错：能区分模型未生成 tool_calls、工具名称不一致、ToolNode 执行失败、调用 ID 不匹配、无限循环、Ollama 状态和 Safeguard 被跳过等问题。

## Phase 10：Ticket Agent 的 Service / FastAPI 接入

### 1. Agent 注册

在 `src/agents/agents.py` 中导入编译后的 `ticket_assistant`，并以 `ticket-assistant` 为 key 加入 `agents` 注册表。

注册表把外部传入的字符串 `agent_id` 映射为可执行的 `CompiledStateGraph`。因此不需要为 Ticket Agent 单独编写一套 FastAPI 路由。

### 2. 动态路由复用

Service 已经提供以下动态路由：

```text
/{agent_id}/invoke
/{agent_id}/stream
```

请求 `/ticket-assistant/invoke` 或 `/ticket-assistant/stream` 时，FastAPI 从路径取得 `agent_id="ticket-assistant"`，然后通过 `get_agent(agent_id)` 从注册表选择 Ticket Agent。

`/info` 调用 `get_all_agent_info()` 读取同一个注册表，因此注册完成后会自动返回 Ticket Agent 的 key 和 description。

### 3. 非流式调用链

```text
POST /ticket-assistant/invoke
↓
FastAPI 解析 agent_id，并由 Pydantic 校验请求体
↓
_handle_input() 创建 HumanMessage 和 RunnableConfig
↓
get_agent("ticket-assistant") 取得 CompiledStateGraph
↓
agent.ainvoke() 执行 Ticket Agent
↓
model → ToolNode → model
↓
提取最终 AIMessage，转换为 ChatMessage 并追加 run_id
↓
FastAPI 序列化为 JSON
```

非流式响应只返回 Graph 完成后的最终 `AIMessage`。中间的工具请求已经执行完毕，最终消息不再请求工具，所以最终响应中的 `tool_calls` 可以为空；这不代表 Graph 没有调用工具。

### 4. 流式调用链

```text
POST /ticket-assistant/stream
↓
get_agent("ticket-assistant")
↓
agent.astream() 产生 Graph 执行事件
↓
message_generator() 包装 token/message SSE 事件
↓
StreamingResponse 发送给客户端
↓
data: [DONE]
```

流式接口的 HTTP 200 首先表示 SSE 连接已经建立，不保证后续模型或工具一定成功。连接建立后的异常仍可能通过 `type=error` 的 SSE 事件返回。

### 5. 验证结果

- `/info` 能列出 `ticket-assistant` 及其描述。
- `/ticket-assistant/invoke` 能调用 `Customer_Tickets`，返回客户 1 的 3 个工单及其状态。
- `/ticket-assistant/stream` 能依次显示工具请求、ToolMessage、最终回答和 `[DONE]`。
- `tests/agents/test_agent_loading.py` 新增注册测试，验证 `get_agent()` 返回正确 Graph，并验证 `/info` 使用的元数据。
- Agent loading 测试共 8 项，全部通过。
- 已确认测试断言位于测试方法内部，而不是在测试类定义阶段执行。

## Phase 10 四关验收

- 看得懂：能区分动态路由、`agent_id`、Agent 注册表、`get_agent()` 和 `CompiledStateGraph`。
- 讲得清：能完整说明 `/invoke` 与 `/stream` 从 HTTP 请求到 Graph 再到响应的调用链。
- 改得动：能够注册新 Agent，并补充 Agent loading 与元数据测试，不重复编写 Service 路由。
- 会排错：能区分 Agent 未注册、路径 key 错误、模型或工具执行失败、SSE 连接成功但流内返回 error，以及测试缩进错误。

## Phase 11：Streamlit 客户端接入与 SSE 展示

### 1. 动态 Agent 列表

`AgentClient` 初始化时通过 `retrieve_info()` 请求 `/info`，并把服务端元数据保存到 `self.info`。

```text
agents 注册表
↓
GET /info
↓
AgentClient.retrieve_info()
↓
self.info.agents：所有候选 Agent
↓
Streamlit selectbox
↓
self.agent：当前选择的一个 Agent
```

因此 Phase 10 注册 `ticket-assistant` 后，它会自动出现在 Streamlit 下拉框，不需要在生产前端中再次写死。

### 2. 客户端请求地址

用户选择 `ticket-assistant` 后，`agent_client.agent` 保存当前选择。`AgentClient.astream()` 使用：

```python
f"{self.base_url}/{self.agent}/stream"
```

生成 `/ticket-assistant/stream` 请求地址。非流式调用同理生成 `/ticket-assistant/invoke`。

### 3. SSE 解析

`_parse_stream_line()` 把服务端 SSE 文本行转换为客户端对象：

```text
type=token   → str
type=message → ChatMessage
[DONE]       → None
```

`astream()` 是异步生成器，它逐行读取 SSE，并通过 `yield` 把 `str` 或 `ChatMessage` 交给 Streamlit；遇到 `None` 时结束循环。

### 4. Streamlit 消息展示

- `streaming_content`：累加目前收到的 token。
- `streaming_placeholder`：反复更新页面上的同一个显示位置。
- 最终 `AIMessage` 到达后，用完整内容覆盖 placeholder，避免重复显示。
- `call_results` 使用工具调用 ID 保存状态框；收到 `ToolMessage` 后，通过 `tool_call_id` 更新正确的工具状态框。

### 5. 自动化测试

`tests/app/conftest.py` 的 `mock_info` 增加 `ticket-assistant`，模拟 `/info` 返回动态 Agent 列表。

`test_app_settings()` 模拟用户在下拉框选择 `ticket-assistant`，并断言 `mock_agent_client.agent` 已更新。

测试最初出现 `AppTest script run timed out`，真正原因是公共 `mock_env` 使用 `clear=True` 清除了 Windows 的 `USERPROFILE`，导致 Streamlit 线程中的 `Path.home()` 抛出：

```text
RuntimeError: Could not determine home directory.
```

修复方式是在 App 测试 fixture 中使用 `tmp_path` 创建临时目录，并用 `monkeypatch.setenv()` 临时设置 `USERPROFILE`。测试结束后环境变量自动恢复。

### 6. 验证结果

- Streamlit 下拉框能够显示并选择 `ticket-assistant`。
- `Customer_Tickets` 和 `Device_Repair_History` 均能显示工具输入、输出和最终回答。
- `tests/client/test_client.py` 与 `tests/app/test_streamlit_app.py` 共 26 项测试，全部通过。
- Ruff 与 `git diff --check` 均通过。
- 生产客户端无需修改，本阶段只补充回归测试和测试环境修复。

## Phase 11 四关验收

- 看得懂：能区分 `self.info.agents`、`self.agent`、`_parse_stream_line()`、`astream()` 和 `draw_messages()`。
- 讲得清：能说明从 `/info` 到下拉框，以及从 SSE 到页面 token、工具状态框和最终答案的完整链路。
- 改得动：能够给 UI mock 增加 Agent，并修改 AppTest 验证选择结果。
- 会排错：能从外层 timeout 继续追查到底层线程异常，并用 `tmp_path` 与 `monkeypatch` 隔离测试环境。

## Phase 12：多轮对话 Memory

### 1. 核心概念

- LangGraph State：Agent 当前执行所需的完整状态。
- `messages`：State 中保存消息历史的一个字段。
- Checkpoint：某一时刻的完整 Graph State 快照。
- Checkpointer：负责保存和读取 Checkpoint。
- `thread_id`：标识一段具体对话，是恢复 thread 范围短期记忆的主要 key。
- `user_id`：标识用户，用于归类该用户的多个 thread，并为跨 thread Store 提供用户范围。

相同 `user_id`、不同 `thread_id` 的对话不会自动共享短期消息历史。

### 2. Checkpointer 初始化

FastAPI 启动时，`lifespan()` 调用 `initialize_database()`。当前默认 SQLite 配置创建 `AsyncSqliteSaver`，随后通过：

```python
agent.checkpointer = saver
```

把同一个 Checkpointer 注入已加载的 Agent。SQLite 数据保存在 `checkpoints.db`，与保存客户、设备、工单和维修记录的 `data/business.db` 职责不同。

### 3. 多轮调用链

```text
客户端发送 message、thread_id、user_id
↓
_handle_input() 创建 RunnableConfig
↓
configurable.thread_id 确定对话 State
metadata 记录 user_id 与 agent_id
↓
LangGraph 通过 Checkpointer 恢复旧 State
↓
MessagesState / add_messages 合并新的 HumanMessage
↓
Graph 执行并保存新 Checkpoint
```

客户端第二轮只需要发送新消息并复用相同 `thread_id`，不需要重新发送第一轮全部历史。

### 4. `/history` 与 `/threads`

- `/history`：根据 `agent_id + thread_id` 返回一段对话的完整 `ChatHistory.messages`。
- `/threads`：根据 `user_id + agent_id` 返回该用户在指定 Agent 下的会话摘要列表。
- Streamlit 的 Previous Chats 先调用 `/threads`，用户点击后再调用 `/history`，最后把消息写入 `st.session_state.messages`。
- New Chat 只清空页面消息并生成新 `thread_id`，不会删除旧 Checkpoint。

`st.session_state.messages` 是前端页面状态；Checkpoint 中的 `messages` 是服务端持久化的 LangGraph State 字段，两者不能混为一谈。

### 5. Checkpointer 与 Store

```text
Checkpointer
→ thread 范围短期对话记忆

Store
→ 跨 thread 的用户记忆
```

“短期/长期”描述作用范围，不等同于存储介质。当前 SQLite Checkpointer 写入磁盘，服务重启后仍存在；SQLite 模式的 Store 使用 `InMemoryStore`，服务重启后会丢失。

### 6. 真实验证

- 使用相同 `thread_id` 完成两轮 Ticket 对话；第二轮通过指代词使用第一轮 ToolMessage，没有重复调用工具。
- `/history` 返回 `human → ai(tool_calls) → tool → ai → human → ai` 共 6 条消息。
- 重启 FastAPI 后仍能从 `checkpoints.db` 恢复相同 6 条消息，证明 SQLite Checkpoint 持久化。
- 同一 `user_id` 创建两个不同 thread，`/threads` 能同时列出，但各自 `/history` 分别只有 6 条和 2 条消息，证明 State 隔离。

### 7. 自动化测试

在 `tests/service/test_service_real_graphs.py` 新增 `test_invoke_isolates_state_between_threads`：

```text
thread-a 第一次 → heard 1 messages
thread-b 第一次 → heard 1 messages
thread-a 第二次 → heard 3 messages
```

参数化 fixture 让同一测试分别使用 `MemorySaver` 和 `AsyncSqliteSaver` 执行，两项均通过。

完整相关回归中 54 项通过，唯一一次失败是 Streamlit AppTest 默认 3 秒偶发超时。该测试没有底层线程异常，单项连续两次分别在 2.74 秒和 2.56 秒通过，因此判断为测试环境时序波动，暂不扩大代码改动。

## Phase 12 四关验收

- 看得懂：能区分 State、messages、Checkpoint、Checkpointer、Store、`thread_id` 与 `user_id`。
- 讲得清：能说明相同 thread 的 State 恢复、不同 thread 的隔离，以及 `/threads → /history → Streamlit` 调用链。
- 改得动：能够为 MemorySaver 与 SQLiteSaver 增加相同的 thread 隔离回归测试。
- 会排错：能区分客户端页面状态、服务端 Checkpoint、业务数据库、固定功能失败和偶发测试超时。

## 下一阶段需要理解的内容

Phase 13 开始 MCP：先理解普通 BaseTool 与 MCP Tool 的边界，再创建最小 ticket MCP Server，只暴露少量只读工具并接入 Agent；暂不提前做 Docker、Evaluation 或求职材料。

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

### Phase 6

1. Embedding、Qdrant、Cross-Encoder Reranker 和 Qwen 的输入输出分别是什么？
2. 为什么采用“Qdrant Top-K 召回 → Reranker Top-N 精排”，而不是让 Reranker 扫描整个知识库？
3. `RETRIEVAL_K=5` 和 `RERANK_TOP_N=2` 分别控制哪个阶段？
4. 模型磁盘缓存与 `lru_cache` 的生命周期和作用有什么区别？
5. 为什么经过 Reranker 后仍可能包含不相关 Chunk，应该从哪些层面排查和优化？

### Phase 7

1. 为什么 LangGraph Checkpoint 与客户、设备、工单等业务数据应该使用不同的数据库？
2. `customer → device → ticket → repair_record` 的主外键关系是什么，为什么 `ticket` 不重复保存 `customer_id`？
3. SQLite 为什么需要在每个连接中启用外键检查，插入数据为什么必须遵守父表到子表的顺序？
4. `JOIN` 与 `LEFT JOIN` 有什么区别，为什么统计全部工单维修次数时需要 `LEFT JOIN`？
5. 事务的 `commit()` 和 `rollback()` 分别有什么作用，pytest 如何避免修改真实的 `business.db`？

### Phase 8

1. `business/queries.py`、普通工具函数和 BaseTool 分别承担什么职责？
2. Tool 的 name、description 和 `args_schema` 分别从哪里产生，执行前如何校验输入？
3. 为什么手工执行 `BaseTool.invoke()` 不代表 Qwen 已经选择了工具，也不会生成 ToolMessage？
4. 为什么 Ticket Tool 返回带字段名的 JSON，而不是无字段名的 tuple？
5. `tmp_path` 和 `monkeypatch` 如何避免 Ticket Tool 测试修改真实业务数据库？

### Phase 9

1. StateGraph builder 与 `compile()` 后的 CompiledStateGraph 分别用于什么？
2. `model.bind_tools(tools)` 与 `ToolNode(tools)` 分别承担什么职责，为什么要使用同一组工具？
3. `pending_tool_calls()` 如何控制 `model → tools → model` 循环，RemainingSteps 如何防止循环失控？
4. 为什么 AIMessage 工具请求 ID 必须与 ToolMessage 的 `tool_call_id` 对应？
5. Fake Model Graph 测试和真实 Qwen 端到端测试分别证明什么，为什么当前 Agent 仍不能通过 FastAPI 路径访问？

### Phase 10

1. 为什么注册 `ticket-assistant` 后可以直接复用 `/{agent_id}/invoke` 和 `/{agent_id}/stream`，不需要新增路由？
2. `get_agent(agent_id)` 如何把 URL 中的字符串转换为可执行的 `CompiledStateGraph`？
3. `/invoke` 和 `/stream` 分别如何执行并返回 Agent 结果，为什么非流式最终消息的 `tool_calls` 可以为空？
4. `/info` 为什么能自动显示新 Agent，`get_all_agent_info()` 与 `agents` 注册表是什么关系？
5. 为什么流式接口返回 HTTP 200 仍不能证明模型和工具执行成功，客户端还必须检查哪些 SSE 事件？

### Phase 11

1. `ticket-assistant` 为什么不需要写死在 Streamlit 中也能自动出现在 Agent 下拉框？
2. `self.info.agents` 与 `self.agent` 分别保存什么，当前 Agent 如何参与 invoke / stream URL 拼接？
3. `_parse_stream_line()` 如何处理 token、message、error 和 `[DONE]`，`astream()` 为什么属于异步生成器？
4. `streaming_content`、`streaming_placeholder` 和 `call_results` 分别如何展示 token 与工具调用？
5. 为什么 AppTest 的外层 timeout 不一定是真正根因，本次如何通过 `tmp_path` 与 `monkeypatch` 修复 `Path.home()`？

### Phase 12

1. LangGraph State、`messages`、Checkpoint 和 Checkpointer 分别是什么，它们之间有什么关系？
2. `thread_id` 与 `user_id` 分别解决什么问题，为什么相同用户的不同 thread 不共享短期历史？
3. 第二轮请求复用相同 `thread_id` 时，旧 State 如何恢复，新 HumanMessage 如何与旧 messages 合并？
4. Checkpointer 与 Store 的记忆范围有什么区别，为什么 SQLite Checkpointer 可以持久化，而当前 InMemoryStore 重启后会丢失？
5. `/threads`、`/history` 和 Streamlit Previous Chats 如何协作，如何测试同一用户的不同 thread 相互隔离？

Phase 1 至 Phase 12 均已逐项学习并验收通过。

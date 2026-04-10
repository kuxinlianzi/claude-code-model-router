# 智能路由网关（Model Router）设计文档

## 1. 概述

智能路由网关是一个用于根据任务复杂度自动选择合适大语言模型的代理服务器。其核心理念是**"用简单的模型判断任务的难度，然后调度更强的模型完成复杂任务"**，从而在保证质量的同时优化成本。

### 1.1 解决的问题

- **成本控制**：简单任务使用轻量模型，避免浪费昂贵资源
- **效率优化**：复杂任务自动路由到强推理模型，保证输出质量
- **透明路由**：对客户端完全隐藏路由逻辑，保持 API 兼容性

### 1.2 系统定位

```
用户 → Anthropic 格式请求 → [本网关] → 复杂度评估 → 路由至 DashScope → 返回结果
```

---

## 2. 核心设计理念

### 2.1 复杂度分层思想

采用**双阶分类法**将任务复杂度分为两个区间，对应不同能力层级的模型：

```
┌─────────────────────────────────────────────────────┐
│          LIGHTWEIGHT INTERVAL (Level 1-5)           │
│   执行层任务：无深度推理，模式匹配，常规操作         │
├─────────────────────────────────────────────────────┤
│              THRESHOLD LINE                         │
│           >> 需要强推理能力 <<                       │
├─────────────────────────────────────────────────────┤
│          HEAVYWEIGHT INTERVAL (Level 6-10)          │
│   思考层任务：多步推理，逻辑演绎，深度专业知识       │
└─────────────────────────────────────────────────────┘
```

### 2.2 为什么是 1-10 分级？

| 理由 | 说明 |
|------|------|
| **足够精细** | 10 级可以区分从"打招呼"到"世界级难题"的连续谱系 |
| **清晰阈值** | 以 6 分为界（≥6 为重任务），便于决策 |
| **可扩展性** | 若未来增加更多模型档位，可灵活扩展为多级路由 |

### 2.3 轻量级区间（Level 1-5）

这些任务特点是**确定性高、推理链短、容错性强**：

| Level | 类型 | 典型场景 | 错误容忍度 |
|-------|------|----------|-----------|
| 1 | 问候测试 | "hello", "test", "谢谢" | 极高 |
| 2 | 文本变换 | 翻译、大小写转换、拼写检查 | 高 |
| 3 | 基础问答 | "地球有多大"、提取明确信息 | 中高 |
| 4 | 简单摘要 | 例行邮件、段落格式化 | 中 |
| 5 | 带约束生成 | 300 字文章、冒泡排序代码 | 中低 |

**关键特征**：
- 答案通常可验证
- 不需要长链条推理
- 模式匹配即可解决

### 2.4 重量级区间（Level 6-10）

这些任务特点是**需要深度推理、领域知识、多步骤规划**：

| Level | 类型 | 典型场景 | 推理需求 |
|-------|------|----------|---------|
| 6 | 创意 + 中等代码 | 3+ 约束的文案、中等难度 API 集成 | 多条件权衡 |
| 7 | 技术排查 | 调试、数据库设计、日志分析 | 因果推理 |
| 8 | 专业领域 | 法律/医学/金融分析、学术写作 | 专业知识 + 深度推理 |
| 9 | 大型规划 | 活动策划（预算/时间/宣传） | 多步骤规划 |
| 10 | 创新难题 | 数学推导、算法创新、复杂世界观 | 创造性思维 |

**关键特征**：
- 答案不可预知
- 需要长链条思考
- 涉及专业领域或创造性工作

### 2.5 评估维度

评判复杂度时综合考虑以下四个维度：

1. **是否需要多步骤推理？**  
   - 单步查询 → 低级
   - 多步串联 → 高级

2. **是否有多个约束条件？**  
   - 单一约束 → 低级
   - 三重及以上约束 → 高级

3. **是否依赖专业领域知识？**  
   - 通用常识 → 低级
   - 法律/医学/金融/学术等 → 高级

4. **错误的代价有多高？**  
   - 无影响 → 低级
   - 可能导致严重后果 → 高级

---

## 3. 系统架构

### 3.1 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
│                   (Any Anthropic-compatible Client)              │
└──────────────────────────────────┬──────────────────────────────┘
                                   │ HTTP POST /v1/messages
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Model Router Gateway                         │
│                            (This App)                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  FastAPI Server                                          │   │
│  │  - Port: 8888 (configurable)                             │   │
│  │  - Endpoints: /v1/messages, /messages, /health          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                 │                                │
│  ┌──────────────────────────────▼─────────────────────────────┐ │
│  │  Complexity Judge Module                                   │ │
│  │  ├─ Extract & filter user messages                        │ │
│  │  ├─ Take LAST valid user message only                     │ │
│  │  ├─ Truncate to 2000 chars if needed                     │ │
│  │  ├─ Call Ollama via /api/generate (not /api/chat)        │ │
│  │  └─ Output: integer 1-10                                 │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                 │                                │
│  ┌──────────────────────────────▼─────────────────────────────┐ │
│  │  Routing Logic                                             │ │
│  │  if score >= 6:                                            │ │
│  │      select qwen3.6-plus    ← Heavyweight                  │ │
│  │  else:                                                     │ │
│  │      select qwen3.5-flash   ← Lightweight                  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                 │                                │
│  ┌──────────────────────────────▼─────────────────────────────┐ │
│  │  Proxy to DashScope                                        │ │
│  │  ├─ Override `model` field in request                      │ │
│  │  ├─ Add Bearer token                                       │ │
│  │  ├─ Transparent SSE passthrough                          │ │
│  │  └─ Extract & log token usage                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬──────────────────────────────┘
                                   │ HTTPS
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DashScope API                              │
│              (Qwen3.5-Flash / Qwen3.6-Plus)                      │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 模块职责划分

| 模块 | 职责 | 关键技术 |
|------|------|---------|
| **FastAPI Server** | 接收请求、消息过滤、路由分发、响应返回 | FastAPI, uvicorn |
| **HTTP Client Pool** | 连接复用、超时控制、重试机制 | httpx.AsyncClient |
| **Message Filter** | 提取真实用户指令、过滤工具响应和 UI 干扰 | `extract_text_content`, `is_valid_user_message` |
| **Complexity Judge** | 调用本地小模型评估任务难度 | Ollama `/api/generate` |
| **Routing Logic** | 根据分数决定目标模型 | 规则引擎 |
| **Proxy to DashScope** | 转发请求、流式传输、token 统计 | SSE passthrough |

---

## 4. 关键设计细节

### 4.1 连接池管理

```python
_global_client = None

def get_http_client():
    global _global_client
    if _global_client is None:
        _global_client = httpx.AsyncClient(
            timeout=300.0,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=60.0,
            ),
        )
    return _global_client
```

**设计理由**：
- 全局单例避免重复创建开销
- `max_connections=100` 支持高并发
- `keepalive_expiry=60s` 减少握手次数

### 4.2 指数退避重试

```python
async def request_with_retry(client, method, url, headers, data, retries=3):
    last_exception = None
    for attempt in range(retries):
        try:
            resp = await client.post(url, content=data, headers=headers)
            if resp.status_code >= 500:
                raise httpx.HTTPError(f"Server error: {resp.status_code}")
            return resp
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_exception = e
            if attempt < retries - 1:
                wait = 0.5 * (2**attempt) + random.uniform(0, 0.3)
                log(f"[WARN] Retry {attempt+1}/{retries} after {wait:.1f}s")
                await httpx.sleep(wait)
    raise last_exception
```

**设计理由**：
- 指数退避（0.5s → 1s → 2s）避免雪崩效应
- 随机抖动防止集体恢复时的同步问题
- 只重试 5xx 和连接/超时错误，不重试客户端错误

### 4.3 流式传输透明透传

```python
if body.get("stream"):
    async def event_stream():
        full_text_parts = []
        async for chunk in resp.aiter_bytes():
            yield chunk               # 直接透传原始字节
            full_text_parts.append(chunk)
        
        # 流结束后解析 token 用量
        full_text = b"".join(full_text_parts).decode("utf-8")
        input_tokens = parse_input_tokens(full_text)
        output_tokens = parse_output_tokens(full_text)
    
    return StreamingResponse(...)
```

**设计理由**：
- 字节级透传保持格式零损耗
- 流结束后再统计 token，不影响用户体验
- 兼容任何上游 API 的 SSE 格式

### 4.4 复杂度评估提示词设计

**2026-04-10 更新**: 改用 `/api/generate` 端点，精简 Prompt 结构，提升小模型指令跟随能力

**Prompt 结构**：

```
你是一位顶级的 LLM 路由网关。请评估用户输入的语义复杂度和逻辑推理深度，输出 1-10 的复杂度分数。

=== 轻量级区间：Level 1-5（执行层任务：无深度推理，模式匹配）===
Level 1: 问候、感谢、无意义测试
Level 2: 简单单词翻译、拼写检查、大小写转换
Level 3: 基础知识问答、从短文本提取显式信息
Level 4: 简单摘要、写例行邮件、基本格式化
Level 5: 带少量约束的文本生成、非常基础的代码

--- >> 超过此线需要强推理能力 << ---

=== 重量级区间：Level 6-10（思考层任务：多步推理，逻辑演绎，深度专业知识）===
Level 6: 创意任务 (3+ 约束)、中等难度代码、逻辑谜题
Level 7: 复杂代码调试、API 集成设计、数据库模式规划
Level 8: 法律/医学/金融/学术深度分析、图表数据推理
Level 9: 多步骤规划、大型任务策划
Level 10: 复杂数学推导、创新算法设计、庞大世界观构建

评估考虑：
1. 是否需要多步骤推理？
2. 有多少个约束条件？
3. 是否需要专业领域知识？
4. 错误的代价有多高？

只输出一个 1-10 的整数。

[用户任务内容]
```

**Prompt 结构优化**：

1. **Instruction 前置**: 将 role definition + classification criteria 放在开头，让模型先"记住任务要求"
2. **Context 隔离**: 只传最后一条用户消息，不传 system prompt 和历史对话
3. **结尾提示词**: 在 user input 后加 "Complexity score:"，引导模型直接输出数字
4. **截断阈值**: 从 3000 字符降至 2000 字符（小模型处理长文能力弱）

**技术改进细节**：

**A. 消息过滤 (新增)**

```python
async def extract_text_content(message: dict) -> str:
    """从 message dict 中提取纯文本内容"""
    ...

def is_valid_user_message(text: str) -> bool:
    """过滤工具响应和 UI 干扰"""
    if any(pattern in text_lower for pattern in [
        '<tool_use_id', '<tool-result', 'tool_result',
        '<system-reminder', 'sessionstart hook',
        'exit code', 'parse error', '/clear', ...
    ]):
        return False
    return True
```

**B. `/api/generate` vs `/api/chat`**

| 端点 | 输入格式 | 对小模型友好度 |
|------|---------|--------------|
| `/api/chat` | `messages=[{"role": "user", "content": "..."}]` | ⭐⭐ |
| `/api/generate` | `prompt="instruction\n\nUser input\nOutput:"` | ⭐⭐⭐⭐⭐ |

**原因**: `qwen2.5:1.5b` 的指令跟随能力较弱，需要更清晰的 instruction→context→output 三段式结构。

**C. 错误处理增强**

```python
# 解析逻辑：优先匹配行首数字，fallback 到全文搜索 1-9 单 digit
for line in lines:
    match = re.match(r'^(\d+)', stripped)
    ...
if score is None:
    log(f"[WARN] Judge parsing error...")
    return 5  # 降级策略
```

---

---

### 4.6 默认降级策略

```python
try:
    score = await judge_complexity(user_messages, system_prompt)
except Exception as e:
    log(f"[WARN] Judge failed ({e}), defaulting to 5")
    return 5
```

### 4.6 默认降级策略

当评测器失败时回退到中等复杂度 (5)，保证服务可用性。

---

## 5. 配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8888` | 服务端口 |
| `JUDGE_MODEL` | `qwen2.5:1.5b` | 本地复杂度评测模型 |
| `OLLAMA_PORT` | `11434` | Ollama 服务端口 |
| `OLLAMA_TIMEOUT` | `8s` | 评测请求超时时间 |
| `CHEAP_MODEL` | `qwen3.5-flash` | 轻量级路由目标 |
| `EXPENSIVE_MODEL` | `qwen3.6-plus` | 重量级路由目标 |
| `DASHSCOPE_API_KEY` | — | DashScope API 密钥 |

**扩展建议**：
- 可通过环境变量注入敏感配置
- 未来可支持动态切换模型而不重启服务

---

## 6. API 接口

### 6.1 健康检查

```http
GET /health
```

响应：
```json
{ "status": "ok" }
```

### 6.2 根路径信息

```http
GET /
```

响应：
```json
{
  "status": "ok",
  "judge_model": "qwen2.5:1.5b",
  "cheap_model": "qwen3.5-flash",
  "expensive_model": "qwen3.6-plus",
  "uptime": "2026-04-09 12:34:56"
}
```

### 6.3 消息路由

```http
POST /v1/messages
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "帮我分析一下这段报错日志"}
  ],
  "stream": true
}
```

响应：SSE 流（与 DashScope 原生格式一致）

---

## 7. 日志与监控

### 7.1 路由决策日志

```
[complexity=7/10] judge=1.23s → qwen3.6-plus
  tokens: input=128, output=512
```

**关键字段**：
- `complexity=X/10`：评估到的复杂度分数
- `judge=Y.YYs`：评测耗时
- `model`：最终选择的模型
- `tokens`：输入/输出 token 数

### 7.2 监控价值

通过分析路由日志可以：
1. **优化成本**：查看是否过多任务被路由到高价模型
2. **调优阈值**：如果 5 分和 6 分任务分布不均，可调整分界线
3. **发现异常**：某类任务频繁导致 judge 超时或失败

---

---

## 8. 并发控制与响应排序 (2026-04-10)

### 8.1 问题描述

当多个并发请求到达时，由于不同复杂度模型的处理时间差异和网络延迟波动，可能导致**后提交的请求先于之前提交的请求返回结果**。例如：

1. 请求 A（complexity ≥ 6 → qwen3.6-plus）评测耗时 5s，模型响应 8s
2. 请求 B（complexity < 6 → qwen3.5-flash）评测耗时 1s，模型响应 3s

B 可能比 A 早完成 4 秒，导致前端收到的消息顺序错乱。

此外，流式响应出错时（如网络断开），原代码只 `yield err` 但**不会调用 enqueue_response()**，导致后续请求永久阻塞在 `dequeue_ordered_response()`，造成死锁。

### 8.2 解决方案：FIFO 队列 + 超时机制

#### 全局状态管理

```python
_response_queue = asyncio.Queue()  # FIFO queue: (sequence_id, bytes_data)
_order_lock = asyncio.Lock()
_sequence_counter = 0

async def enqueue_response(raw_bytes: bytes) -> int:
    """收集完整响应并加入有序队列释放。返回序列号"""
    global _sequence_counter
    async with _order_lock:
        seq = _sequence_counter
        _sequence_counter += 1
    await _response_queue.put((seq, raw_bytes))
    return seq

async def dequeue_ordered_response() -> bytes:
    """阻塞等待下一个有序响应可用。"""
    _, data = await _response_queue.get()
    return data
```

#### Buffer-Then-Yield 模式

修改 `proxy_to_dashscope` 中的流式处理逻辑：

```python
if body.get("stream"):
    async def event_stream():
        try:
            resp = await request_with_retry(...)
            
            # 第一步：完整收集所有 chunks（不立即 yield）
            full_text_parts = []
            async for chunk in resp.aiter_bytes():
                full_text_parts.append(chunk)  # 仅缓冲，无修改
            
            # 第二步：解析 token 统计
            full_text = b"".join(full_text_parts).decode("utf-8", errors="ignore")
            # ... parse input_tokens, output_tokens ...
            
            # 第三步：将完整响应加入队列
            await enqueue_response(b"".join(full_text_parts))
            
            # 第四步：带超时等待自己的轮次（防死锁）
            timeout_sec = 60 if model == EXPENSIVE_MODEL else 30
            
            try:
                yielded_data = await asyncio.wait_for(
                    dequeue_ordered_response(),
                    timeout=timeout_sec
                )
                yield yielded_data
            except asyncio.TimeoutError:
                log(f"[WARN] Request timeout for {model} after {timeout_sec}s")
                
        except httpx.ConnectError as e:
            log(f"[ERROR] DashScope connection failed: {e}")
            err = json.dumps({"error": {"type": "connection_error", ...}}).encode()
            await enqueue_response(err)  # 错误时也入队，防止死锁
            yield err
```

### 8.3 超时策略

| 模型类型 | 等待超时 | 适用场景 |
|---------|---------|----------|
| 轻量级 (qwen3.5-flash) | 30 秒 | 简单任务，快速失败 |
| 重量级 (qwen3.6-plus) | 60 秒 | 复杂任务，允许更长等待 |

超时后的行为：**静默跳过该请求**，继续处理后续请求。避免一个卡住的请求拖垮整个服务。

### 8.4 设计权衡

| 方面 | 优化前 | 优化后 |
|------|--------|-------|
| **顺序保证** | 无 - 真透传 | 严格 FIFO |
| **延迟** | 极低 - 即时流式 | 较高 - 需等待前序释放 |
| **内存占用** | 低 - 逐块流式 | 较高 - 整响应缓冲 |
| **鲁棒性** | 错误时可能死锁 | 超时降级，永不挂起 |

### 8.5 测试建议

1. **并发压力测试**：同时发起 5+ 个不同复杂度的请求，验证返回顺序
2. **超时触发测试**：人为模拟上游延迟超过 30/60 秒，验证优雅降级
3. **错误恢复测试**：模拟网络中断，验证队列不会被永久阻塞
4. **解析错误验证**：测试 Ollama 返回非标准格式时的默认行为

```bash
# 测试复杂度 1（问候/测试类）
curl -X POST http://localhost:8888/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "test"}], "stream": false}'

# 预期输出包含 "qwen3.5-flash"（复杂度 < 6）
```

---

## 7. 未来演进方向

### 7.1 多级路由（3+ 档位）

当前二分法可扩展为三级：

```
Level 1-3  → 最快最便宜模型（如 qwen-max-turbo）
Level 4-6  → 均衡模型（如 qwen3.5-flash）
Level 7-10 → 最强模型（如 qwen3.6-plus）
```

### 7.2 缓存机制

对重复的相同 query 直接返回缓存结果，避免重复调用：

```python
cache_key = hash(messages)
if cache.exists(cache_key):
    return cache.get(cache_key)
```

### 7.3 异步评测器

当前复杂度评测阻塞主线程，可改造为独立协程预先评估：

```python
score_task = asyncio.create_task(judge_complexity(...))
# 处理其他请求...
score = await score_task
```

### 7.4 A/B 测试框架

对不同任务随机分配两种评分策略，对比效果：

```python
if experimental_mode and random.random() < 0.5:
    score = await judge_complexity_v2(...)
else:
    score = await judge_complexity(...)
```

---

## 7.5 总结

智能路由网关的核心价值在于**"用最小代价实现最佳效果平衡"**：

| 优势 | 说明 |
|------|------|
| **成本低** | 简单任务走轻量模型，节省大量 API 费用 |
| **质量稳** | 复杂任务自动路由到强模型，保证输出水平 |
| **易部署** | 仅依赖本地 Ollama + DashScope，无需额外基础设施 |
| **透明化** | 对客户端完全隐藏路由逻辑，API 不变 |

这套设计的精髓是**"用小型智能筛选大型需求"**——用一个 1.5B 的小模型做守门员，决定是否要调用强大的 3.6B+ 模型，既经济又高效。

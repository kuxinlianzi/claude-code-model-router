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
│  │  ├─ Input: user messages + system prompt                   │ │
│  │  ├─ Trim to 3000 chars if needed                           │ │
│  │  ├─ Call Ollama qwen2.5:1.5b                               │ │
│  │  └─ Output: integer 1-10                                   │ │
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
| **FastAPI Server** | 接收请求、路由分发、响应返回 | FastAPI, uvicorn |
| **HTTP Client Pool** | 连接复用、超时控制、重试机制 | httpx.AsyncClient |
| **Complexity Judge** | 调用本地小模型评估任务难度 | Ollama API |
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

**设计理由**：
- 分区间描述让评分标准更清晰
- 给出具体例子降低歧义
- 明确的 4 个评估维度引导评分
- 强调"只输出整数"确保解析可靠性

### 4.5 默认降级策略

```python
try:
    score = await judge_complexity(user_messages, system_prompt)
except Exception as e:
    log(f"[WARN] Judge failed ({e}), defaulting to 5")
    return 5
```

**设计理由**：
- 当评测器失败时回退到中等复杂度 (5)
- 5 分是轻量级区间的上限，避免误判为高复杂度而浪费资源
- 同时保证服务可用性——即使评测失效，仍能提供服务

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

## 8. 未来演进方向

### 8.1 多级路由（3+ 档位）

当前二分法可扩展为三级：

```
Level 1-3  → 最快最便宜模型（如 qwen-max-turbo）
Level 4-6  → 均衡模型（如 qwen3.5-flash）
Level 7-10 → 最强模型（如 qwen3.6-plus）
```

### 8.2 缓存机制

对重复的相同 query 直接返回缓存结果，避免重复调用：

```python
cache_key = hash(messages)
if cache.exists(cache_key):
    return cache.get(cache_key)
```

### 8.3 异步评测器

当前复杂度评测阻塞主线程，可改造为独立协程预先评估：

```python
score_task = asyncio.create_task(judge_complexity(...))
# 处理其他请求...
score = await score_task
```

### 8.4 A/B 测试框架

对不同任务随机分配两种评分策略，对比效果：

```python
if experimental_mode and random.random() < 0.5:
    score = await judge_complexity_v2(...)
else:
    score = await judge_complexity(...)
```

---

## 9. 总结

智能路由网关的核心价值在于**"用最小代价实现最佳效果平衡"**：

| 优势 | 说明 |
|------|------|
| **成本低** | 简单任务走轻量模型，节省大量 API 费用 |
| **质量稳** | 复杂任务自动路由到强模型，保证输出水平 |
| **易部署** | 仅依赖本地 Ollama + DashScope，无需额外基础设施 |
| **透明化** | 对客户端完全隐藏路由逻辑，API 不变 |

这套设计的精髓是**"用小型智能筛选大型需求"**——用一个 1.5B 的小模型做守门员，决定是否要调用强大的 3.6B+ 模型，既经济又高效。

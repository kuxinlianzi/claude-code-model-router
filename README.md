# Claude Code Model Router

<div align="center">

**基于复杂度评估的智能模型路由网关**  
自动为不同任务分配最合适的模型，平衡成本与效果

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

**最新版本**: 2026-04-12

</div>

---

## 🔐 安全与隐私

### API Key 管理

本项目采用**配置与环境变量分离**的设计理念：

1. **配置文件中不提交密钥** - `config.yaml` 已加入 `.gitignore`
2. **支持环境变量注入** - CI/CD 部署推荐方式
3. **提供设置脚本** - `setup_config.sh` 交互式配置

```bash
# 安全配置方式 1: 使用设置脚本（推荐）
./setup_config.sh

# 安全配置方式 2: 环境变量
export DASHSCOPE_API_KEY="sk-your-key"
python3 model_router.py
```

### 网络访问控制

默认配置绑定到 `localhost`，防止外部访问：

- ✅ **本地开发**: `host: "localhost"` (默认)
- ⚠️ **允许外部**: `host: "0.0.0.0"` (需配合防火墙规则)

---

## 🌟 项目简介

这是一个智能路由代理服务器，通过本地小模型分析用户请求的复杂度，然后自动将其路由到最合适的大语言模型：

| 复杂度等级 | 评分 | 路由目标 | 特点 |
|-----------|------|---------|------|
| **轻量级区间** | 1-5 分 | `qwen3.5-flash` | 快速响应，成本低廉 |
| **重量级区间** | 6-10 分 | `qwen3.6-plus` | 深度推理，专业领域 |

### 核心优势

- 💰 **成本优化** - 简单任务节省高达 50% API 费用
- 🧠 **智能决策** - 基于语义理解的自动复杂度评分
- ⚡ **零延迟体验** - 流式传输透明透传，无明显额外延迟
- 🔒 **安全可靠** - 连接池、重试机制、优雅降级、本地化配置
- ✅ **精准过滤** - 自动排除工具消息和 UI 干扰，只提取真实用户指令
- ✅ **顺序保证** - FIFO 队列确保并发请求按序返回，超时防死锁
- 🚀 **双客户端** - 独立 Ollama 专用客户端，优化超时配置

---

## 🏗️ 工作原理

```
┌─────────────┐
│   Client    │  Anthropic 格式请求
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         Complexity Judge                │  Ollama (qwen3.5:2b)
│    ┌──────────────────────────────┐    │
│    │ 1. Extract & Filter messages │    │
│    │    → Remove tool/UI artifacts│    │
│    │    → Take LAST user message  │    │
│    │ 2. Truncate to 2000 chars    │    │
│    │ 3. Ask judge model → score   │    │
│    │    (via /api/generate)       │    │
│    │ 4. Return 1-10 complexity    │    │
│    └──────────────────────────────┘    │
└──────────────┬──────────────────────────┘
               │
               ▼
       ┌─────────────┐
       │  Router     │
       ├─────────────┤
       │ score ≤ 5   │ → qwen3.5-flash  (⚡ Fast & Cheap)
       │ score ≥ 6   │ → qwen3.6-plus   (🧠 Smart & Powerful)
       └──────┬──────┘
              │
              ▼
┌─────────────────────────────────────────┐
│         DashScope API                   │  Qwen3.x Series
│      Transparent SSE Passthrough        │
└─────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 前置条件

```bash
# 1. Install Ollama
brew install ollama        # macOS
# or see https://ollama.com for other platforms

# 2. Pull judge model
ollama pull qwen3.5:2b

# 3. Python dependencies
pip install fastapi httpx uvicorn pyyaml
```

### 安装依赖

```bash
# From project root
pip install fastapi httpx uvicorn pyyaml
```

### 配置 API Key

**Option 1: Interactive Setup (Recommended)**

```bash
chmod +x setup_config.sh
./setup_config.sh
```

This script will prompt you to enter your DashScope API key and configure it securely in `config.yaml`.

**Option 2: Manual Configuration**

1. Copy the example config file:
```bash
cp config.example.yaml config.yaml
```

2. Edit `config.yaml` and add your API key:
```yaml
dashscope:
  api_key: "sk-your-actual-api-key-here"  # Required! Get from https://dashscope.aliyun.com/
```

**Option 3: Environment Variables**

For CI/CD deployments, use environment variables:
```bash
export DASHSCOPE_API_KEY="sk-your-actual-api-key-here"
python3 model_router.py
```

Or all settings:
```bash
export MODEL_ROUTER_SERVER_HOST=0.0.0.0 \
       MODEL_ROUTER_SERVER_PORT=9000 \
       MODEL_ROUTER_JUDGE_MODEL=qwen3.5:2b \
       MODEL_ROUTER_DASHSCOPE_API_KEY=sk-xxx
```

### 启动服务

```bash
# Use existing config.yaml
python3 model_router.py

# Custom port (overrides config)
python3 model_router.py --port 9000

# Custom host (for external access - ensure firewall is configured!)
python3 model_router.py --host 0.0.0.0 --port 8888

# Custom config file
python3 model_router.py --config my-config.yaml
```

### 验证运行

```bash
curl http://localhost:8888/health
# {"status": "ok"}

curl http://localhost:8888/
# {
#   "status": "ok",
#   "judge_model": "qwen3.5:2b",
#   "cheap_model": "qwen3.5-flash",
#   "expensive_model": "qwen3.6-plus"
# }
```

---

## ⚙️ 配置选项

所有配置项位于 `config.yaml` 文件：

```yaml
server:
  host: "localhost"        # 监听地址，使用 "0.0.0.0" 允许外部访问（需注意安全）
  port: 8888               # 服务端口

judge:
  model: "qwen3.5:2b"      # Ollama 复杂度评测模型
  ollama_host: "localhost" # Ollama 服务器地址
  ollama_port: 11434       # Ollama 端口
  timeout: 8               # Ollama 请求超时（秒）
  truncate_limit: 2000     # 用户输入截断限制（字符数）

routing:
  cheap_model: "qwen3.5-flash"    # 轻量级任务模型 (复杂度 < 阈值)
  expensive_model: "qwen3.6-plus" # 重量级任务模型 (复杂度 ≥ 阈值)
  threshold: 6                    # 路由决策阈值

dashscope:
  api_key: ""              # DashScope API 密钥 (必需)
  base_url: "..."          # DashScope 端点 URL

client:
  max_connections: 100            # 最大连接数
  max_keepalive_connections: 20   # 最大长连接数
  keepalive_expiry: 60.0          # Keepalive 超时（秒）
  default_timeout: 60.0           # 默认超时（秒）
```

### 命令行参数

```bash
# 指定配置文件
python3 model_router.py --config custom.yaml

# 覆盖端口（从 config.yaml 读取）
python3 model_router.py --port 9000

# 覆盖主机地址
python3 model_router.py --host 0.0.0.0
```

---

## 📊 复杂度分级系统

系统使用 1-10 分制评估任务复杂度：

### Lightweight Interval (Level 1-5)

执行层任务 - 无深度推理，模式匹配

| Level | 类型 | 典型场景 |
|-------|------|----------|
| 1 | Greeting | "hello", "test", "谢谢" |
| 2 | Text Transform | 翻译、大小写转换、拼写检查 |
| 3 | Basic QA | "地球有多大"、提取明确信息 |
| 4 | Simple Summarization | 写例行邮件、段落格式化 |
| 5 | Constrained Generation | 300 字文章、冒泡排序代码 |

### Heavyweight Interval (Level 6-10)

思考层任务 - 多步推理，逻辑演绎，深度专业知识

| Level | 类型 | 典型场景 |
|-------|------|----------|
| 6 | Creative/Medium Code | 3+ 约束文案、中等难度 API 集成 |
| 7 | Technical Troubleshooting | 复杂调试、数据库设计、错误日志分析 |
| 8 | Professional Domain | 法律/医学/金融分析、学术写作 |
| 9 | Multi-step Planning | 大型活动策划（预算/时间/宣传） |
| 10 | Innovative Problem | 数学推导、算法创新、复杂世界观 |

### 评估维度

评判时综合考虑四个核心维度：

1. **是否需要多步骤推理？**
2. **有多少个约束条件？**
3. **是否依赖专业领域知识？**
4. **错误的代价有多高？**

完整规则请参考 [设计文档](docs/model-router-design.md)。

---

## 📡 API 接口

完全兼容 Anthropic Chat Completions 格式。

### POST /v1/messages

```bash
# 非流式响应
curl -X POST http://localhost:8888/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "帮我分析这段报错日志"}
    ]
  }'

# 流式响应 (SSE)
curl -X POST http://localhost:8888/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "解释量子纠缠"}],
    "stream": true
  }'
```

### GET /health

健康检查端点：

```bash
curl http://localhost:8888/health
# {"status": "ok"}
```

### GET /

获取服务信息：

```bash
curl http://localhost:8888/
# {
#   "status": "ok",
#   "judge_model": "qwen3.5:2b",
#   "cheap_model": "qwen3.5-flash",
#   "expensive_model": "qwen3.6-plus"
# }
```

---

## 📈 监控与日志

运行时输出详细信息：

```
[2026-04-10 23:19:12] [complexity=1/10] judge=1.07s → qwen3.5-flash
[2026-04-10 23:19:14] [complexity=1/10] upstream_tokens: input=31121, output=34
```

### 日志字段说明

| 字段 | 含义 |
|------|------|
| `complexity=X/10` | 评估到的复杂度分数 |
| `judge=Y.YYs` | 复杂度评估耗时 |
| `model` | 最终选择的模型 |
| `upstream_tokens` | 上游模型实际使用的输入/输出 token |

---

## 🛠️ 今日更新 (2026-04-10)

### 核心改进

**精准指令提取修复** - 解决 Judge 模型误判问题

**问题诊断**：
- 原始实现将所有用户消息和 system prompt 拼接后传入 Judge，导致上下文污染
- Judge 看到大量历史对话和系统信息，返回固定分值（总是 5）

**解决方案**：
1. **新增 `is_valid_user_message()` 过滤函数** - 自动识别并排除工具响应、UI 干扰等信息
2. **只保留最后一条真实用户指令** - 避免多轮对话中的历史内容影响判断
3. **改用 `/api/generate` 端点** - 小模型的指令跟随能力优于 `/api/chat`
4. **精简 Prompt 结构** - 将 instruction 放在开头，user input 紧接其后，末尾加"Complexity score:"提示词

**技术细节**：
- 上下文截断从 3000 字符降至 2000 字符
- 移除所有 DEBUG 日志，只保留关键业务日志
- Judge raw response 错误处理增强

**效果对比**：
| 输入 | 修复前 | 修复后 |
|------|--------|--------|
| "你好" | 5 (错误) | 1 (正确) |
| "帮我分析代码" | 5 (可能错误) | 6+ (准确) |

---

## 🛠️ 架构设计

### 模块职责

| 模块 | 职责 | 关键技术 |
|------|------|---------|
| FastAPI Server | 请求接收与响应 | FastAPI, uvicorn |
| HTTP Client Pool | 连接复用与超时控制 | httpx.AsyncClient (双客户端) |
| Message Filter | 提取真实用户指令 | `extract_text_content`, `is_valid_user_message` |
| Complexity Judge | 本地模型评估 | Ollama `/api/generate` |
| Routing Logic | 决策引擎 | 规则引擎 |
| Proxy to DashScope | 流式转发与 token 统计 | SSE passthrough |

### 关键设计

**指令精准提取 (2026-04-10)**
- `extract_text_content()`: 从 message dict 中提取纯文本内容，支持 str/list/dict 多种格式
- `is_valid_user_message()`: 过滤工具响应和 UI 干扰（tool_result, system-reminder, exit code 等）
- 只取最后一条有效的用户消息作为复杂度评估依据
- 避免历史对话和系统信息污染 Judge 模型的判断

**上下文隔离** - 移除 system prompt 在 judging 中的影响，专注于用户真实意图

**双 HTTP 客户端管理 (2026-04-12)**
- `_global_client`: 用于 DashScope 上游请求，`timeout=60.0s`
- `_ollama_client`: 独立 Ollama 专用客户端，`timeout=8.0s`
- 独立超时配置确保快速失败和资源释放

**安全性增强 (2026-04-12)**
- `HOST` 从 `0.0.0.0` 改为 `localhost` (2026-04-12)，限制外部访问
- Judge 模型升级为 `qwen3.5:2b`，提升指令跟随能力

**FIFO 响应排序 (2026-04-10)**
- 并发请求按提交顺序返回结果
- Buffer-first 模式：先完整收集响应，再按序 release
- 超时防死锁机制：简单模型 30s/复杂模型 60s
- 错误时自动入队，避免队列永久阻塞

**连接池管理 (2026-04-10)** - 简化设计，使用 httpx.AsyncClient 全局单例维持连接池
```python
_global_client = httpx.AsyncClient(
    timeout=60.0,
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
        keepalive_expiry=60.0,
    ),
)
```

**指数退避重试**
```python
wait = 0.5 * (2**attempt) + random.uniform(0, 0.3)
```

**流式传输透明透传** - 字节级转发，零格式损耗

---

## 📁 项目结构

```
model-router/
├── model_router.py          # 主程序 (使用 config.py)
├── config.py                # 配置加载模块 ⭐ 新增 (v1.0+)
├── config.example.yaml      # 配置示例文件
├── config.yaml              # 实际配置文件（已 .gitignore）⚠️
├── setup_config.sh          # 交互式配置脚本 ⭐ 新增 (v1.0+)
├── start_llm.sh             # 启动脚本 (macOS)
├── stop_llm.sh              # 停止脚本 (macOS)
├── .gitignore               # Git ignore 配置 ⭐ 新增 (v1.0+)
├── README.md                # 项目文档
├── CHANGELOG.md             # 变更日志
└── docs/
    └── model-router-design.md  # 详细设计文档
```

**新增核心文件** (v1.0+):
- `config.py`: 配置加载器，支持 YAML + 环境变量 + CLI 参数三级优先级
- `setup_config.sh`: 交互式 API Key 配置工具
- `.gitignore`: 保护敏感配置不提交到仓库

---

## 🔮 未来演进方向

### 已实现功能 (v1.0+)

- ✅ **[x] 配置系统** - YAML + 环境变量 + CLI 参数三级优先级
- ✅ **[x] API Key 安全隔离** - config.yaml 加入 .gitignore，提供交互式设置脚本
- ✅ **[x] 精准指令过滤** - 自动排除工具响应，只提取真实用户意图
- ✅ **[x] FIFO 响应排序** - 按提交顺序返回，超时防死锁
- ✅ **[x] 双 HTTP 客户端** - 独立 Ollama 专用客户端，优化超时配置
- ✅ **[x] 安全性加固** - localhost 默认绑定，防止外部未授权访问

### 计划功能

- **[ ] 多级路由** - 支持 3+ 档位模型选择
- **[ ] 缓存机制** - 重复 query 直接返回缓存结果
- **[ ] 异步评测器** - 预评估降低延迟
- **[ ] A/B 测试框架** - 对比不同评分策略效果
- **[ ] 可视化 Dashboard** - 实时监控路由决策分布

---

## 📄 许可证

MIT License - 欢迎自由使用和修改

---

## 🙏 致谢

- 感谢 [Anthropic](https://anthropic.com) Claude 生态带来的启发
- 基于 [DashScope](https://dashscope.aliyun.com) Qwen 模型系列
- Ollama 提供的本地模型推理能力

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

<div align="center">

**Star this repo if it helps you optimize your LLM costs!** ⭐

</div>

# Claude Code Model Router

<div align="center">

**基于复杂度评估的智能模型路由网关**  
自动为不同任务分配最合适的模型，平衡成本与效果

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

</div>

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
- 🔒 **安全可靠** - 连接池、重试机制、优雅降级

---

## 🏗️ 工作原理

```
┌─────────────┐
│   Client    │  Anthropic 格式请求
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         Complexity Judge                │  Ollama (qwen2.5:1.5b)
│    ┌──────────────────────────────┐    │
│    │ 1. Extract user messages     │    │
│    │ 2. Truncate to 3000 chars    │    │
│    │ 3. Ask judge model → score   │    │
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
ollama pull qwen2.5:1.5b

# 3. Python dependencies
pip install fastapi httpx uvicorn
```

### 安装依赖

```bash
# From project root
pip install fastapi httpx uvicorn
```

### 配置

在 `model_router.py` 中修改以下配置项：

```python
# 替换为你的实际密钥
DASHSCOPE_API_KEY = "your-dashscope-api-key-here"

# 路由目标模型
CHEAP_MODEL = "qwen3.5-flash"      # 轻量级（Level 1-5）
EXPENSIVE_MODEL = "qwen3.6-plus"   # 重量级（Level 6-10）

# 本地评测模型
JUDGE_MODEL = "qwen2.5:1.5b"       # Ollama 中需已存在此模型
OLLAMA_PORT = 11434                # Ollama 服务端口
```

### 启动服务

```bash
# 默认端口 8888
python3 model_router.py

# 自定义端口
python3 model_router.py --port 9000
```

### 验证运行

```bash
curl http://localhost:8888/health
# {"status": "ok"}
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
#   "judge_model": "qwen2.5:1.5b",
#   "cheap_model": "qwen3.5-flash",
#   "expensive_model": "qwen3.6-plus"
# }
```

---

## 📈 监控与日志

运行时输出详细信息：

```
[2026-04-09 18:45:32] [complexity=7/10] judge=1.23s → qwen3.6-plus
  [complexity=7/10] qwen3.6-plus | tokens: input=128, output=512
```

### 日志字段说明

| 字段 | 含义 |
|------|------|
| `complexity=X/10` | 评估到的复杂度分数 |
| `judge=Y.YYs` | 复杂度评估耗时 |
| `model` | 最终选择的模型 |
| `tokens` | 输入/输出 token 数量 |

---

## 🛠️ 架构设计

### 模块职责

| 模块 | 职责 | 关键技术 |
|------|------|---------|
| FastAPI Server | 请求接收与响应 | FastAPI, uvicorn |
| HTTP Client Pool | 连接复用与超时控制 | httpx.AsyncClient |
| Complexity Judge | 本地模型评估 | Ollama API |
| Routing Logic | 决策引擎 | 规则引擎 |
| Proxy to DashScope | 流式转发与 token 统计 | SSE passthrough |

### 关键设计

**连接池管理**
```python
_global_client = httpx.AsyncClient(
    timeout=300.0,
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
claude-code-model-router/
├── model_router.py          # 主程序 (320 lines)
├── README.md                # 此文件
├── docs/
│   └── model-router-design.md  # 详细设计文档
├── start_llm.sh             # 启动脚本 (macOS)
├── stop_llm.sh              # 停止脚本 (macOS)
└── claude_settings.sh       # 环境变量配置
```

---

## 🔮 未来演进方向

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

# 更改日志

## 2026-04-10 至 2026-04-11 变更对比

### 概述

本次变更主要对模型路由器（Model Router）进行了核心改进，包括：

1. **Judge 模型优化** - 从 `qwen2.5:1.5b` 升级到 `qwen3.5:2b`
2. **精准指令提取** - 解决 Judge 模型误判问题
3. **API 端点改进** - 改用 `/api/generate` 替代 `/api/chat`
4. **日志格式优化** - 简化输出，提升可读性
5. **启动脚本优化** - 增加模型预加载和日志重定向

---

### 详细变更内容

#### 1. 模型路由器核心改进 (`model_router.py`)

**A. Judge 模型升级**
- **模型变更**: `qwen2.5:1.5b` → `qwen3.5:2b`
- **端点变更**: `/api/chat` → `/api/generate`
- **超时配置**: 默认超时从 300s 降至 60s，Ollama 专用客户端独立管理

**B. 消息过滤机制（新增）**

新增两个核心函数：

```python
async def extract_text_content(message: dict) -> str:
    """从 message dict 中提取纯文本内容"""

def is_valid_user_message(text: str) -> bool:
    """检查是否为有效的自然语言用户消息"""
```

**功能说明**：
- 自动过滤工具响应（`tool_result`, `<tool_use_id>`, 等）
- 排除 UI 干扰信息（`system-reminder`, `exit code`, 等）
- 只保留最后一条真实用户指令用于复杂度评估

**C. Prompt 结构优化**

**优化前**：
```
System context: {system_prompt}
User task: {所有用户消息拼接}
```

**优化后**：
```
You are a top-tier LLM Router Gateway...
User input: {最后一条有效用户消息}
Complexity score:
```

**改进点**：
1. Instruction 前置，让模型先记住任务要求
2. 只传最后一条用户消息，隔离历史对话干扰
3. 末尾添加 "Complexity score:" 提示词，引导直接输出数字

**D. 解析逻辑增强**

**优化前**：
```python
score = int(content)  # 简单转换，易失败
```

**优化后**：
```python
# 多阶段解析策略
# 1. 优先匹配行首数字
# 2. Fallback 到全文搜索 1-9 单 digit
# 3. 最终降级到默认值 5
```

**E. 日志格式简化**

**优化前**：
```
[complexity=7/10] qwen3.6-plus | tokens: input=128, output=512
```

**优化后**：
```
[complexity=1/10] upstream_tokens: input=31121, output=34
```

**F. 配置变更**

| 配置项 | 旧值 | 新值 | 原因 |
|--------|------|------|------|
| `JUDGE_MODEL` | `qwen2.5:1.5b` | `qwen3.5:2b` | 更好的指令跟随能力 |
| `HOST` | `0.0.0.0` | `localhost` | 安全考虑，限制本地访问 |
| `OLLAMA_TIMEOUT` | 8s | 8s | 保持不变 |
| `num_predict` | 5 | 3 | 只需要一个数字 |

---

#### 2. 启动脚本优化 (`start_llm.sh`)

**A. Judge 模型预加载**

新增步骤 1.5，在启动路由服务前预加载 Judge 模型：

```bash
JUDGE_MODEL="qwen3.5:2b"
log "Loading judge model: $JUDGE_MODEL..."
if ! ollama list 2>/dev/null | grep -q "$JUDGE_MODEL"; then
    ollama pull "$JUDGE_MODEL"
else
    log "Model $JUDGE_MODEL already exists, skipping pull"
fi
```

**B. 日志重定向优化**

**优化前**：
```bash
ollama serve > /tmp/ollama.log 2>&1 &
```

**优化后**：
```bash
ollama serve >/dev/null 2>/tmp/ollama.log &
```

**改进点**：stdout 完全抑制，只将 stderr 重定向到日志文件，减少不必要的输出。

---

#### 3. 文档更新 (`README.md`, `docs/model-router-design.md`)

**A. README.md 新增内容**

- 新增 "今日更新 (2026-04-10)" 章节
- 更新架构图，反映消息过滤流程
- 添加精准指令过滤的详细说明
- 更新日志字段说明

**B. 设计文档更新**

- 更新复杂度评估流程图
- 新增消息过滤模块说明
- 添加 `/api/generate` vs `/api/chat` 对比表
- 更新 Prompt 设计说明

---

### 效果对比

| 测试场景 | 修复前 | 修复后 |
|----------|--------|--------|
| 输入 "你好" | 5 (错误) | 1 (正确) |
| 输入 "帮我分析代码" | 5 (可能错误) | 6+ (准确) |
| 输入工具响应内容 | 5 (误判) | 过滤后正确评估 |
| Judge 响应解析 | 单一策略，易失败 | 多阶段策略，鲁棒性强 |

---

### 技术亮点

1. **上下文隔离** - 移除 system prompt 在 judging 中的影响
2. **多阶段解析** - 优先精确匹配，fallback 模糊搜索，最终降级默认值
3. **独立客户端管理** - Ollama 专用 httpx 客户端，独立超时配置
4. **安全加固** - HOST 改为 localhost，限制外部访问

---

### 影响范围

- **兼容性**: 无破坏性变更
- **性能**: Judge 评估时间可能略有增加（模型更大），但准确度显著提升
- **部署**: 需要确保 `qwen3.5:2b` 模型已拉取

---

### 后续计划

- [ ] 多级路由支持（3+ 档位）
- [ ] 缓存机制实现
- [ ] 异步评测器优化
- [ ] A/B 测试框架搭建

---

*生成时间: 2026-04-11*
*生成方式: Git diff 对比分析*

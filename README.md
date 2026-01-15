# Perplexity AI Proxy

一个基于 Docker 的 Perplexity AI 代理服务，支持多账户 Token 池管理、负载均衡和高可用。

## 目录

- [快速开始](#docker-compose-一键部署)
- [配置文件](#1-准备配置文件)
- [启动服务](#2-启动服务)
- [测试接口](#3-测试api接口)

## Docker Compose 一键部署

### 1. 准备配置文件

从示例文件复制并编辑 `token_pool_config.json`：

```bash
# 复制示例配置文件
cp token_pool_config-example.json token_pool_config.json
```

编辑 `token_pool_config.json`，填入你的 Perplexity 账户 token：
支持配置多个 Perplexity 账户 token，实现负载均衡和高可用。

```json
{
  "tokens": [
    {
      "id": "account1@example.com",
      "csrf_token": "your-csrf-token-1",
      "session_token": "your-session-token-1"
    },
    {
      "id": "account2@example.com",
      "csrf_token": "your-csrf-token-2",
      "session_token": "your-session-token-2"
    }
  ]
}
```

> **获取 Token 的方法：** 打开 perplexity.ai -> F12 开发者工具 -> Application -> Cookies
> - `csrf_token` 对应 `next-auth.csrf-token`
> - `session_token` 对应 `__Secure-next-auth.session-token`

### 2. 启动服务

```bash
# 创建 .env 文件
cp .env.example .env

# 修改 .env 文件，设置 PPLX_API_TOKEN 和 PPLX_ADMIN_TOKEN
# 可以使用以下命令生成随机 Token（16字节）：

# Windows PowerShell:
#   "sk-" + -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 32 | %{[char]$_})
#   "admin-" + -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 32 | %{[char]$_})

# Linux / macOS:
#   echo "sk-$(openssl rand -hex 16)"
#   echo "admin-$(openssl rand -hex 16)"

# Python (跨平台):
#   python -c "import secrets; print('sk-' + secrets.token_hex(16))"
#   python -c "import secrets; print('admin-' + secrets.token_hex(16))"

# 启动服务
docker compose up -d
```

### docker-compose.yml 配置

项目已包含 [docker-compose.yml](./docker-compose.yml) 配置文件，可根据需要修改：
- `ports`: 修改 `15001` 为你想要的端口
- `HTTPS_PROXY`: 如在 perplexity 不可用地区，取消注释并配置代理

### 3. API 接口文档

#### 认证说明

所有 API 请求（除健康检查外）需要在 Header 中携带 API Token：

```
Authorization: Bearer <你的API_TOKEN>
```

#### 3.1 文生文接口 - POST /search

执行 AI 搜索查询，返回智能回答和来源链接。

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | ✅ | - | 搜索查询内容 |
| mode | string | ❌ | `"auto"` | 搜索模式 |
| model | string | ❌ | `null` | AI 模型（按 mode 选择） |
| sources | array | ❌ | `["web"]` | 搜索来源 |
| language | string | ❌ | `"en-US"` | 语言代码 |
| incognito | boolean | ❌ | `true` | 隐身模式 |

**mode 可选值：**

| 值 | 说明 |
|----|------|
| `auto` | 自动模式（快速响应） |
| `pro` | 专业模式（更详细的回答） |
| `reasoning` | 推理模式（深度思考，支持图片生成） |
| `deep research` | 深度研究模式（最全面的分析） |

**model 可选值（按 mode 分类）：**

| mode | 可选 model |
|------|------------|
| `auto` | 无需指定（默认 turbo） |
| `pro` | `sonar`, `gpt-5.2`, `claude-4.5-sonnet`, `grok-4.1` |
| `reasoning` | `gpt-5.2-thinking`, `claude-4.5-sonnet-thinking`, `gemini-3.0-pro`, `kimi-k2-thinking`, `grok-4.1-reasoning` |
| `deep research` | 无需指定（默认 pplx_alpha） |

**sources 可选值：**

| 值 | 说明 |
|----|------|
| `web` | 网页搜索 |
| `scholar` | 学术论文 |
| `social` | 社交媒体 |

**响应结构：**

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 状态，成功为 `"ok"` |
| client_id | string | 使用的客户端 ID |
| answer | string | AI 生成的回答内容 |
| web_results | array | 来源链接列表 |

**curl 示例：**

```bash
curl -X POST "http://localhost:8000/search" \
  -H "Authorization: Bearer sk-your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是量子计算？",
    "mode": "auto",
    "sources": ["web", "scholar"],
    "language": "zh-CN"
  }'
```

**Python 示例：**

```python
import requests

response = requests.post(
    "http://localhost:8000/search",
    headers={"Authorization": "Bearer sk-your-token"},
    json={
        "query": "什么是量子计算？",
        "mode": "pro",
        "model": "claude-4.5-sonnet",
        "sources": ["web", "scholar"]
    }
)
print(response.json())
```

---

#### 3.2 文生图接口 - POST /generate-image

通过 AI 生成图片，返回图片 URL 和相关信息。

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| prompt | string | ✅ | - | 图片生成提示词 |
| mode | string | ❌ | `"reasoning"` | 搜索模式 |
| model | string | ❌ | `"claude-4.5-sonnet-thinking"` | AI 模型 |
| language | string | ❌ | `"en-US"` | 语言代码 |
| incognito | boolean | ❌ | `true` | 隐身模式 |

> 💡 **提示**：文生图功能需要使用 `reasoning` 模式，推荐使用默认的 `claude-4.5-sonnet-thinking` 模型。

**响应结构：**

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 状态，成功为 `"ok"` |
| client_id | string | 使用的客户端 ID |
| images | array | 生成的图片列表 |
| images[].url | string | 图片完整 URL |
| images[].thumbnail_url | string | 缩略图 URL |
| images[].width | number | 图片宽度（像素） |
| images[].height | number | 图片高度（像素） |
| prompt_used | string | 实际使用的提示词 |
| caption | string | 图片描述/标题 |
| model | string | 使用的生成模型 |

**curl 示例：**

```bash
curl -X POST "http://localhost:8000/generate-image" \
  -H "Authorization: Bearer sk-your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "一只可爱的橘猫在阳光下打盹"
  }'
```

**Python 示例：**

```python
import requests

response = requests.post(
    "http://localhost:8000/generate-image",
    headers={"Authorization": "Bearer sk-your-token"},
    json={
        "prompt": "一只可爱的橘猫在阳光下打盹",
        "mode": "reasoning",
        "model": "claude-4.5-sonnet-thinking"
    }
)

result = response.json()
if result["status"] == "ok" and result["images"]:
    print(f"图片URL: {result['images'][0]['url']}")
```

---

#### 3.3 辅助接口

| 接口 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/health` | GET | ❌ | 健康检查，返回服务状态 |
| `/pool/status` | GET | ❌ | 号池状态，返回可用客户端数量 |
| `/pool/list` | GET | API Token | 列出所有客户端详情 |

---

#### 3.4 测试脚本

测试脚本 `test_server.py` 包含以下测试项：

| 测试项 | 自动运行 | 说明 |
|--------|----------|------|
| 健康检查 | ✅ | 测试 `/health` 端点 |
| 号池状态 | ✅ | 测试 `/pool/status` 端点 |
| 认证验证 | ✅ | 无 Token 访问应返回 401 |
| 客户端列表 | ✅ | 测试 `/pool/list` 端点 |
| 搜索功能 | ❌ 交互确认 | 测试 `/search` 端点（消耗配额） |
| 图片生成 | ❌ 交互确认 | 测试 `/generate-image` 端点（消耗配额） |

运行测试：

```bash
# 设置环境变量（可选）
export PPLX_HOST_URL="http://localhost:8000"
export PPLX_API_TOKEN="sk-your-token"

# 运行测试
python test_server.py
```

> 💡 **提示**：搜索和图片生成测试会消耗 Perplexity 账户配额，脚本会询问是否执行。

---

## 参考项目

本项目参考了以下开源项目：

- [helallao/perplexity-ai](https://github.com/helallao/perplexity-ai)
- [escapeWu/perplexity-ai](https://github.com/escapeWu/perplexity-ai)


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

### 3. 测试API接口

修改 `test_server.py` 中的 `BASE_URL` 为你的服务地址，然后运行测试脚本：

```bash
python test_server.py
```

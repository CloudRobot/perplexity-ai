# NAS 部署指南

本指南将帮助你将 Perplexity API Proxy 部署到你的 NAS（如 Synology, QNAP 或运行 Linux 的服务器）上。

## 1. 准备工作

### 1.1 推送代码到 GitHub
你需要将此项目推送到你自己的 GitHub 仓库。GitHub Actions 会自动构建 Docker 镜像并发布到 GitHub Container Registry (GHCR)。

1. 在 GitHub 上创建一个新仓库（例如 `perplexity-proxy`）。
2. 在本地执行以下命令推送代码：
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/你的用户名/perplexity-proxy.git
   git push -u origin main
   ```
3. 推送成功后，点击 GitHub 仓库的 **Actions** 标签页，你应该能看到 `Docker Build and Publish` 正在运行。等待它显示绿色对号（成功）。

### 1.2 获取镜像地址
构建成功后，你的镜像地址通常是：
`ghcr.io/你的用户名/perplexity-proxy:latest`
*(注意：用户名和仓库名可能需要转换为小写)*

## 2. 在 NAS 上部署

### 2.1 准备文件
在你的 NAS 上创建一个文件夹（例如 `/docker/perplexity-proxy`），并上传以下两个文件：

1. **`docker-compose.yml`** (见下文)
2. **`token_pool_config.json`** (把 `token_pool_config.example.json` 重命名并填入真实 Token)

### 2.2 创建 `docker-compose.yml`
在 NAS 文件夹中创建 `docker-compose.yml`，内容如下：

```yaml
version: "3.8"

services:
  perplexity-proxy:
    # 替换为你的 GitHub 镜像地址
    image: ghcr.io/你的用户名/perplexity-proxy:latest
    container_name: perplexity-proxy
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - PPLX_API_TOKEN=sk-123456  # 设置你的 API 访问密码
      - PPLX_ADMIN_TOKEN=admin-secret  # 设置管理员密码
    volumes:
      # 挂载配置文件
      - ./token_pool_config.json:/app/token_pool_config.json:ro
```

### 2.3 运行
在 NAS 的终端（SSH）中进入该目录并运行：

```bash
# 登录 ghcr.io (如果你的仓库是私有的)
docker login ghcr.io -u 你的GitHub用户名 -p 你的GitHub_Token

# 启动服务
docker-compose up -d
```

如果是 Synology 群晖，你也可以直接在 **Container Manager (Docker)** 套件中：
1. **映像** -> **新增** -> **来自 URL 添加** -> 输入 `ghcr.io/你的用户名/perplexity-proxy:latest`。
2. 下载完成后启动，配置端口映射 (8000:8000) 和存储卷挂载 (`docker/perplexity-proxy/token_pool_config.json` -> `/app/token_pool_config.json`)。
3. 在“环境”中添加变量 `PPLX_API_TOKEN` 等。

## 3. 验证
访问 `http://NAS_IP:8000/health`，如果返回 JSON 数据，说明部署成功。

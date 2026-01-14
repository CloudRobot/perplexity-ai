"""
FastAPI-based HTTP server for Perplexity API with load balancing.
Provides RESTful endpoints for search and pool management.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 加载 .env 文件
load_dotenv()

from .client_pool import ClientPool

# ==================== 配置 ====================
CONFIG = {
    "host": os.getenv("PPLX_HOST", "0.0.0.0"),
    "port": int(os.getenv("PPLX_PORT", "8000")),
    "api_token": os.getenv("PPLX_API_TOKEN", "sk-123456"),
    "admin_token": os.getenv("PPLX_ADMIN_TOKEN", ""),
}

# ==================== FastAPI App ====================
app = FastAPI(
    title="Perplexity API Proxy",
    description="HTTP API with load balancing for Perplexity AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 全局 ClientPool ====================
_pool: Optional[ClientPool] = None


def get_pool() -> ClientPool:
    """Get or create the singleton ClientPool instance."""
    global _pool
    if _pool is None:
        config_path = os.getenv("PPLX_TOKEN_POOL_CONFIG", "token_pool_config.json")
        _pool = ClientPool(config_path if os.path.exists(config_path) else None)
    return _pool


def _extract_clean_result(response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the final answer and source links from the search response."""
    result = {}

    # 提取最终答案
    if "answer" in response:
        result["answer"] = response["answer"]
    else:
        result["answer"] = ""

    # 提取来源链接
    sources = []

    # 方法1: 从 text 字段的 SEARCH_RESULTS 步骤中提取 web_results
    if "text" in response and isinstance(response["text"], list):
        for step in response["text"]:
            if isinstance(step, dict) and step.get("step_type") == "SEARCH_RESULTS":
                content = step.get("content", {})
                web_results = content.get("web_results", [])
                for web_result in web_results:
                    if isinstance(web_result, dict) and "url" in web_result:
                        source = {"url": web_result["url"]}
                        if "name" in web_result:
                            source["title"] = web_result["name"]
                        if "snippet" in web_result:
                            source["snippet"] = web_result["snippet"]
                        sources.append(source)

    # 方法2: 备用 - 从 chunks 字段提取（如果 chunks 包含 URL）
    if not sources and "chunks" in response and isinstance(response["chunks"], list):
        for chunk in response["chunks"]:
            if isinstance(chunk, dict):
                source = {}
                if "url" in chunk:
                    source["url"] = chunk["url"]
                if "title" in chunk:
                    source["title"] = chunk["title"]
                if "name" in chunk and "title" not in source:
                    source["title"] = chunk["name"]
                if "url" in source:
                    sources.append(source)

    result["sources"] = sources

    return result


# ==================== 认证依赖 ====================
async def verify_api_token(authorization: str = Header(None)):
    """Verify API token from Authorization header."""
    expected = f"Bearer {CONFIG['api_token']}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


async def verify_admin_token(x_admin_token: str = Header(None)):
    """Verify admin token from X-Admin-Token header."""
    if not CONFIG["admin_token"]:
        raise HTTPException(status_code=403, detail="Admin token not configured")
    if x_admin_token != CONFIG["admin_token"]:
        raise HTTPException(status_code=401, detail="Invalid admin token")


# ==================== 请求/响应模型 ====================
class SearchRequest(BaseModel):
    """Search request model."""

    query: str
    mode: str = "auto"
    model: Optional[str] = None
    sources: List[str] = ["web"]
    language: str = ("en-US",)
    incognito: bool = True


class ClientRequest(BaseModel):
    """Client management request model."""

    id: str
    csrf_token: Optional[str] = None
    session_token: Optional[str] = None


# ==================== API 端点 ====================
@app.get("/health")
async def health_check():
    """健康检查（无需认证）"""
    pool = get_pool()
    status = pool.get_status()
    return {
        "status": "healthy",
        "service": "perplexity-proxy",
        "pool": {
            "total": status["total"],
            "available": status["available"],
            "mode": status["mode"],
        },
    }


@app.get("/pool/status")
async def pool_status():
    """号池状态（无需认证）"""
    return get_pool().get_status()


@app.post("/search", dependencies=[Depends(verify_api_token)])
async def search(request: SearchRequest):
    """
    执行搜索查询（需要 API Token）

    使用负载均衡从池中选择可用客户端
    """
    pool = get_pool()
    client_id, client = pool.get_client()

    if client is None:
        status = pool.get_status()
        raise HTTPException(
            status_code=503,
            detail={
                "message": "No available clients",
                "pool_status": status,
            },
        )

    try:
        response = client.search(
            query=request.query,
            mode=request.mode,
            model=request.model,
            sources=request.sources,
            language=request.language,
            stream=False,
            incognito=request.incognito,
        )
        pool.mark_success(client_id)

        # # 保存响应到 JSON 文件以便分析
        # responses_dir = os.path.join(os.path.dirname(__file__), "..", "responses")
        # os.makedirs(responses_dir, exist_ok=True)
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # filename = os.path.join(responses_dir, f"response_{timestamp}.json")
        # with open(filename, "w", encoding="utf-8") as f:
        #     json.dump(response, f, ensure_ascii=False, indent=2)
        # print(f"Response saved to: {filename}")

        # 使用 _extract_clean_result 提取答案和来源链接
        clean_result = _extract_clean_result(response)

        return {
            "status": "ok",
            "client_id": client_id,
            "answer": clean_result["answer"],
            "web_results": clean_result["sources"],
        }
    except Exception as e:
        pool.mark_failure(client_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pool/list", dependencies=[Depends(verify_api_token)])
async def list_clients():
    """列出所有客户端（需要 API Token）"""
    return get_pool().get_status()


@app.post("/pool/add", dependencies=[Depends(verify_admin_token)])
async def add_client(request: ClientRequest):
    """添加客户端（需要 Admin Token）"""
    if not request.csrf_token or not request.session_token:
        raise HTTPException(status_code=400, detail="csrf_token and session_token are required")
    return get_pool().add_client(request.id, request.csrf_token, request.session_token)


@app.post("/pool/remove", dependencies=[Depends(verify_admin_token)])
async def remove_client(request: ClientRequest):
    """移除客户端（需要 Admin Token）"""
    return get_pool().remove_client(request.id)


@app.post("/pool/enable", dependencies=[Depends(verify_admin_token)])
async def enable_client(request: ClientRequest):
    """启用客户端（需要 Admin Token）"""
    return get_pool().enable_client(request.id)


@app.post("/pool/disable", dependencies=[Depends(verify_admin_token)])
async def disable_client(request: ClientRequest):
    """禁用客户端（需要 Admin Token）"""
    return get_pool().disable_client(request.id)


@app.post("/pool/reset", dependencies=[Depends(verify_admin_token)])
async def reset_client(request: ClientRequest):
    """重置客户端状态（需要 Admin Token）"""
    return get_pool().reset_client(request.id)


# ==================== 入口点 ====================
def main():
    """Run the HTTP server."""
    import uvicorn

    print(f"Starting Perplexity API Proxy on {CONFIG['host']}:{CONFIG['port']}")
    uvicorn.run(app, host=CONFIG["host"], port=CONFIG["port"])


if __name__ == "__main__":
    main()

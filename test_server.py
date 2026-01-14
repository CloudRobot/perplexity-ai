"""
测试脚本 - 验证 Perplexity API Proxy 服务
"""

import requests
import json

import os

# ==================== 配置 ====================
BASE_URL = os.getenv("PPLX_HOST_URL", "http://localhost:8000")
# 从环境变量获取 Token，避免硬编码泄露
API_TOKEN = os.getenv("PPLX_API_TOKEN", "sk-123456") 
#ADMIN_TOKEN = os.getenv("PPLX_ADMIN_TOKEN", "admin-secret-token")


def print_result(name: str, response: requests.Response):
    """打印测试结果"""
    status = "✅" if response.ok else "❌"
    print(f"\n{status} [{response.status_code}] {name}")
    try:
        data = response.json()
        # 打印完整的格式化 JSON
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        print("\nanswer:")
        print(data.get("answer", "N/A"))
        
        print("\nweb_results:")
        # 再次格式化 web_results 以便阅读
        print(json.dumps(data.get("web_results", []), indent=2, ensure_ascii=False))
        print(len(data.get("web_results", [])))
    except Exception as e:
        print(f"Error parsing response: {e}")
        print(response.text[:200])


def test_health():
    """测试健康检查端点"""
    print("\n" + "="*50)
    print("1. 测试健康检查 /health")
    print("="*50)
    
    resp = requests.get(f"{BASE_URL}/health")
    print_result("Health Check", resp)
    return resp.ok


def test_pool_status():
    """测试号池状态端点"""
    print("\n" + "="*50)
    print("2. 测试号池状态 /pool/status")
    print("="*50)
    
    resp = requests.get(f"{BASE_URL}/pool/status")
    print_result("Pool Status", resp)
    return resp.ok


def test_search():
    """测试搜索端点"""
    print("\n" + "="*50)
    print("3. 测试搜索 /search")
    print("="*50)
    
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    data = {
        "query": "今天的天气如何，今天是星期几，明天是星期几?",
        "mode": "reasoning",
        "model": "claude-4.5-sonnet-thinking",
        "sources": ["web"],
        "language": "zh-CN"
    }
    
    resp = requests.post(f"{BASE_URL}/search", json=data, headers=headers)
    print_result("Search", resp)
    return resp.ok


def test_search_without_token():
    """测试无 Token 访问"""
    print("\n" + "="*50)
    print("4. 测试无 Token 访问 (应该返回 401)")
    print("="*50)
    
    data = {"query": "test"}
    resp = requests.post(f"{BASE_URL}/search", json=data)
    print_result("Search without token", resp)
    return resp.status_code == 401


def test_pool_list():
    """测试列出客户端"""
    print("\n" + "="*50)
    print("5. 测试列出客户端 /pool/list")
    print("="*50)
    
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    resp = requests.get(f"{BASE_URL}/pool/list", headers=headers)
    print_result("Pool List", resp)
    return resp.ok


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("       Perplexity API Proxy 测试脚本")
    print("="*60)
    print(f"服务地址: {BASE_URL}")
    print(f"API Token: {API_TOKEN[:10]}...")
    
    results = []
    
    try:
        # 基础测试
        #results.append(("健康检查", test_health()))
        #results.append(("号池状态", test_pool_status()))
        #results.append(("无Token访问", test_search_without_token()))
        #results.append(("列出客户端", test_pool_list()))
        
        # 可选：搜索测试（需要有效的 Token 配置）
        # print("\n是否测试实际搜索功能? (需要有效的 Perplexity Token)")
        # user_input = input("输入 y 继续，其他键跳过: ").strip().lower()
        # if user_input == 'y':
        #     results.append(("搜索功能", test_search()))
        test_search()
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到服务器，请确保服务已启动:")
        print(f"   python -m perplexity.http_server")
        return
    
    # 打印总结
    print("\n" + "="*60)
    print("                    测试结果总结")
    print("="*60)
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
    
    passed_count = sum(1 for _, p in results if p)
    print(f"\n总计: {passed_count}/{len(results)} 通过")


if __name__ == "__main__":
    main()

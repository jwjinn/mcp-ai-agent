# =================================================================
# [설정] 서버 및 모델 주소 관리
# =================================================================

# 1. MCP 서버 목록
MCP_SERVERS = [
    {"name": "k8s",     "url": "http://127.0.0.1:30184/sse"},
    {"name": "vlogs",   "url": "http://127.0.0.1:31916/sse"},
    {"name": "vm",      "url": "http://127.0.0.1:30618/sse"},
    {"name": "vtraces", "url": "http://127.0.0.1:30606/sse"},
]

# 2. 모델 설정 (Dual Model)

# A. Instruct Model (Router & Executor & Simple Chat)
# 빠르고 도구 사용에 능숙한 모델
INSTRUCT_CONFIG = {
    "base_url": "http://127.0.0.1:80/v1",
    "model_name": "qwen-custom",
    "api_key": "EMPTY",
    "default_headers": {"Host": "qwen-instruct.example.com"},
    "temperature": 0
}

# B. Thinking Model (Planner & Synthesizer)
# 깊은 추론과 복잡한 문제 해결에 능숙한 모델
THINKING_CONFIG = {
    "base_url": "http://127.0.0.1:80/v1",
    "model_name": "qwen-thinking", # 유저가 제공한 모델명
    "api_key": "EMPTY",
    # 유저가 제공한 Host 헤더
    "default_headers": {"Host": "qwen-thinking.example.com"},
    "temperature": 0
}

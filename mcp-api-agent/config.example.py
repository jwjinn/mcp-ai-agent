import os
import json
import logging
import sys

# =================================================================
# 1. 로깅 설정
# =================================================================
# K8s ConfigMap이나 환경변수에서 LOG_LEVEL을 읽어옵니다. (기본값: INFO)
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

# 
# 기본 로거 포맷 설정 (K8s 스트림에 맞게 표준 출력 사용)
logging.basicConfig(
    stream=sys.stdout,
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_agent")

# =================================================================
# 2. 서버 및 모델 주소 관리 (ConfigMap 동적 로드)
# =================================================================

# K8s ConfigMap을 통해 마운트될 JSON 설정 파일 경로
CONFIG_FILE_PATH = os.getenv("CONFIG_FILE_PATH", "config.json")

# K8s 마운트 경로에 파일이 없을 경우를 대비한 기본값들
DEFAULT_MCP_SERVERS = [
    {"name": "k8s",     "url": "http://127.0.0.1:30184/sse"},
    {"name": "vlogs",   "url": "http://127.0.0.1:31916/sse"},
    {"name": "vm",      "url": "http://127.0.0.1:30618/sse"},
    {"name": "vtraces", "url": "http://127.0.0.1:30606/sse"},
]

DEFAULT_INSTRUCT_CONFIG = {
    "base_url": "http://127.0.0.1:80/v1",
    "model_name": "qwen-custom",
    "api_key": "EMPTY",
    "default_headers": {"Host": "qwen-instruct.example.com"},
    "temperature": 0
}

DEFAULT_THINKING_CONFIG = {
    "base_url": "http://127.0.0.1:80/v1",
    "model_name": "qwen-thinking",
    "api_key": "EMPTY",
    "default_headers": {"Host": "qwen-thinking.example.com"},
    "temperature": 0
}

# 설정 변수 할당
MCP_SERVERS = DEFAULT_MCP_SERVERS
INSTRUCT_CONFIG = DEFAULT_INSTRUCT_CONFIG
THINKING_CONFIG = DEFAULT_THINKING_CONFIG

# 파일에서 식별할 경우 오버라이드
if os.path.exists(CONFIG_FILE_PATH):
    logger.info(f"Loading configuration from {CONFIG_FILE_PATH}")
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # JSON 파일 내부에 키가 존재하면 덮어쓰기
            if "MCP_SERVERS" in data:
                MCP_SERVERS = data["MCP_SERVERS"]
            if "INSTRUCT_CONFIG" in data:
                INSTRUCT_CONFIG = data["INSTRUCT_CONFIG"]
            if "THINKING_CONFIG" in data:
                THINKING_CONFIG = data["THINKING_CONFIG"]
                
    except Exception as e:
        logger.error(f"Failed to load config from {CONFIG_FILE_PATH}: {e}. Using defaults.")
else:
    logger.debug(f"Config file not found at {CONFIG_FILE_PATH}, using default configurations.")

logger.debug(f"Config Loaded - LLM Base URL: {INSTRUCT_CONFIG.get('base_url')}")

# =================================================================
# 3. 브로드캐스팅용 Async Queue (진행방향 상태 공유 API용)
# =================================================================
import asyncio
stream_queue = asyncio.Queue()

import os
import json
import logging
import sys
from typing import Optional

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


def _env_int(name: str, default: Optional[int] = None) -> Optional[int]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning(f"Invalid integer for {name}: {value}. Using default={default}")
        return default


def _env_float(name: str, default: Optional[float] = None) -> Optional[float]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning(f"Invalid float for {name}: {value}. Using default={default}")
        return default


def _env_str(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value

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
    "temperature": 0,
    "context_window": None,
    "max_input_tokens": None,
    "max_output_tokens": None,
}

DEFAULT_THINKING_CONFIG = {
    "base_url": "http://127.0.0.1:80/v1",
    "model_name": "qwen-thinking",
    "api_key": "EMPTY",
    "default_headers": {"Host": "qwen-thinking.example.com"},
    "temperature": 0,
    "context_window": 32768,
    "max_input_tokens": 28672,
    "max_output_tokens": 4096,
}

DEFAULT_RUNTIME_LIMITS = {
    "router_keep_last": 5,
    "simple_keep_last": 15,
    "max_ai_steps": 10,
    "worker_summary_quota": 2000,
    "max_total_context": 10000,
    "mcp_tool_max_output_chars": 10000,
    "worker_raw_result_max_chars": 8000,
}

# 설정 변수 할당
MCP_SERVERS = DEFAULT_MCP_SERVERS
INSTRUCT_CONFIG = dict(DEFAULT_INSTRUCT_CONFIG)
THINKING_CONFIG = dict(DEFAULT_THINKING_CONFIG)
RUNTIME_LIMITS = dict(DEFAULT_RUNTIME_LIMITS)

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
                INSTRUCT_CONFIG.update(data["INSTRUCT_CONFIG"])
            if "THINKING_CONFIG" in data:
                THINKING_CONFIG.update(data["THINKING_CONFIG"])
            if "RUNTIME_LIMITS" in data:
                RUNTIME_LIMITS.update(data["RUNTIME_LIMITS"])
                
    except Exception as e:
        logger.error(f"Failed to load config from {CONFIG_FILE_PATH}: {e}. Using defaults.")
else:
    logger.debug(f"Config file not found at {CONFIG_FILE_PATH}, using default configurations.")

# Environment variables override JSON/file defaults.
INSTRUCT_CONFIG["base_url"] = _env_str("INSTRUCT_BASE_URL", INSTRUCT_CONFIG["base_url"])
INSTRUCT_CONFIG["model_name"] = _env_str("INSTRUCT_MODEL_NAME", INSTRUCT_CONFIG["model_name"])
INSTRUCT_CONFIG["api_key"] = _env_str("INSTRUCT_API_KEY", INSTRUCT_CONFIG["api_key"])
INSTRUCT_CONFIG["temperature"] = _env_float("INSTRUCT_TEMPERATURE", INSTRUCT_CONFIG["temperature"])
INSTRUCT_CONFIG["context_window"] = _env_int("INSTRUCT_MODEL_CONTEXT_WINDOW", INSTRUCT_CONFIG.get("context_window"))
INSTRUCT_CONFIG["max_input_tokens"] = _env_int("INSTRUCT_MODEL_MAX_INPUT_TOKENS", INSTRUCT_CONFIG.get("max_input_tokens"))
INSTRUCT_CONFIG["max_output_tokens"] = _env_int("INSTRUCT_MODEL_MAX_OUTPUT_TOKENS", INSTRUCT_CONFIG.get("max_output_tokens"))

instruct_host = _env_str("INSTRUCT_HOST_HEADER")
if instruct_host:
    INSTRUCT_CONFIG["default_headers"] = {"Host": instruct_host}

THINKING_CONFIG["base_url"] = _env_str("THINKING_BASE_URL", THINKING_CONFIG["base_url"])
THINKING_CONFIG["model_name"] = _env_str("THINKING_MODEL_NAME", THINKING_CONFIG["model_name"])
THINKING_CONFIG["api_key"] = _env_str("THINKING_API_KEY", THINKING_CONFIG["api_key"])
THINKING_CONFIG["temperature"] = _env_float("THINKING_TEMPERATURE", THINKING_CONFIG["temperature"])
THINKING_CONFIG["context_window"] = _env_int("THINKING_MODEL_CONTEXT_WINDOW", THINKING_CONFIG.get("context_window"))
THINKING_CONFIG["max_input_tokens"] = _env_int("THINKING_MODEL_MAX_INPUT_TOKENS", THINKING_CONFIG.get("max_input_tokens"))
THINKING_CONFIG["max_output_tokens"] = _env_int("THINKING_MODEL_MAX_OUTPUT_TOKENS", THINKING_CONFIG.get("max_output_tokens"))

thinking_host = _env_str("THINKING_HOST_HEADER")
if thinking_host:
    THINKING_CONFIG["default_headers"] = {"Host": thinking_host}

RUNTIME_LIMITS["router_keep_last"] = _env_int("ROUTER_KEEP_LAST", RUNTIME_LIMITS["router_keep_last"])
RUNTIME_LIMITS["simple_keep_last"] = _env_int("SIMPLE_KEEP_LAST", RUNTIME_LIMITS["simple_keep_last"])
RUNTIME_LIMITS["max_ai_steps"] = _env_int("MAX_AI_STEPS", RUNTIME_LIMITS["max_ai_steps"])
RUNTIME_LIMITS["worker_summary_quota"] = _env_int("WORKER_SUMMARY_QUOTA", RUNTIME_LIMITS["worker_summary_quota"])
RUNTIME_LIMITS["max_total_context"] = _env_int("MAX_TOTAL_CONTEXT", RUNTIME_LIMITS["max_total_context"])
RUNTIME_LIMITS["mcp_tool_max_output_chars"] = _env_int("MCP_TOOL_MAX_OUTPUT_CHARS", RUNTIME_LIMITS["mcp_tool_max_output_chars"])
RUNTIME_LIMITS["worker_raw_result_max_chars"] = _env_int("WORKER_RAW_RESULT_MAX_CHARS", RUNTIME_LIMITS["worker_raw_result_max_chars"])

logger.debug(f"Config Loaded - LLM Base URL: {INSTRUCT_CONFIG.get('base_url')}")
logger.debug(
    "Runtime limits loaded - "
    f"router_keep_last={RUNTIME_LIMITS['router_keep_last']}, "
    f"simple_keep_last={RUNTIME_LIMITS['simple_keep_last']}, "
    f"max_ai_steps={RUNTIME_LIMITS['max_ai_steps']}, "
    f"worker_summary_quota={RUNTIME_LIMITS['worker_summary_quota']}, "
    f"max_total_context={RUNTIME_LIMITS['max_total_context']}, "
    f"mcp_tool_max_output_chars={RUNTIME_LIMITS['mcp_tool_max_output_chars']}, "
    f"worker_raw_result_max_chars={RUNTIME_LIMITS['worker_raw_result_max_chars']}"
)

# =================================================================
# 3. 브로드캐스팅용 Async Queue (진행방향 상태 공유 API용)
# =================================================================
import asyncio
stream_queue = asyncio.Queue()

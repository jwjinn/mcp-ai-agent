from typing import TypedDict, Annotated, List, Literal, Dict
import json
import asyncio
import math

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from datetime import datetime, timezone

from config import INSTRUCT_CONFIG, THINKING_CONFIG, RUNTIME_LIMITS, logger

# =================================================================
# 1. 상태(State) 정의
# =================================================================
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    # 라우팅 결과 ("simple" 또는 "complex")
    mode: str 
    # [Orchestrator] 각 Worker에게 내릴 지시사항 (Key: worker_name, Value: instruction)
    worker_plans: Dict[str, str]
    # [Workers] 각 Worker의 실행 결과 리스트
    worker_results: List[str]
    
# =================================================================
# 2. 모델 초기화
# =================================================================
from langchain_core.callbacks import BaseCallbackHandler
import sys
import tiktoken

# Thinking 과정을 실시간으로 보여주기 위한 콜백
from langchain_core.callbacks import AsyncCallbackHandler

class AsyncThinkingStreamCallback(AsyncCallbackHandler):
    def __init__(self, target_queue=None):
        self.in_thinking = True # 기본적으로 생각 중이라고 가정 (첫 출력부터 숨김)
        self.buffer = "" # 태그 감지를 위한 버퍼
        self.target_queue = target_queue

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        import sys
        if not self.in_thinking:
            # 이미 생각 끝났으면 바로 출력
            sys.stdout.write(token)
            sys.stdout.flush()
            if self.target_queue:
                await self.target_queue.put(f"TOKEN:{token}")
            return

        # 태그 감지를 위해 버퍼에 추가
        self.buffer += token
        
        # </think> 감지
        if "</think>" in self.buffer:
            self.in_thinking = False
            # </think> 뒷부분을 찾아서 출력
            parts = self.buffer.split("</think>")
            if len(parts) > 1:
                # 뒷부분만 출력 (앞부분은 버림)
                chunk = parts[-1]
                sys.stdout.write(chunk)
                sys.stdout.flush()
                if self.target_queue:
                    await self.target_queue.put(f"TOKEN:{chunk}")
            self.buffer = "" # 버퍼 초기화

def get_instruct_model():
    kwargs = {
        "model": INSTRUCT_CONFIG["model_name"],
        "api_key": INSTRUCT_CONFIG["api_key"],
        "base_url": INSTRUCT_CONFIG["base_url"],
        "default_headers": INSTRUCT_CONFIG["default_headers"],
        "temperature": INSTRUCT_CONFIG["temperature"],
        "request_timeout": 300,
        "max_retries": 3,
    }
    max_output_tokens = INSTRUCT_CONFIG.get("max_output_tokens")
    if max_output_tokens is not None:
        kwargs["max_tokens"] = max_output_tokens

    return ChatOpenAI(
        **kwargs
    )

def get_thinking_model(stream_prefix=""):
    """
    Thinking 모델은 시간이 오래 걸리므로 타임아웃을 길게 잡고,
    실시간으로 생각하는 과정을 보여주기 위해 스트리밍을 켭니다.
    """
    callbacks = []
    if stream_prefix:
        logger.debug(f"{stream_prefix} ") # 시작할 때
        from config import stream_queue
        callbacks = [AsyncThinkingStreamCallback(target_queue=stream_queue)]

    kwargs = {
        "model": THINKING_CONFIG["model_name"],
        "api_key": THINKING_CONFIG["api_key"],
        "base_url": THINKING_CONFIG["base_url"],
        "default_headers": THINKING_CONFIG["default_headers"],
        "temperature": THINKING_CONFIG["temperature"],
        "request_timeout": 3600,
        "streaming": True,
        "callbacks": callbacks,
        "max_retries": 3,
    }
    max_output_tokens = THINKING_CONFIG.get("max_output_tokens")
    if max_output_tokens is not None:
        kwargs["max_tokens"] = max_output_tokens

    return ChatOpenAI(**kwargs)

# =================================================================
# 3. 노드(Node) 정의
# =================================================================

# [최적화] Smart Sliding Window
# 시스템 메시지(0번)는 무조건 유지하고, 최근 N개 대화만 남깁니다.
def trim_messages_history(messages: list, keep_last: int = 15) -> list:
    if len(messages) <= keep_last + 1:
        return messages
    
    # 0번(System) + 최근 keep_last개
    # (주의: LangChain message 객체들이므로 슬라이싱 가능)
    return [messages[0]] + messages[-keep_last:]

# [최적화] 중복 호출 방지 (Deduplication)
# 이전 대화 내역에 동일한 도구+인자가 있는지 검사합니다.
def check_and_filter_duplicate_tools(history_messages: list, new_msg: BaseMessage) -> BaseMessage:
    if not new_msg.tool_calls:
        return new_msg
    
    # [변경] Consecutive(연속) 중복만 차단하도록 완화
    # 사용자가 "아까 그거 다시 보여줘" 할 수도 있고, 다른 맥락에서 다시 쓸 수도 있음.
    # 하지만 "무한 루프"는 보통 바로 직전 걸 계속 부르는 현상이므로, 직전 메시지만 확인.
    
    last_ai_msg = None
    # 뒤에서부터 찾아서 가장 최신의 AI 메시지(Tool Call이 있는)를 찾음
    for msg in reversed(history_messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            last_ai_msg = msg
            break
    
    unique_tool_calls = []
    for new_tc in new_msg.tool_calls:
        is_dup = False
        
        # 직전 AI 메시지와 비교
        if last_ai_msg and last_ai_msg.tool_calls:
            for old_tc in last_ai_msg.tool_calls:
                # 이름과 인자가 같으면 중복으로 간주
                if new_tc["name"] == old_tc["name"] and new_tc["args"] == old_tc["args"]:
                    is_dup = True
                    break
        
        if not is_dup:
            # [추가] 현재 배치 내 중복 확인
            # (모델이 한번에 똑같은 도구를 2번 호출하는 경우 방지)
            for existing in unique_tool_calls:
                if existing["name"] == new_tc["name"] and existing["args"] == new_tc["args"]:
                    is_dup = True
                    break
        
        if not is_dup:
            unique_tool_calls.append(new_tc)
        else:
            logger.info(f"🚫 [Loop Prevention] 연속/중복된 도구 실행 차단: {new_tc['name']}")

    # 중복이 제거된 리스트로 교체
    if len(unique_tool_calls) != len(new_msg.tool_calls):
        # 만약 모든 도구가 중복이라 다 지워졌다면? -> 사용자에게 알림
        if not unique_tool_calls:
            return AIMessage(content="✅ [System] 이미 최신 데이터를 확보했습니다. (중복 실행 방지됨)\n바로 위에서 출력된 도구 실행 결과(로그/메트릭)를 확인해주세요.")
        
        # 일부만 남음
        new_msg.tool_calls = unique_tool_calls
        
    return new_msg

# [최적화] Thinking 태그 제거 함수
def remove_thinking_tags(text: str) -> str:
    if "<think>" in text and "</think>" in text:
        # <think>...</think> 블록 제거
        import re
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


def estimate_token_count(text: str, model_name: str) -> int:
    """가능하면 tokenizer로, 어려우면 보수적인 문자 길이 추정으로 토큰 수를 계산합니다."""
    if not text:
        return 0

    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        encoding = None

    if encoding is not None:
        return len(encoding.encode(text))

    # fallback: 한국어/혼합 텍스트를 고려해 2 chars ~= 1 token으로 보수 추정
    return math.ceil(len(text) / 2)


def trim_text_to_token_limit(text: str, max_tokens: int, model_name: str, suffix: str) -> str:
    if max_tokens <= 0 or not text:
        return suffix.strip()

    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        encoding = None

    if encoding is not None:
        tokens = encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        clipped_tokens = tokens[:max_tokens]
        return encoding.decode(clipped_tokens).rstrip() + suffix

    max_chars = max_tokens * 2
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + suffix


def is_listing_request(text: str) -> bool:
    normalized = (text or "").lower().strip()
    listing_keywords = [
        "목록", "리스트", "보여줘", "나열", "조회", "줄래",
        "list", "show", "display",
    ]
    resource_keywords = [
        "namespace", "namespaces", "네임스페이스",
        "pod", "pods", "파드",
        "service", "services", "svc", "서비스",
        "deployment", "deployments", "디플로이먼트",
        "node", "nodes", "노드",
    ]
    diagnosis_keywords = [
        "왜", "원인", "진단", "분석", "이상", "문제", "에러", "오류", "상태 어때",
        "why", "diagnose", "analysis", "error", "issue", "problem",
    ]

    has_listing = any(keyword in normalized for keyword in listing_keywords)
    has_resource = any(keyword in normalized for keyword in resource_keywords)
    has_diagnosis = any(keyword in normalized for keyword in diagnosis_keywords)
    return has_listing and has_resource and not has_diagnosis

async def router_node(state: AgentState):
    """
    [Router] Instruct 모델이 사용자 질문을 분석하여 모드를 결정합니다.
    """
    # Router는 짧으니까 타임아웃만 적용된 instruct 모델 사용
    instruct_llm = get_instruct_model()
    
    # [최적화] 메시지 최적화 (Router는 최신 메시지만 봐도 됨)
    # 하지만 문맥 파악을 위해 최근 5개 정도는 유지
    safe_messages = trim_messages_history(
        state["messages"], keep_last=RUNTIME_LIMITS["router_keep_last"]
    )
    last_msg = safe_messages[-1]

    if is_listing_request(str(last_msg.content)):
        logger.info("🧭 [Router] 규칙 기반 분류: 목록/나열 요청으로 판단하여 SIMPLE 경로 선택")
        return {"mode": "simple"}
    
    prompt = f"""
    당신은 사용자 의도를 분류하는 AI입니다.
    사용자의 질문이 다음 중 어디에 해당하는지 단답형으로 대답하세요.
    
    1. "SIMPLE": 특정 단일 리소스의 단순 조회 또는 단일 도구로 즉시 답변 가능한 경우
       - 예: aaa 파드 목록 줘, 현재 시간 알려줘, 클러스터 CPU 상위 3개 파드 알려줘
       - 예: 네임스페이스 목록 보여줘, 서비스 목록 보여줘, 디플로이먼트 이름만 나열해줘
       - "목록", "이름만", "나열", "조회"처럼 단순 리소스 목록을 요구하는 요청은 기본적으로 SIMPLE입니다.
    2. "COMPLEX": 복합적인 추론이 필요하거나, 원인 분석(Diagnosis), 에러(Error) 해결, 여러 단계의 도구 사용이 필요한 경우. 특히 "전반적으로 진단해줘" 와 같은 포괄적 분석 요청은 COMPLEX로 분류하되, "전체 클러스터에서 CPU 점유율 상위 3개 알려줘"와 같이 단순히 랭킹/통계만 묻는 경우에는 단일 도구(`vm_query`)로 즉시 조회가 가능하므로 "SIMPLE"로 분류하세요.
    
    [사용자 질문]
    {last_msg.content}
    
    [응답 형식]
    오직 "SIMPLE" 또는 "COMPLEX"라고만 대답하세요.
    """
    
    response = await instruct_llm.ainvoke([HumanMessage(content=prompt)])
    mode = response.content.strip().upper()
    
    # 안전장치
    if "COMPLEX" in mode:
        return {"mode": "complex"}
    else:
        return {"mode": "simple"}

# -----------------------------------------------------------------
# [Simple Mode] 단순 실행
# -----------------------------------------------------------------
async def simple_agent_node(state: AgentState, tools):
    """표준 ReAct 에이전트"""
    instruct_llm = get_instruct_model()
    llm_with_tools = instruct_llm.bind_tools(tools)
    
    # 현재 시간 주입 (모델이 'now'를 모를 때 대비)
    current_time = datetime.now(timezone.utc).isoformat()
    
    sys_msg = SystemMessage(content=f"""
    당신은 빠르고 정확한 K8s 및 Observability 관리자입니다.
    
    [현재 시간 (UTC)]
    {current_time}
    
    [VictoriaLogs(vlogs) 도구 가이드]
    - **vlogs_query**: LogsQL을 사용하여 로그를 검색합니다.
      - 문법: `level:error`, `pod:backend` (따옴표 없이 텍스트 검색 권장)
      - **주의**: `level="error"` (X) -> `level:error` (O). 빈 쿼리나 `.*` 만 쓰는 것은 피하세요.
    - **vlogs_hits**: 로그 발생 건수 추이를 봅니다.
    
    [VictoriaMetrics(vm) 도구 가이드]
    - **vm_query**: PromQL을 사용해 메트릭 조회 (예: `rate(error_count[5m])`).
    - **vm_alerts**: 현재 알람 조회.
    
    [Kubernetes(k8s) 도구 가이드]
    - **k8s_kubectl_get**: 리소스 조회. `labelSelector`에 `status=...` 넣지 마세요.
    - **k8s_kubectl_describe**: 이벤트 및 상세 상태 확인.
    
    [규칙]
    1. 사용자의 요청이 단순하므로, 생각하지 말고 바로 도구를 호출하세요.
    2. 중복 실행을 피하고, 결과가 나오면 바로 요약해서 답변하세요.
    3. 무조건 한국어로 대답하세요.
    """)

    
    # [최적화] 메시지 정리
    safe_messages = trim_messages_history(
        state["messages"], keep_last=RUNTIME_LIMITS["simple_keep_last"]
    )
    messages = [sys_msg] + safe_messages
    
    # [최적화] Max Steps Check (무한 루프 방지)
    # 현재 답변(AIMessage) 개수가 너무 많으면 강제 종료
    ai_msg_count = sum(1 for m in state["messages"] if isinstance(m, AIMessage))
    if ai_msg_count > RUNTIME_LIMITS["max_ai_steps"]:
        return {"messages": [AIMessage(content="⚠️ [System] 대화가 너무 길어져 안전을 위해 종료합니다. 현재까지의 정보로 답변해주세요.")]}

    response = await llm_with_tools.ainvoke(messages)
    
    # [최적화] 중복 호출 필터링 (무한 루프 방지)
    # 동일한 입력값으로 연속 호출 시 차단하고 사용자에게 알림
    final_response = check_and_filter_duplicate_tools(state["messages"], response)
    
    return {"messages": [final_response]}

async def orchestrator_node(state: AgentState):
    """[Orchestrator] Instruct 모델이 작업을 분석하고 Worker들에게 위임합니다."""
    # [변경] Thinking 모델 대신 Instruct 모델 사용 (JSON 생성 안정성 확보)
    instruct_llm = get_instruct_model()
    
    # 최신 메시지 위주로 분석
    last_msg = state["messages"][-1]
    
    prompt = f"""
    당신은 AIOps 시스템의 '지휘자(Orchestrator)'입니다.
    사용자의 요청을 해결하기 위해 하위 전문가(Worker)들에게 작업을 지시해야 합니다.
    직접 문제를 해결하려 하지 말고, "어떤 정보를 수집해야 하는지" 계획을 세워 위임하세요.
    
    [하위 전문가 목록]
    1. **LogSpecialist** (Logs): 로그 분석 전문가.
       - 도구: VictoriaLogs (`vlogs_*`), Loki.
       - 역할: 에러 로그 패턴 파악 및 특정 대상(Pod, Namespace 등)의 전체 흐름 분석.
       - 팁: 에러(`level:error`)만 보지 말고, **경고(`level:warn`)나 'cannot', 'fail', 'forbidden', 'denied'** 같은 핵심 키워드를 함께 조회하도록 하세요. **중요: 방대한 데이터 반환으로 인한 Truncation(잘림) 현상을 막기 위해, 검색 시간 범위를 넉넉히 최근 1시간(`now-1h`)으로 설정하되, `limit: 50`과 같이 요청 로그 건수를 제한하며, 쿼리 문자열 끝에 반드시 `| collapse_nums` 파이프를 붙여 중복 로그를 제거하라고 명시적으로 지시하세요.**
    2. **MetricSpecialist** (Metrics/Traces): 메트릭 및 트레이스 분석 전문가.
       - 도구: VictoriaMetrics (`vm_*`), VictoriaTraces (`vtraces_*`), Prometheus.
       - 역할: 리소스 사용량(CPU/Mem/Network), 트래픽 패턴(`vm_query`), 분산 트레이싱 추적(`vtraces_trace`).
       - 팁: 전체 클러스터를 조회할 때는 방대한 데이터로 인한 Truncation 방지를 위해 **CPU, Memory, Network 사용량의 Top 10 파드**를 중점적으로 확인하라고 지시하세요. **(주의: 메트릭(PromQL) 쿼리에는 절대 `| limit` 나 `| collapse_nums` 파이프를 붙이지 마세요. 개수 제한이 필요할 경우 오직 `topk(N, ...)` 함수의 숫자 N을 조절하라고 작업자에게 명시적으로 경고하세요.)**
    3. **K8sSpecialist** (K8s Config): K8s 설정 및 리소스 조회 전문가.
       - 도구: Kubernetes (`k8s_*`), Kubectl.
       - 역할: Pod 상태 목록(`k8s_kubectl_get`), 상세 설정(`k8s_kubectl_describe`), 이벤트 조회.
       - **중요**: 클러스터 전체 조회 등 대량의 데이터를 요청할 때는 작업자에게 반드시 `output="name"` 등의 필터를 사용하라고 지시하세요.
       
    [사용자 질문]
    {last_msg.content}
    
    [지시 작성 규칙]
    1. 각 전문가에게 시킬 일을 명확한 문장으로 작성하세요.
    2. **핵심 룰**: 사용자의 질문이 "전반적인 진단", "전체 상태 어때?" 처럼 포괄적인(COMPLEX) 경우, **반드시 K8s, Log, Metric 3명의 전문가를 모두 호출**하여 교차 검증할 수 있도록 입체적인 지시를 내리세요. 이때 로그 전문가에게는 **에러(`error`)뿐만 아니라 경고(`warn`)나 'cannot', 'fail'** 같은 이상 징후 키워드도 같이 찾아보라고 지시하세요.
    3. 특정 리소스에만 한정된 질문이라면 필요한 전문가에게만 지시를 내리세요. (선택적 위임)
    4. **출력 형식은 반드시 JSON 코드 블록**이어야 합니다.
    
    [출력 예시]
    ```json
    {{
        "log": "backend-api의 최근 1시간 에러 로그를 조회해서 원인을 파악해.",
        "metric": "해당 파드의 메모리 사용량이 급증했는지 확인해.",
        "k8s": "최근 배포된 이미지 태그와 Deployment 설정을 확인해."
    }}
    ```
    """
    
    response = await instruct_llm.ainvoke([HumanMessage(content=prompt)])
    # Instruct 모델은 태그가 없으므로 제거 로직 불필요
    content = response.content
    logger.debug(f"🐛 [Debug] Orchestrator Raw Content:\n{content[:500]}...") # 디버깅용
    
    # JSON 파싱
    worker_plans = {}
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
            worker_plans = json.loads(json_str)
        elif "{" in content:
            # 코드 블록이 없을 경우 대비
            import re
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                worker_plans = json.loads(match.group())
    except Exception as e:
        logger.warning(f"⚠️ [Orchestrator] JSON 파싱 실패: {e}")
    
    # [안전장치] 만약 파싱 실패하거나 계획이 비어있다면 -> K8s 전문가에게 전체 위임
    if not worker_plans:
        logger.warning("⚠️ [Orchestrator] 계획 수립 실패 또는 결과 없음 -> K8s Fallback 모드 작동")
        worker_plans = {
            "k8s": f"사용자의 다음 요청을 스스로 판단하여 해결하시오(Log/Metric 도구 사용 가능시 사용): {last_msg.content}",
            "log": f"필요시 {last_msg.content} 관련 에러 로그 조회",
            "metric": f"필요시 {last_msg.content} 관련 리소스 조회"
        }

    return {
        "worker_plans": worker_plans, 
        "messages": [AIMessage(content=f"🧠 [Orchestrator] 작업 위임:\n{json.dumps(worker_plans, ensure_ascii=False, indent=2)}")]
    }

# -----------------------------------------------------------------
# [Workers] 병렬 실행
# -----------------------------------------------------------------

def filter_tools(tools: list, category: str) -> list:
    """도구 이름에 따라 Worker별로 도구를 필터링합니다."""
    filtered = []
    # 소문자로 비교
    for t in tools:
        name = t.name.lower()
        if category == "log":
            if any(k in name for k in ["log", "vlogs", "loki"]): filtered.append(t)
        elif category == "metric":
            # [변경] vtraces(VictoriaTraces)도 메트릭 전문가에게 할당
            if any(k in name for k in ["metric", "vm", "prom", "vtraces", "trace"]): filtered.append(t)
        elif category == "k8s":
             # 로그나 메트릭/트레이스가 아닌 모든 것은 K8s/General 담당
             if not any(k in name for k in ["log", "vlogs", "loki", "metric", "vm", "prom", "vtraces", "trace"]):
                 filtered.append(t)
    return filtered

async def run_single_worker(worker_name: str, instruction: str, tools: list):
    """단일 Worker 실행 함수 (독립된 LLM 호출)"""
    if not instruction or not tools:
        return f"[{worker_name}] 실행 안 함 (지시 없음 또는 도구 없음)"
        
    logger.info(f"👷 [{worker_name}] 시작: {instruction}")
    from config import stream_queue
    worker_node_map = {
        "K8sSpecialist": "worker_k8s",
        "MetricSpecialist": "worker_metric",
        "LogSpecialist": "worker_log",
    }
    worker_node_id = worker_node_map.get(worker_name, "agent")
    await stream_queue.put(f'STATUS:{{"nodeId":"{worker_node_id}","status":"running"}}')
    await stream_queue.put(f"EVENT:👷 [{worker_name}] 시작: {instruction}")
    
    # Worker는 빠르고 정확한 Instruct 모델 사용
    llm = get_instruct_model()
    llm_with_tools = llm.bind_tools(tools)
    
    # [변경] Worker별 특화 프롬프트 (User 제공 Docs 반영)
    special_instructions = ""
    
    if "LogSpecialist" in worker_name:
        special_instructions = """
    [VictoriaLogs(vlogs) 도구 가이드]
    - **vlogs_query**: LogsQL을 사용하여 로그를 검색합니다.
      - 문법: `level:error`, `level:warn`, `pod:backend`, `cannot OR fail OR forbidden`
      - **주의**: `level="error"` 형태는 지원하지 않습니다.
      - **중요(데이터 절단 방지 및 limit)**: 반환 데이터가 5만 자를 넘기면 잘리므로(Truncation), `start` 범위를 넉넉히 **`now-1h`** (최근 1시간)으로 설정하되, 도구가 지원한다면 반드시 **`limit=50`** 파라미터를 활용하여 **최대 로그 결과 수를 제한**하세요.
      - **중복 로그 폭주 대처법 (대안A)**: 특정 에러가 단기간에 폭주하여 다른 중요 로그를 가릴 우려가 있다면, 쿼리 문자열 끝에 파이프라인 연산자인 **`| collapse_nums`** 를 붙여서(예: `level:error | collapse_nums`) 숫자나 시간값 등 때문에 다르게 인식되는 비슷한 패턴의 로그들을 하나로 묶어버리세요. 이렇게 하면 훨씬 다양한(Unique한) 종류의 에러 로그 샘플을 확보할 수 있습니다.
      - **분석 요령**: 단순히 에러만 찾지 말고, **`level:warn`이나 'cannot', 'fail', 'forbidden'** 같은 키워드를 포함해 조회하세요. 특정 파드의 전체 로그(`*`)를 조회하여 에러 전후 상황을 살피는 것이 중요합니다.
      - **전체 로그 검색**: 특정 필드가 없을 수 있으므로 전체 로그를 볼 때는 `*` 또는 아무것도 입력하지 마세요.
    - **vlogs_facets**: 특정 필드(예: `level`, `pod`)의 빈도수(Top N)를 봅니다. (로그 양이 많을 때 유용)
    - **vlogs_hits**: 로그 발생 건수 시계열 통계를 봅니다.
    """
    elif "MetricSpecialist" in worker_name:
        special_instructions = """
    [VictoriaMetrics(vm) 도구 가이드]
    - **vm_query**: PromQL을 사용하여 메트릭을 조회합니다. 
      - **중요(데이터 절단 방지):** 클러스터 전체 조회 시 데이터가 5만 자를 넘어 잘리는 것을 막기 위해, 반드시 **`topk(10, ...)`** 함수를 사용하여 리소스를 가장 많이 소모하는 상위 파드 위주로 분석하세요.
      - **경고(문법 오류 절대 주의):** PromQL 쿼리 끝에 로그 검색용 파이프 문법인 `| limit N` 이나 `| collapse_nums` 를 절대 붙이지 마세요. 심각한 422 구문 오류가 발생합니다. 반환 결과 개수를 제한하려면 오직 `topk(N, 쿼리)` 의 N 값만 변경하세요.
      - **추천 쿼리 패턴 (강력 권장):**
        * CPU Top 10: `topk(10, sum(rate(container_cpu_usage_seconds_total{container!=""}[5m])) by (pod))`
        * RAM Top 10 (OOM 킬러가 보는 지표): `topk(10, sum(container_memory_working_set_bytes{container!=""}) by (pod))`
        * Network In Top 10: `topk(10, sum(rate(container_network_receive_bytes_total[5m])) by (pod))`
        * Network Out Top 10: `topk(10, sum(rate(container_network_transmit_bytes_total[5m])) by (pod))`
    - **vm_alerts**: 현재 발생 중인 알림(Alerts)을 조회합니다. 경로는 `/api/v1/alerts`가 기본입니다.
    - **vm_metrics**: 특정 메트릭 이름을 검색할 때 유용합니다. (주의: 빈 인자로 호출 시 모든 메트릭 이름이 반환되어 데이터가 잘릴 수 있으므로, 구체적인 패턴 검색 시에만 사용)
    
    [VictoriaTraces(vtraces) 도구 가이드]
    - **vtraces_traces**: TraceQL 또는 필터를 사용해 트레이스를 검색합니다.
    - **vtraces_services**: 트레이싱된 서비스 목록을 봅니다.
    - **vtraces_dependencies**: 서비스 간 의존성 그래프를 봅니다.
    """
    elif "K8sSpecialist" in worker_name:
        special_instructions = """
    [Kubernetes(k8s) 도구 가이드]
    - **k8s_kubectl_get**: 리소스 목록 조회. 필터(fieldSelector)를 적극 활용해 데이터를 최소화하세요.
      - **중요**: 대량 조회 시 반드시 `output="name"`이나 `output="custom-columns=NAME:.metadata.name,STATUS:.status.phase"`를 써서 데이터 양을 아끼세요.
    - **k8s_kubectl_events** (이벤트 조회): 에러 원인을 찾을 때 `describe`보다 가볍고 빠른 이벤트를 우선 조회하세요. (예: `kubectl get events --field-selector type=Warning`)
    - **k8s_kubectl_describe**: 특정 단일 객체의 원인이 이벤트만으로 안 나올 때 최후의 수단으로만 사용하세요. (출력물이 너무 길어 시스템 속도를 크게 저하시킵니다)
    """
    
    sys_msg = SystemMessage(content=f"""
    당신은 {worker_name}입니다.
    Orchestrator로부터 다음 지시를 받았습니다:
    "{instruction}"
    
    {special_instructions}
    
    당신에게 할당된 도구만을 사용하여 지시를 수행하세요.
    - 필요한 정보를 찾았다면 즉시 답변하세요.
    - 도구 실행 결과(Logs, Metrics 등)를 요약해서 보고하세요.
    """)
    
    try:
        # 1. 도구 호출 결정
        response = await llm_with_tools.ainvoke([sys_msg])
        
        # 2. 도구 실행 (Tool Call이 있다면)
        if response.tool_calls:
            # LangGraph ToolNode를 쓰지 않고 여기서 직접 호출해서 결과를 받음
            # (Worker 내부의 루프를 단순화하기 위함)
            # 하지만 여기서는 간단히 Tool 결과까지 포함해서 반환하도록 함.
            
            tool_outputs = []
            for tc in response.tool_calls:
                # 도구 객체 찾기
                selected_tool = next((t for t in tools if t.name == tc["name"]), None)
                if selected_tool:
                    logger.debug(f"   🔨 [{worker_name}] 도구 실행: {tc['name']}")
                    # 동기/비동기 호출 처리 (LangChain Tool은 보통 run 또는 arun)
                    # 여기서는 간단히 tool.invoke 사용
                    try:
                        # tool.invoke는 동기일 수도, 비동기일 수도 있음. 안전하게 비동기 tool이면 ainvoke
                        if hasattr(selected_tool, "ainvoke"):
                            res = await selected_tool.ainvoke(tc["args"])
                        else:
                            res = selected_tool.invoke(tc["args"])
                            
                        res_str = str(res).strip()
                        if not res_str:
                            res_str = "[빈 결과 반환 - 이는 에러가 아니라, 필터 조건(예: Error 상태)에 해당하는 타겟 리소스가 클러스터 내에 단 하나도 없어서 완벽하게 건강함을 의미합니다.]"
                            
                        tool_outputs.append(f"Tool({tc['name']}) Output: {res_str}")
                    except Exception as te:
                        tool_outputs.append(f"Tool({tc['name']}) Error: {te}")
            
            # 3. [최적화] Sub-Agent Summarization (Map-Reduce)
            # 도구 결과를 날것 그대로 보내지 않고, Orchestrator의 지시(instruction)에 맞춰 필터링/요약합니다.
            raw_results = "\n\n".join(tool_outputs)
            
            # 토큰 절약을 위해 날것의 데이터가 너무 길면 여기서도 1차 절단 (비상용)
            max_raw_length = RUNTIME_LIMITS["worker_raw_result_max_chars"]
            if len(raw_results) > max_raw_length:
                if "K8sSpecialist" in worker_name:
                    # K8s describe 결과는 맨 끝에 핵심인 'Events'가 있으므로 뒷부분 위주로 보존
                    head_quota = min(2000, max_raw_length)
                    tail_quota = max(0, max_raw_length - head_quota)
                    original_raw_results = raw_results
                    raw_results = original_raw_results[:head_quota]
                    if tail_quota > 0:
                        raw_results += "\n\n... (중략: 장황한 환경변수/볼륨 데이터 생략) ...\n\n" + original_raw_results[-tail_quota:]
                elif "LogSpecialist" in worker_name:
                    # 너무 많이 자르면(4000자) 핵심 에러가 유실될 부작용이 있으므로,
                    # 여유를 두고 8000자로 늘립니다. (대신 파이프라인에서 limit: 50 등으로 걸러진 상태를 가정)
                    raw_results = raw_results[:max_raw_length] + "\n... (로그 데이터 길어짐, 이하 생략)"
                else:
                    raw_results = raw_results[:max_raw_length] + "\n... (데이터 길어짐)"

            summarize_prompt = f"""
            당신은 {worker_name}의 요약 담당자입니다.
            지휘자(Orchestrator)가 당신에게 내린 원래 임무는 다음과 같습니다:
            <instruction>
            {instruction}
            </instruction>
            
            아래는 도구를 실행하여 얻은 날것의 데이터(Raw Data)입니다:
            <raw_data>
            {raw_results}
            </raw_data>
            
            **[작업 지시]**
            1. 오직 위의 <instruction>에 답하는 데 필요한 핵심 팩트만 <raw_data>에서 추출하세요.
            2. 발견된 에러 문구, 경고, 실패 파드 이름은 절대 누락하지 말고 보존하세요.
            3. 문장을 엄청 길게 풀어서 설명하지 마시고, "1. API 파드 Pending" 처럼 가독성이 좋은 개조식(Bullet points)으로 작성해주세요.
            4. 출력 길이는 충분한 장애 진단 정보 제공을 위해 최대 **2,000자**까지 허용합니다. 단, 인사말(서론/결론)은 생략하세요.
            5. 핵심 에러 원문(Stack Trace)만 예외적으로 그대로 붙여넣어 주세요.
            """

            max_input_tokens = INSTRUCT_CONFIG.get("max_input_tokens")
            if max_input_tokens:
                prompt_without_raw_data = summarize_prompt.replace(raw_results, "")
                reserved_tokens = estimate_token_count(
                    prompt_without_raw_data, INSTRUCT_CONFIG["model_name"]
                )
                available_tokens = max_input_tokens - reserved_tokens
                if available_tokens < estimate_token_count(raw_results, INSTRUCT_CONFIG["model_name"]):
                    raw_results = trim_text_to_token_limit(
                        raw_results,
                        max(available_tokens, 1),
                        INSTRUCT_CONFIG["model_name"],
                        "\n... (⚠️ max_input_tokens 보호 장치에 의해 절단됨)",
                    )
                    summarize_prompt = f"""
            당신은 {worker_name}의 요약 담당자입니다.
            지휘자(Orchestrator)가 당신에게 내린 원래 임무는 다음과 같습니다:
            <instruction>
            {instruction}
            </instruction>
            
            아래는 도구를 실행하여 얻은 날것의 데이터(Raw Data)입니다:
            <raw_data>
            {raw_results}
            </raw_data>
            
            **[작업 지시]**
            1. 오직 위의 <instruction>에 답하는 데 필요한 핵심 팩트만 <raw_data>에서 추출하세요.
            2. 발견된 에러 문구, 경고, 실패 파드 이름은 절대 누락하지 말고 보존하세요.
            3. 문장을 엄청 길게 풀어서 설명하지 마시고, "1. API 파드 Pending" 처럼 가독성이 좋은 개조식(Bullet points)으로 작성해주세요.
            4. 출력 길이는 충분한 장애 진단 정보 제공을 위해 최대 **2,000자**까지 허용합니다. 단, 인사말(서론/결론)은 생략하세요.
            5. 핵심 에러 원문(Stack Trace)만 예외적으로 그대로 붙여넣어 주세요.
            """
            
            logger.debug(f"   📝 [{worker_name}] 도구 결과 요약 중... (Sub-Agent Summarization)")
            
            import time
            import asyncio
            start_time = time.time()
            
            async def poll_progress(coro):
                t = asyncio.create_task(coro)
                # 5초마다 상태(진행 시간) 출력 및 Queue로 전송(UI 스트리밍용)
                while not t.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(t), timeout=5.0)
                    except asyncio.TimeoutError:
                        elapsed = int(time.time() - start_time)
                        m, s = divmod(elapsed, 60)
                        ts = f"{m}m{s}s" if m > 0 else f"{s}s"
                        msg = f"⏳ `[{worker_name}]` 계속 요약 중... (running for {ts})"
                        logger.info(msg)
                        await stream_queue.put(msg)
                return t.result()
                
            summary_response = await poll_progress(llm.ainvoke([HumanMessage(content=summarize_prompt)]))
            
            total_time = int(time.time() - start_time)
            msg_done = f"✅ `[{worker_name}]` 도구 결과 요약 완료! (총 {total_time}초 소요)"
            logger.info(msg_done)
            await stream_queue.put(f'STATUS:{{"nodeId":"{worker_node_id}","status":"success"}}')
            await stream_queue.put(msg_done)
            
            final_report = f"[{worker_name}] 집중 분석 결과:\n" + summary_response.content
            return final_report
        else:
            await stream_queue.put(f'STATUS:{{"nodeId":"{worker_node_id}","status":"success"}}')
            return f"[{worker_name}] 집중 분석 결과: (도구 호출 없이 답변) {response.content}"
            
    except Exception as e:
        await stream_queue.put(f'STATUS:{{"nodeId":"{worker_node_id}","status":"error","error":{json.dumps(str(e), ensure_ascii=False)}}}')
        return f"[{worker_name}] 에러 발생: {e}"

async def workers_node(state: AgentState, tools: list):
    """[Workers] Orchestrator의 계획을 받아 병렬로 작업을 수행합니다."""
    plans = state.get("worker_plans", {})
    
    # 도구 분류
    log_tools = filter_tools(tools, "log")
    metric_tools = filter_tools(tools, "metric")
    k8s_tools = filter_tools(tools, "k8s")
    
    tasks = []
    
    # 할 일 있는 Worker만 실행
    if plans.get("log"):
        tasks.append(run_single_worker("LogSpecialist", plans["log"], log_tools))
        
    # metric이나 traces 키가 있으면 MetricSpecialist에게 할당 (두 지시가 다 있으면 합침)
    metric_instruction = ""
    if plans.get("metric"):
        metric_instruction += plans["metric"] + "\n"
    if plans.get("traces"):
        metric_instruction += plans["traces"] + "\n"
        
    if metric_instruction.strip():
        tasks.append(run_single_worker("MetricSpecialist", metric_instruction.strip(), metric_tools))
        
    if plans.get("k8s"):
        tasks.append(run_single_worker("K8sSpecialist", plans["k8s"], k8s_tools))
        
    if not tasks:
        return {"worker_results": ["⚠️ 작업 지시 사항이 없습니다."]}
        
    # [최적화] API Rate Limit 및 Hang 방지를 위한 Semaphore 도입
    # 한 번에 최대 2개의 Worker만 LLM을 호출하도록 강제 (동시성 제한)
    sem = asyncio.Semaphore(2)
    
    async def run_with_semaphore(task_coro):
        async with sem:
            # 약간의 시차(Jitter)를 두어 API 융단폭격(Thundering Herd) 방지
            await asyncio.sleep(0.5) 
            return await task_coro

    # 래핑된 태스크들로 병렬 실행
    safe_tasks = [run_with_semaphore(t) for t in tasks]
    results = await asyncio.gather(*safe_tasks)
    
    # 결과 포맷팅
    formatted_results = "\n\n".join(results)
    
    return {
        "worker_results": results, 
        "messages": [AIMessage(content=f"👷 [Workers] 작업 완료. (총 {len(results)}건 보고)")]
    }

async def synthesizer_node(state: AgentState):
    """[Synthesizer] Thinking 모델이 도구 실행 결과를 종합하여 최종 답변을 작성합니다."""
    # 스트리밍 끔 (안정성)
    thinking_llm = get_thinking_model(stream_prefix="📝 [Synthesizing]")
    from config import stream_queue
    await stream_queue.put('STATUS:{"nodeId":"synthesizer","status":"running"}')
    await stream_queue.put("EVENT:📝 [Synthesizer] 최종 종합 시작")
    
    # [최적화] 진단 우선순위 재정렬 및 균등 배분(Fair Share)
    # K8s(기본 상태) -> Metric(현상) -> Log(상세 원인) 순서로 중요도 배치
    worker_results_dict = {}
    for res in state.get("worker_results", []):
        if "[K8sSpecialist]" in res: worker_results_dict["k8s"] = res
        elif "[MetricSpecialist]" in res: worker_results_dict["metric"] = res
        elif "[LogSpecialist]" in res: worker_results_dict["log"] = res

    # 각 전문가별 최대 할당 글자 수 (이미 요약본이므로 2,000자면 충분)
    quota = RUNTIME_LIMITS["worker_summary_quota"]
    ordered_results = []
    
    # 1순위: K8s (기반 정보)
    if "k8s" in worker_results_dict:
        res = worker_results_dict["k8s"]
        if len(res) > quota:
            res = res[:quota] + "\n... (⚠️ 요약본이 너무 길어 절단됨)"
        ordered_results.append(res)

    # 2순위: Metric (수치적 징후)
    if "metric" in worker_results_dict:
        res = worker_results_dict["metric"]
        if len(res) > quota:
            res = res[:quota] + "\n... (⚠️ 요약본이 너무 길어 절단됨)"
        ordered_results.append(res)

    # 3순위: Log (상세 발생 원인)
    if "log" in worker_results_dict:
        res = worker_results_dict["log"]
        if len(res) > quota:
            res = res[:quota] + "\n... (⚠️ 요약본이 너무 길어 절단됨)"
        ordered_results.append(res)

    worker_results_str = "\n\n".join(ordered_results)
    
    # [최적화] 전역 컨텍스트 가드 (최종 안전장치) - 요약본이므로 10,000자면 충분
    max_total_context = RUNTIME_LIMITS["max_total_context"]
    if len(worker_results_str) > max_total_context:
        worker_results_str = worker_results_str[:max_total_context] + "\n\n... (⚠️ 전역 보호 장치에 의해 하단 절단됨)"
    
    logger.debug(f"   📝 [Synthesizer] 각 전문가의 요약본 취합 완료 (총 길이: {len(worker_results_str)}자)")

    prompt = f"""
    당신은 최종 답변을 정리하는 Synthesizer입니다.
    Orchestrator가 작업자(Worker)들에게 지시를 내렸고, 그 결과가 아래와 같습니다.
    이 내용을 종합하여 사용자의 질문에 대한 최종 진단과 답변을 작성하세요.
    
    [사용자 질문]
    {state['messages'][-1].content}
    
    [Worker 실행 결과 보고서]
    {worker_results_str}
    
    [작성 규칙]
    1. 각 전문가의 분석 결과를 인용하여 논리적으로 설명하세요.
    2. 결과를 바탕으로 원인을 진단하고, 해결책을 제안하세요.
    2-1. 단, 사용자의 질문이 "목록", "리스트", "이름만", "나열", "조회" 같은 단순 리소스 조회라면 진단문으로 과해석하지 말고 요청한 목록을 간단히 반환하세요.
    2-2. 단순 목록 요청에서는 "클러스터가 건강하다", "수동 점검이 필요 없다" 같은 건강성 평가를 덧붙이지 마세요. 정말 필요한 경우에만 한 줄 덧붙이세요.
    3. **핵심 분석 룰**: 도구 실행 결과가 "[빈 결과 반환...]" 형태로 왔다면, 절대 권한 부족이나 통신 장애로 오해하지 마세요! 오류 필터(예: Failed 파드 제한)에 걸리는 안 좋은 리소스가 아예 없어서 클러스터가 매우 건강하다는 뜻입니다. 이를 분석하여 사용자에게 "에러 파드가 하나도 없이 건강하다"고 보고하세요.
    4. **추가 건강성 룰**: K8s 전문의 보고서가 단순히 파드 이름 목록(`pod/xxx`, `deployment/yyy` 등)만 나열하고 특별한 에러 메시지(CrashLoopBackOff, Pending, Failed 등)가 없다면, 그 리소스들은 정상적으로 띄워져 있는 것(Running)으로 확신하고 설명하세요. "상태를 명확히 알 수 없다"고 애매하게 답변하지 마세요.
    5. 결과에 실제 에러 문구(Unauthorized, Connection Refused 등)나 알 수 없는 크래시 흔적이 있을 때만 수동 점검을 제안하세요.
    """

    max_input_tokens = THINKING_CONFIG.get("max_input_tokens")
    if max_input_tokens:
        prompt_without_results = f"""
    당신은 최종 답변을 정리하는 Synthesizer입니다.
    Orchestrator가 작업자(Worker)들에게 지시를 내렸고, 그 결과가 아래와 같습니다.
    이 내용을 종합하여 사용자의 질문에 대한 최종 진단과 답변을 작성하세요.
    
    [사용자 질문]
    {state['messages'][-1].content}
    
    [Worker 실행 결과 보고서]
    
    [작성 규칙]
    1. 각 전문가의 분석 결과를 인용하여 논리적으로 설명하세요.
    2. 결과를 바탕으로 원인을 진단하고, 해결책을 제안하세요.
    2-1. 단, 사용자의 질문이 "목록", "리스트", "이름만", "나열", "조회" 같은 단순 리소스 조회라면 진단문으로 과해석하지 말고 요청한 목록을 간단히 반환하세요.
    2-2. 단순 목록 요청에서는 "클러스터가 건강하다", "수동 점검이 필요 없다" 같은 건강성 평가를 덧붙이지 마세요. 정말 필요한 경우에만 한 줄 덧붙이세요.
    3. **핵심 분석 룰**: 도구 실행 결과가 "[빈 결과 반환...]" 형태로 왔다면, 절대 권한 부족이나 통신 장애로 오해하지 마세요! 오류 필터(예: Failed 파드 제한)에 걸리는 안 좋은 리소스가 아예 없어서 클러스터가 매우 건강하다는 뜻입니다. 이를 분석하여 사용자에게 "에러 파드가 하나도 없이 건강하다"고 보고하세요.
    4. **추가 건강성 룰**: K8s 전문의 보고서가 단순히 파드 이름 목록(`pod/xxx`, `deployment/yyy` 등)만 나열하고 특별한 에러 메시지(CrashLoopBackOff, Pending, Failed 등)가 없다면, 그 리소스들은 정상적으로 띄워져 있는 것(Running)으로 확신하고 설명하세요. "상태를 명확히 알 수 없다"고 애매하게 답변하지 마세요.
    5. 결과에 실제 에러 문구(Unauthorized, Connection Refused 등)나 알 수 없는 크래시 흔적이 있을 때만 수동 점검을 제안하세요.
    """
        reserved_tokens = estimate_token_count(
            prompt_without_results, THINKING_CONFIG["model_name"]
        )
        available_tokens = max_input_tokens - reserved_tokens
        if available_tokens < estimate_token_count(
            worker_results_str, THINKING_CONFIG["model_name"]
        ):
            worker_results_str = trim_text_to_token_limit(
                worker_results_str,
                max(available_tokens, 1),
                THINKING_CONFIG["model_name"],
                "\n\n... (⚠️ max_input_tokens 보호 장치에 의해 절단됨)",
            )
            prompt = f"""
    당신은 최종 답변을 정리하는 Synthesizer입니다.
    Orchestrator가 작업자(Worker)들에게 지시를 내렸고, 그 결과가 아래와 같습니다.
    이 내용을 종합하여 사용자의 질문에 대한 최종 진단과 답변을 작성하세요.
    
    [사용자 질문]
    {state['messages'][-1].content}
    
    [Worker 실행 결과 보고서]
    {worker_results_str}
    
    [작성 규칙]
    1. 각 전문가의 분석 결과를 인용하여 논리적으로 설명하세요.
    2. 결과를 바탕으로 원인을 진단하고, 해결책을 제안하세요.
    2-1. 단, 사용자의 질문이 "목록", "리스트", "이름만", "나열", "조회" 같은 단순 리소스 조회라면 진단문으로 과해석하지 말고 요청한 목록을 간단히 반환하세요.
    2-2. 단순 목록 요청에서는 "클러스터가 건강하다", "수동 점검이 필요 없다" 같은 건강성 평가를 덧붙이지 마세요. 정말 필요한 경우에만 한 줄 덧붙이세요.
    3. **핵심 분석 룰**: 도구 실행 결과가 "[빈 결과 반환...]" 형태로 왔다면, 절대 권한 부족이나 통신 장애로 오해하지 마세요! 오류 필터(예: Failed 파드 제한)에 걸리는 안 좋은 리소스가 아예 없어서 클러스터가 매우 건강하다는 뜻입니다. 이를 분석하여 사용자에게 "에러 파드가 하나도 없이 건강하다"고 보고하세요.
    4. **추가 건강성 룰**: K8s 전문의 보고서가 단순히 파드 이름 목록(`pod/xxx`, `deployment/yyy` 등)만 나열하고 특별한 에러 메시지(CrashLoopBackOff, Pending, Failed 등)가 없다면, 그 리소스들은 정상적으로 띄워져 있는 것(Running)으로 확신하고 설명하세요. "상태를 명확히 알 수 없다"고 애매하게 답변하지 마세요.
    5. 결과에 실제 에러 문구(Unauthorized, Connection Refused 등)나 알 수 없는 크래시 흔적이 있을 때만 수동 점검을 제안하세요.
    """
    
    # [최적화] Synthesizer는 직전 맥락(질문)을 포함
    messages = [HumanMessage(content=prompt)]
    
    response = await thinking_llm.ainvoke(messages)
    
    # [최적화] 태그 제거 후 저장
    response.content = remove_thinking_tags(response.content)
    
    return {"messages": [response]}

# =================================================================
# 4. 그래프 생성 함수
# =================================================================
def create_agent_app(tools: list):
    workflow = StateGraph(AgentState)
    
    # 노드 등록
    workflow.add_node("router", router_node)
    
    # 1. Simple Path 노드
    async def simple_agent_wrapper(state):
        return await simple_agent_node(state, tools)
    workflow.add_node("simple_agent", simple_agent_wrapper)
    
    # 2. Complex Path 노드들 (Orchestrator-Workers)
    async def orchestrator_wrapper(state):
        return await orchestrator_node(state)
    workflow.add_node("orchestrator", orchestrator_wrapper)
    
    async def workers_wrapper(state):
        return await workers_node(state, tools)
    workflow.add_node("workers", workers_wrapper)
    
    workflow.add_node("synthesizer", synthesizer_node)
    
    # 3. 도구 실행 노드 (Simple Mode용)
    workflow.add_node("tools", ToolNode(tools))

    # --- 엣지(Edge) 연결 ---
    
    # 시작 -> 라우터
    workflow.add_edge(START, "router")
    
    # 라우터 -> 분기
    def route_decision(state):
        if state and state.get("mode") == "complex":
            return "orchestrator"
        return "simple_agent"
        
    workflow.add_conditional_edges("router", route_decision)
    
    # [Path 1] Simple Mode 루프
    def simple_tools_condition(state):
        if state and state["messages"][-1].tool_calls:
            return "tools"
        return END

    workflow.add_conditional_edges("simple_agent", simple_tools_condition, {"tools": "tools", END: END})
    workflow.add_edge("tools", "simple_agent") 
    
    # [Path 2] Complex Mode 흐름 (Orchestrator -> Workers -> Synthesizer)
    workflow.add_edge("orchestrator", "workers")
    workflow.add_edge("workers", "synthesizer")
    workflow.add_edge("synthesizer", END)
    
    # Synthesizer -> END
    workflow.add_edge("synthesizer", END)

    return workflow.compile()

# MCP AI Agent: System Architecture & Prompts Deep-Dive

이 보고서는 `mcp-ai-agent`의 내부 로직, 특히 각 단계에서 사용되는 **System Prompt**와 상세 구현 메커니즘을 심증 분석합니다.

> 이 문서는 코드/프롬프트 심화 문서입니다. 현재 운영 기준 문서는 [`mcp-api-agent/DOCS_MAP.md`](../mcp-api-agent/DOCS_MAP.md), [`mcp-api-agent/DEPLOYMENT_GUIDE.md`](../mcp-api-agent/DEPLOYMENT_GUIDE.md)입니다.

---

## 1. 상태 관리 (State Management)

에이전트는 LangGraph의 `AgentState`를 통해 모든 노드 간의 데이터를 공유합니다.

*   **messages**: 대화 기록 (LangChain Message 객체 배열). 현재 버전에서는 실제 보존 개수가 `RUNTIME_LIMITS`에 의해 조정될 수 있습니다.
*   **mode**: "SIMPLE" 또는 "COMPLEX" 라우팅 결과.
*   **worker_plans**: 조율자(Orchestrator)가 전문가(Worker)에게 내린 JSON 지시서.
*   **worker_results**: 각 전문가가 도구를 실행하고 요약한 보고서들의 리스트.

---

## 2. 노드별 상세 로직 및 시스템 프롬프트

### 🔄 Router Node
**목적**: 효율적인 리소스 사용을 위한 경로 결정.
*   **Prompt**: 
    > "SIMPLE": 특정 단일 리소스의 단순 조회... (예: 파드 목록 줘)
    > "COMPLEX": 복합 추론, 원인 분석, 에러 해결... (예: 전반적으로 진단해줘)

### 🛠️ Simple Agent Node
**목적**: 빠른 즉답 및 단일 도구 실행.
*   **System Prompt 핵심**:
    > "당신은 빠르고 정확한 K8s 및 Observability 관리자입니다... 생각하지 말고 바로 도구를 호출하세요. 무조건 한국어로 대답하세요."
*   **특이사항**: `bind_tools`를 통해 모든 MCP 도구에 직접 접근 가능.

### 🧠 Orchestrator Node (지휘자)
**목적**: 복잡한 문제를 분해하고 적절한 전문가에게 위임.
*   **System Prompt 핵심**:
    > "직접 문제를 해결하려 하지 말고, '어떤 정보를 수집해야 하는지' 계획을 세워 위임하세요. 전반적인 진단 시 반드시 K8s, Log, Metric 3명의 전문가를 모두 호출하세요."
*   **Output**: JSON 형식 (`{"log": "...", "metric": "...", "k8s": "..."}`)

### 👷 Worker Node (전문가)
**목적**: 할당된 전용 도구만 사용하여 심층 분석 및 요약.
*   **분야별 특화 가이드**:
    *   **LogSpecialist**: `vlogs_query` 시 `| collapse_nums` 사용 및 `limit: 50` 권장.
    *   **MetricSpecialist**: `topk(10, ...)` 사용 강제, PromQL에 `| limit` 사용 금지 경고.
    *   **K8sSpecialist**: `output="name"` 등을 사용한 데이터 최소화 전략.
*   **Sub-Agent Summarization**: 도구 결과(Raw Data)가 너무 클 경우, LLM이 1차적으로 핵심 팩트(에러 문구, 스택 트레이스 등)만 추출하여 요약본 작성.

### 📝 Synthesizer Node (종합가)
**목적**: 모든 전문가의 보고서를 논리적으로 엮어 최종 답변 생성.
*   **System Prompt 핵심**:
    > "K8s(기반) -> Metric(현상) -> Log(원인) 순서로 중요도를 배치하세요. '[빈 결과 반환...]'은 장애가 아니라 클러스터가 건강하다는 뜻임을 명심하세요."

---

## 3. 고급 구현 메커니즘 (Advanced Logic)

### 🚫 루프 및 중복 방지 (Loop Prevention)
`check_and_filter_duplicate_tools` 함수는 AI가 동일한 도구를 동일한 인자로 반복 호출하는 것을 차단합니다.
```python
if new_tc["name"] == old_tc["name"] and new_tc["args"] == old_tc["args"]:
    is_dup = True
```

### ✂️ 데이터 절단 관리 (Truncation Strategy)
네트워크 버퍼(ENOBUFS) 오류와 LLM 컨텍스트 초과를 막기 위해 다중 레이어 절단 전략을 사용합니다.
1.  **MCP Level**: `call_mcp_tool`에서 10,000자 초과 시 절단.
2.  **Worker Level**: 요약 전 Raw Data가 8,000자 초과 시 핵심(뒷부분 등) 위주로 보존.
3.  **Synthesizer Level**: 전체 취합본이 10,000자 초과 시 최종 절단.

### ⚡ 병렬 실행 및 동시성 제어
`asyncio.gather`를 통해 전문가들을 동시에 실행하되, `asyncio.Semaphore(2)`를 사용하여 API Rate Limit을 보호합니다.

---

## 4. MCP 통신 상세 (`mcp_client.py`)

*   **Keep-Alive**: SSE 연결 유지를 위해 45초마다 `ping`을 전송하는 백그라운드 태스크 실행.
*   **Dynamic Pydantic Model**: `create_model`을 사용하여 서버의 `inputSchema`를 런타임에 클래스로 변환. 이는 LangChain이 도구 인자를 정확히 검증하게 해줍니다.
*   **Namespace 적용**: 여러 서버의 도구가 섞이지 않도록 `server_name` + `tool_name` 형식을 사용합니다.

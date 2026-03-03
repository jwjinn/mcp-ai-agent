# 🧠 1. State Management & Graph Lifecycle (심화)

이 문서는 `agent_graph.py` 내부에서 LangGraph가 어떻게 상태(State)를 관리하고, 메모리 한계(Context Window)를 어떻게 수학적으로 제어하는지 파고드는 **시니어 엔지니어 및 코어 개발자**를 위한 문서입니다.

---

## 🏗️ 1. AgentState의 해부학 (Anatomy of `AgentState`)

LangGraph의 핵심은 모든 노드(Node)가 공유하는 **상태 객체(State Object)**입니다. 우리 시스템의 `AgentState`는 단순한 변수 모음이 아니라, **Reducer** 규칙에 의해 생명주기가 관리됩니다.

```python
class AgentState(TypedDict):
    # BaseMessage의 List를 누적(Append)하는 Reducer
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 덮어쓰기(Overwrite) 
    mode: str 
    
    # 덮어쓰기(Overwrite): Orchestrator가 작성한 JSON 지시서
    worker_plans: Dict[str, str]
    
    # [핵심] 병렬 Worker들이 던진 요약본이 'append' 형태가 아님.
    # Worker 단계 진입 시 초기화되고 덮어씌워짐.
    worker_results: List[str] 
```

**[🔥 설계 의도 분석]**
*   `messages`는 사용자와 AI가 나눈 대화를 계속 쌓아야 하므로 LangGraph의 내장 리듀서인 `add_messages`를 사용합니다.
*   반면 `worker_results`가 누적(Append)이 아닌 단순 `List[str]` (기본 Reducer=Overwrite) 인 이유가 중요합니다. 만약 누적으로 설계했다면, 첫 번째 질문의 요약본과 두 번째 질문의 요약본이 섞여서 Synthesizer가 과거의 에러를 현재 에러로 착각(Hallucination)하게 됩니다. **Worker 노드가 실행될 때마다 이전 라운드의 결과물은 완벽히 휘발(Overwrite)되어야 합니다.**

---

## ✂️ 2. Smart Sliding Window (토큰 폭발 방어 알고리즘)

AIOps 환경에서 시스템 프롬프트는 매우 길고, 에러 로그는 더 깁니다. 대화가 10턴만 넘어가도 128K 짜리 Context Window가 터져버립니다.
이를 막기 위해 `trim_messages_history` 함수가 개입합니다.

```python
def trim_messages_history(messages: list, keep_last: int = 15):
    """
    시스템 메시지는 무조건 보존하고, 최근 N개의 대화만 슬라이싱.
    """
    if len(messages) <= keep_last:
        return messages

    # [핵심 로직] index 0번(System Message)은 절대로 지우면 안 됨!
    system_msg = None
    if messages and isinstance(messages[0], SystemMessage):
        system_msg = messages[0]

    # 최근 N개의 대화만 자르기 (음수 인덱싱 활용)
    recent_messages = messages[-keep_last:]

    # [보정 로직] 슬라이싱된 N개의 대화 중 첫 번째가 ToolMessage 라면 고아(Orphan)가 됨.
    # LLM은 AIMessage(tool_call) 없이 ToolMessage만 등장하면 API 에러를 뱉으므로 보정 필요.
    if recent_messages and isinstance(recent_messages[0], ToolMessage):
        recent_messages = recent_messages[1:]

    # 시스템 메시지 결합 및 반환
    if system_msg and recent_messages and not isinstance(recent_messages[0], SystemMessage):
        return [system_msg] + recent_messages
        
    return recent_messages
```

**[🔥 설계 의도 분석]**
이 함수의 진짜 어려운 점은 **"고아 메시지(Orphan Message) 처리"**입니다.
만약 `[0] System`, `[1] User`, `[2] AI(tool_call)`, `[3] Tool(Result)` 상태에서 최근 1개(`keep_last=1`)만 자르면 어떻게 될까요?
`[3] Tool(Result)`만 LLM으로 넘어갑니다. 하지만 OpenAI 규격(Qwen 포함) 상, **도구를 부른 직전의 AI 메시지가 없는데 도구 결과만 존재하면 `400 Bad Request` 에러를 던집니다.**
따라서 위 코드에서는 자른 리스트의 첫 요소가 `ToolMessage`면 과감히 그 결과값의 생명주기를 폐기처분(`recent_messages[1:]`) 해버리는 안전장치가 들어있습니다.

---

## 🔀 3. Routing Edges (다이내믹 조건부 흐름 제어)

Router 노드의 대답 텍스트에 따라, Graph는 실행 시간에 경로를 틀어버립니다.

```python
def route_decision(state: AgentState) -> Literal["simple", "orchestrator"]:
    # 상태에 주입된 mode 값을 단순히 읽어옴
    mode = state.get("mode", "SIMPLE").strip().upper()
    if mode == "COMPLEX":
        return "orchestrator"
    return "simple"
```

그래프 컴파일 시 우리는 이 반환값 문자열을 다음 노드의 이름과 매핑합니다.
```python
workflow.add_conditional_edges(
    "router",
    route_decision,
    {
        "simple": "simple",
        "orchestrator": "orchestrator"
    }
)
```
이 방식의 장점은 비즈니스 로직(mode 판단)은 `router_node` 안에 순수 파이썬 로직으로 캡슐화되어 있고, Graph는 그저 문자열 티켓만 검사하며 다음 역으로 보내는 철저한 **SoC (Separation of Concerns, 관심사 분리)**가 이뤄져 있다는 점입니다.

---
👉 **[이전으로 돌아가기 (초보자용 2장: 아키텍처 개요)](../paper/2_CORE_ARCHITECTURE.md)**

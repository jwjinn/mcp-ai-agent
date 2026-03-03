# 👨‍💻 3. 코드 투어 (CODE WALKTHROUGH)

앞서 2장에서 본 멋진 "조직도"가 코드로 어떻게 짜여 있는지 궁금하지 않으신가요? 
이번 장에서는 프로젝트의 핵심 심장인 **3개의 방(파일)**을 페어 프로그래밍 하듯이 한 줄 한 줄 쉽게, 하지만 뼈대 위주로 짚어 드리겠습니다.

---

## 🚪 첫 번째 방: `agent_graph.py` (조직의 뇌)

이 파일은 2장에서 보여드린 **"직원들의 업무 흐름(Node와 Graph)"**을 통째로 구워낸 가장 중요한 파일입니다.

**어떻게 생겼을까요?** 크게 4구역으로 나눌 수 있습니다!

### 1️⃣ 구역 1: 직원들이 주고받는 "서류철" 정의 (State)
```python
class AgentState(TypedDict):
    messages: list          # 우리가 주고받은 대화(질문, 답변, 직원의 생각)
    mode: str               # "지금은 단순업무!(SIMPLE)" / "초비상! 팀장 출동!(COMPLEX)"
    worker_plans: dict      # 팀장(Orchestrator)이 각 워커(Log, K8s)에게 내리는 지시서
    worker_results: list    # 워커들이 도구를 쓰고 요약해온 요약본 3장 (매우 중요)
```
이 서류철(`AgentState`)은 직원들(Node)끼리 바통 터치를 할 때마다 건네주는 공통 결재판입니다. 첫 직원이 `plan`을 적으면 다음 직원이 그걸 보고 일합니다.

### 2️⃣ 구역 2: 2가지 뇌(두뇌) 장착하기
```python
def get_instruct_model():
    return ChatOpenAI(...) # 명령만 정확하게 내리는 "이성적인 뇌"

def get_thinking_model():
    return ChatOpenAI(stream_prefix="<think>") # 깊게 원인을 분석하는 "천재 탐정의 뇌"
```
2장에서 배웠죠? 여기서 2개의 AI 모델 뇌를 정의하고 시작합니다. 나중에 필요한 순간마다 다른 뇌를 불러와 씁니다.

### 3️⃣ 구역 3: 각 직원들의 업무 함수 (Node)
이 방에는 각각의 직원들이 하는 일이 파이썬 함수로 짜여 있습니다.
*   `router_node()`: 안내데스크 역할. 사용자의 첫 질문을 보고 서류철에 `mode="SIMPLE"` 또는 `mode="COMPLEX"` 도장을 쾅 찍습니다. (지시 뇌 사용)
*   `orchestrator_node()`: 팀장 역할. `COMPLEX` 도장이 찍힌 서류를 받으면, k8s/vlogs/vm 팀에게 "너는 이거하고, 너는 저거해라"를 JSON으로 작성하여 `worker_plans` 서류철에 철해둡니다. (포맷이 생명이니 지시 뇌 사용)
*   `workers_node()`: 🔥**파워 병렬 처리방**🔥입니다. 팀장의 지시서를 보고 `asyncio.gather`라는 파이썬의 비동기 마법을 써서 3명의 직원이 **"동시에"** 도구를 실행합니다. 그리고 `sub-agent summarizer(요약 요정)`가 에러 팩트만 남겨 1,000자 요약본(`worker_results`)을 만듭니다.
*   `synthesizer_node()`: 최종 탐정. 3장의 `worker_results` 요약본만 싹 받아서, 드디어 **<think>** 뇌(탐정 두뇌)를 켭니다! 그리고 "최종 결론: DB가 죽었소"를 대답합니다.

### 4️⃣ 구역 4: 직원들 연결하기 (Graph 빌드)
```python
def create_agent_app(tools):
    workflow = StateGraph(AgentState)
    
    # 직원 채용(Node 추가)
    workflow.add_node("router", router_node)
    workflow.add_node("orchestrator", orchestrator_node) ...

    # 결재선 연결(Edge 추가)
    workflow.add_edge("START", "router")
    
    # 조건부 결재선 (Router의 판단에 따라 경로가 슝! 나뉨)
    workflow.add_conditional_edges("router", route_decision)
    # ... (K8s 요약본, Log 요약본) -> Synthesizer -> END
    
    return workflow.compile()
```
이 마지막 부분이 방금 만든 직원들의 책상을 화살표로 엮어주는 "LangGraph" 빌드 과정입니다.

---

## 🚪 두 번째 방: `api_server.py` (외부와 소통하는 서비스 창구)

아무리 훌륭한 AI 회사를 차렸어도 밖(웹, 스마트폰, 다른 프로그램)에서 질문을 던질 창구가 없다면 무용지물입니다.
그래서 **FastAPI**라는 엄청나게 빠른 파이썬 웹 프레임워크를 썼습니다.

### 1️⃣. `react_flow_stream_endpoint`
이건 개발자들이 예쁜 대시보드(리액트 화면)에서 "야 셜록 홈즈가 지금 생각 중이래! / 오 요약 요정이 일을 끝냈대!" 라는 **에이전트의 내부 진행 상황(상태)을 실시간 화살표 반짝임으로 보기 위해** 만들어둔 특별한 통신 창구입니다. 글자뿐만 아니라 Node 이름과 Status를 Data Stream이란 특별한 방식으로 쏴줍니다.

### 2️⃣. `openai_compatible_endpoint` (범용 API)
하지만 세상에는 이미 OpenWebUI나 로컬 채팅앱 같은 게 많습니다. 이런 애들은 `react_flow...` 같은 특수 포맷을 거부합니다. 
그래서 ChatGPT가 답변을 줄 때 쓰는 **"OpenAI의 국제 표준 통신 규격(v1/chat/completions)"**을 완벽하게 흉내 내는 창구를 뚫었습니다. 이 API 하나면 세상 어떤 채팅앱이든 우리 에이전트와 완벽하게 붙일 수 있습니다. *(스트리밍 답변 기능 기본 탑재!)*

---

## 🚪 세 번째 방: `mcp_client.py` (도구 무기고)

가장 신박한 부분 중 하나입니다.
우리의 셜록 홈즈나 워커들은 도구를 "직접" 만들지 않았습니다.
우리는 `mcp_client.py` 를 통해 **MCP 규약(Model Context Protocol)**을 따르는 외부의 무기고(서버)들과 손을 잡습니다.

*   **`refresh_tools` 함수**: 에이전트가 눈을 뜨면(서버 기동), 무기고 서버에 전화를 겁니다. "여보세요, 거기서 쓸 수 있는 도구 목록 좀 문자로 보내주세요." 
*   **동적 생성 마법 (`pydantic.create_model`)**: 놀랍게도 그 문자를 받은 파이썬은, 그동안 세상에 없던 새로운 함수의 규칙(Schema)을 **실행되는 도중에 "동적으로"** 뽑아 만들어냅니다! 즉 외부 K8s 팀이 도구 1개를 추가하면, 우리 에이전트는 코드 수정 없이 그냥 그 새로운 도구를 뚝딱 쓸 수 있습니다!

---

## 🎯 다음 장으로 넘어가며...

이 세 파일의 흐름만 알아도, 개발자분들은 이 거대하고 스마트한 AIOps 백엔드 프로그램의 "뼈대"를 완벽히 이해하신 겁니다. "나머지는 살을 붙이는 것뿐"이죠!

자, 눈으로만 보니까 손가락이 조금 심심하시죠? 다음 장 `4_HOW_TO_START_AND_TEST.md`에서는 **아무것도 없는 빈 깡통 컴퓨터에서 어떻게 이 에이전트 서버를 켜서 셜록 홈즈와 채팅을 나눌 수 있는지** "가장 친절한 실전 세팅 가이드"를 제공하겠습니다! 👉

> 💡 **조금 더 기술적으로 깊은 이야기를 원하시나요?**
> * 🏗️ [LangGraph의 핵심, State 관리와 메모리 슬라이딩 윈도우 뜯어보기](../advanced_docs/1_STATE_MANAGEMENT_AND_GRAPH.md)
> * 🔌 [도구(Schema)를 런타임에 동적으로 찍어낸다고? MCP 다이내믹 바인딩의 마법](../advanced_docs/3_MCP_CLIENT_DYNAMIC_BINDING.md)

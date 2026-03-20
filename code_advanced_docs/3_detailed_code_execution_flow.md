# MCP AI Agent: 상세 코드 실행 흐름 및 시스템 프롬프트 분석

이 문서는 사용자의 질문이 입력된 순간부터 시스템 내부의 함수와 변수들이 어떻게 값을 주고받으며, 최종 답변을 생성해 내는지 **실제 코드 레벨에서 단계별로 추적**합니다.

> 이 문서는 상세 코드 흐름 심화 문서입니다. 현재 운영 문서와 설정 키 설명은 [`mcp-api-agent/DOCS_MAP.md`](../mcp-api-agent/DOCS_MAP.md), [`mcp-api-agent/DEPLOYMENT_GUIDE.md`](../mcp-api-agent/DEPLOYMENT_GUIDE.md)를 참고하세요.

---

## 1. 서버 기동 및 MCP 도구 초기화 (Initialization)

프로그램이 시작되면 가장 먼저 외부 모니터링 시스템(Kubernetes, VictoriaLogs 등)과 연결을 맺고 "사용 가능한 도구"를 LangChain이 이해할 수 있는 형태로 준비해야 합니다. 이 작업은 `main.py` (또는 `api_server.py`)의 전역 초기화와 `mcp_client.py`에서 이루어집니다.

### 1-1. 클라이언트 생성 및 연결 (`api_server.py`의 `lifespan` / `main.py`)
애플리케이션은 현재 `config.py`가 읽어들인 설정값(`config.json` + env override)을 바탕으로 `MCP_SERVERS` 배열을 순회하며 `MCPClient` 객체를 생성합니다.

```python
# main.py 발췌
clients = []
all_tools = []

for server_conf in MCP_SERVERS:
    client = MCPClient(server_conf["name"], server_conf["url"])
    await client.connect() # MCP 서버에 SSE 연결
    clients.append(client)
    all_tools.extend(client.tools) # 서버가 제공하는 도구들을 전역 리스트에 추가
```

### 1-2. 도구의 동적 로딩 (`mcp_client.py` -> `refresh_tools()`)
이 프로그램의 핵심 기능 중 하나는 **외부 MCP 서버의 도구 스키마를 동적으로 Python 코드화**하는 것입니다.

```python
# mcp_client.py 내부
async def refresh_tools(self):
    # 1. 서버에 도구 목록 요청
    mcp_tools_list = await self.session.list_tools()
    
    for tool in mcp_tools_list.tools:
        # 2. JSON Schema 분석
        schema = tool.inputSchema
        properties = schema.get("properties", {})
        
        fields = {}
        for prop_name, prop_schema in properties.items():
            # ... 타입 매핑 (string -> str, integer -> int 등) ...
            fields[prop_name] = (py_type, ...) # Pydantic 필드 속성 정의
        
        # 3. Pydantic 모델을 런타임에 동적으로 생성 (!매우 중요!)
        # 이름 충돌 방지를 위해 접두사(self.name)를 붙임 예: "k8s_k8s_kubectl_get_input"
        InputModel = create_model(f"{self.name}_{tool.name}_input", **fields)
        
        # 💡 [왜 필수적인가? (Why?)]
        # LangChain의 LLM은 도구를 사용할 때 "어떤 인자(Arguments)가 어떤 타입으로 필요한지"를 
        # 명확히 알아야 합니다. 일반적인 코드라면 미리 정의해두면 되지만, 
        # MCP는 어떤 서버가 어떤 도구를 줄지 런타임에만 알 수 있으므로, 
        # Python의 동적 클래스 생성(create_model)을 이용해 즉석에서 설명서를 찍어내야 합니다.

        # 4. 래퍼 함수 생성: 실제 도구 실행 시 호출됨
        async def _run_tool(tool_name=tool.name, **kwargs):
            clean_args = {k: v for k, v in kwargs.items() if v is not None}
            # 최종적으로 MCP 통신 로직 진행
            return await self.call_mcp_tool(tool_name, clean_args)
            
        # 5. LangChain의 StructuredTool로 변환하여 에이전트가 사용할 수 있게 만듦
        namespaced_tool_name = f"{self.name}_{tool.name}"
        langchain_tool = StructuredTool.from_function(
            func=None,
            coroutine=_run_tool,
            name=namespaced_tool_name,
            description=f"[{self.name}] {tool.description[:1000]}",
            args_schema=InputModel
        )
        self.tools.append(langchain_tool)
```

---

## 2. 그래프 조립 (`agent_graph.py` -> `create_agent_app`)

위에서 확보한 `all_tools` 리스트를 기반으로, 데이터가 흐를 파이프라인(LangGraph)을 구축합니다.

```python
# agent_graph.py
def create_agent_app(tools: list):
    workflow = StateGraph(AgentState) # 상태 저장소
    
    # 노드들(함수들) 추가
    workflow.add_node("router", router_node)
    workflow.add_node("simple_agent", simple_agent_wrapper)
    workflow.add_node("orchestrator", orchestrator_wrapper)
    workflow.add_node("workers", workers_wrapper)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("tools", ToolNode(tools)) # Simple Mode용 표준 도구 실행기
    
    # 엣지 연결 (실행 순서 정의)
    workflow.add_edge(START, "router")
    
    # 🌟 라우팅 로직 분기점
    def route_decision(state):
        if state and state.get("mode") == "complex":
            return "orchestrator"
        return "simple_agent"
        
    workflow.add_conditional_edges("router", route_decision)
    
    # [Complex 패스] Orchestrator -> Workers -> Synthesizer -> END
    workflow.add_edge("orchestrator", "workers")
    workflow.add_edge("workers", "synthesizer")
    workflow.add_edge("synthesizer", END)
    
    return workflow.compile()
```

---

## 3. 사용자 요청 처리 시작 (Request Handling)

사용자가 API를 통해 질문을 던집니다. (`api_server.py`)

```python
# api_server.py
@app.post("/api/stream_chat")
async def react_flow_stream_endpoint(request: Request):
    # 사용자의 텍스트를 뽑아옵니다.
    user_input = messages[-1]["content"] if messages else data.get("message", "")
    
    # LangGraph에 전달할 초기 상태(입력값) 세팅
    inputs = {"messages": [HumanMessage(content=user_input)]}
    
    # 백그라운드 태스크로 그래프 실행 시작
    async for event in agent_app.astream(inputs):
        # ... 실시간 로그 송출 로직 ...
        pass
```

---

## 4. 노드별 세부 동작 흐름 (`agent_graph.py`)

이제 `inputs`가 LangGraph 파이프라인을 타고 노드(함수)들을 거쳐갑니다. 함수의 `state` 변수는 각 단계를 거치며 업데이트됩니다.

### 4-1. Router Node (`router_node`)
사용자의 질문 난이도를 판단합니다.

> **💡 [왜 분기해야 하는가? (Why?)]**
> 파드 하나의 상태를 묻는 단순한 질문에 지휘자와 3명의 전문가를 모두 깨우는 것은 **막대한 토큰 낭비와 응답 속도 저하**를 일으킵니다. 따라서 가벼운 모델로 질문의 복잡도를 먼저 파악하여, 쉬운 문제는 `Simple Agent`로 빠르게 직행시켜 속도(Latency)와 비용을 최적화하는 것입니다.

*   **입력 변수**: `state["messages"][-1].content` (예: "결제 파드에서 왜 에러가 나는거야?")
*   **LLM에게 전달되는 Prompt 원문**:
```text
당신은 사용자 의도를 분류하는 AI입니다.
사용자의 질문이 다음 중 어디에 해당하는지 단답형으로 대답하세요.

1. "SIMPLE": 특정 단일 리소스의 단순 조회 또는 단일 도구로 즉시 답변 가능한 경우 (예: aaa 파드 목록 줘, 현재 시간 알려줘, 클러스터 CPU 상위 3개 파드 알려줘)
2. "COMPLEX": 복합적인 추론이 필요하거나, 원인 분석(Diagnosis), 에러(Error) 해결, 여러 단계의 도구 사용이 필요한 경우. 특히 "전반적으로 진단해줘" 와 같은 포괄적 분석 요청은 COMPLEX로 분류하되, "전체 클러스터에서 CPU 점유율 상위 3개 알려줘"와 같이 단순히 랭킹/통계만 묻는 경우에는 단일 도구(`vm_query`)로 즉시 조회가 가능하므로 "SIMPLE"로 분류하세요.

[사용자 질문]
{last_msg.content}

[응답 형식]
오직 "SIMPLE" 또는 "COMPLEX"라고만 대답하세요.
```
*   **처리 결과**: LLM이 "COMPLEX"라고 대답하면, `return {"mode": "complex"}` 시그널을 반환하여 앞서 정의된 `add_conditional_edges`를 통해 흐름이 `Orchestrator`로 이동합니다.

### 4-2. Orchestrator Node (`orchestrator_node`)
복잡한 작업을 하위 전문가(Workers)들에게 나누어주는 계획(Plan)을 세웁니다.

> **💡 [왜 지휘자가 필요한가? (Why?)]**
> LLM에게 한 번에 20개가 넘는 도구들을 통째로 주어주면, LLM은 **"도구 혼동(Tool Confusion)"** 에 빠져 엉뚱한 도구를 쓰거나 환각(Hallucination)을 일으킵니다. 이를 방지하기 위해 문제를 쪼개서(Divide & Conquer), 각각 로그, 메트릭, 명세서만 보는 **"전문가 페르소나"** 를 부여하여 작업의 정확도를 극대화하는 패턴입니다.

*   **LLM에게 전달되는 Prompt 원문 (부분 발췌)**:
```text
당신은 AIOps 시스템의 '지휘자(Orchestrator)'입니다.
사용자의 요청을 해결하기 위해 하위 전문가(Worker)들에게 작업을 지시해야 합니다.
직접 문제를 해결하려 하지 말고, "어떤 정보를 수집해야 하는지" 계획을 세워 위임하세요.

[하위 전문가 목록]
1. **LogSpecialist** (Logs): 로그 분석 전문가.
    - 팁: 에러(`level:error`)만 보지 말고, 경고나 'cannot', 'fail' 같은 핵심 키워드를 함께 조회. ...
2. **MetricSpecialist** (Metrics/Traces): 메트릭 및 트레이스 분석 전문가.
3. **K8sSpecialist** (K8s Config): K8s 설정 및 리소스 조회 전문가.

[출력 예시]
```json
{
    "log": "backend-api의 최근 1시간 에러 로그를 조회해서 원인을 파악해.",
    "metric": "해당 파드의 메모리 사용량이 급증했는지 확인해.",
    "k8s": "최근 배포된 이미지 태그와 Deployment 설정을 확인해."
}
```
```
*   **코드 실행 내역**: 
    LLM이 JSON을 반환하면, 정규식과 `json.loads`를 이용해 파싱합니다.
    파싱된 딕셔너리는 `worker_plans` 변수에 저장되어 다음 노드로 넘어갑니다.
    ```python
    worker_plans = json.loads(json_str)
    return {"worker_plans": worker_plans, "messages": [...]}
    ```

### 4-3. Workers 실행 (`workers_node` -> `run_single_worker`)
지휘자가 만든 `worker_plans`를 바탕으로 **LLM 전문가들이 동시에 서로 다른 도구를 들고 일합니다.**

```python
# workers_node 함수 내부
tasks = []
if plans.get("log"):
    # 로그 분석 도구(vlogs_*)들만 추려냄
    log_tools = filter_tools(tools, "log")
    tasks.append(run_single_worker("LogSpecialist", plans["log"], log_tools))

# ... Metric과 K8s도 동일하게 작업 추가 ...

# 병렬 실행 (Rate Limit 보호를 위해 한 번에 최대 2개씩만)
sem = asyncio.Semaphore(2)
# 모든 태스크를 동시에 실행하고 결과가 다 모일 때까지 대기
results = await asyncio.gather(*safe_tasks) 

return {"worker_results": results}
```

#### 📌 Worker 내부의 도구 실행 및 요약 (Map-Reduce 메커니즘)
이 프로젝트에서 가장 복잡하고 심혈을 기울인 부분인 `run_single_worker` 함수 내부를 보겠습니다. Worker는 한 번 LLM을 호출해서 도구를 사용하고, 얻은 날것의 데이터(Raw Data)를 **다시 한번 요약**합니다.

1.  **전용 프롬프트 및 도구 호출**:
    ```python
    llm_with_tools = llm.bind_tools(tools)
    response = await llm_with_tools.ainvoke([sys_msg]) # 도구 사용 결정 (예: "k8s_kubectl_get" 써야겠다)
    ```
    
2.  **수동 도구 실행**: (LangChain 표준 `ToolNode`에 의존하지 않고 직접 실행)
    ```python
    tool_outputs = []
    for tc in response.tool_calls:
        # 매칭되는 도구 찾기
        selected_tool = next((t for t in tools if t.name == tc["name"]), None)
        
        # 실제 도구 함수 호출 (여기서 mcp_client.py의 _run_tool -> call_mcp_tool 로 넘어감)
        res = await selected_tool.ainvoke(tc["args"]) 
        tool_outputs.append(f"Output: {res}")
        
    raw_results = "\n\n".join(tool_outputs)
    ```
    
3.  **결과 요약 (Summarization)**:
    수천 줄에 달할 수 있는 `raw_results`를 다음 프롬프트를 통해 1차 압축합니다.
    ```text
    당신은 {worker_name}의 요약 담당자입니다.
    지휘자가 내린 임무: {instruction}
    
    [작업 지시]
    1. 오직 임무에 답하는 데 필요한 핵심 팩트만 <raw_data>에서 추출하세요.
    2. 발견된 에러 문구, 경고, 실패 파드 이름은 절대 누락하지 말고 보존하세요.
    3. 개조식으로 간결하게. 2,000자 이내. 에러 원문은 그대로 보존.
    ```
    이 과정을 거쳐 핵심 정보만 남은 문자열이 `worker_results` 리스트에 담겨 반환됩니다.
    
    > **💡 [왜 각 전문가가 직접 요약하는가? (Why Map-Reduce?)]**
    > 3명의 전문가가 수집한 K8s 설정, 어마어마한 양의 서버 로그, 메트릭 트레이스 결과를 있는 그대로 최종 종합가(Synthesizer) 모델에게 던져주면, LLM의 **컨텍스트 윈도우(최대 글자 수)**를 초과하여 에러가 나거나, 노이즈가 너무 많아 핵심을 놓치게 됩니다.
    > 따라서 각 전문가 단에서 노이즈를 걸러내고 "순수한 징후(Signal)"만 뽑아내는 Map-Reduce 압축 메커니즘이 대규모 클라우드 데이터를 다룰 때 필수적입니다.

### 4-4. Synthesizer Node (`synthesizer_node`)
각 전문가(Worker)가 올려보낸 요약 보고서를 취합하여 최종 답변을 생성합니다.

```python
# 1. 보고서 우선순위 정렬 (K8s -> Metric -> Log)
# 이유: K8s 기본 자원 상태를 베이스로 깔고 -> 수치 변화(Metric)를 본 다음 -> 원인(Log)을 분석하는 것이 논리적임
worker_results_dict = {}
for res in state["worker_results"]:
    if "[K8sSpecialist]" in res: worker_results_dict["k8s"] = res
    # ...
    
# 2. 취합본 생성 (글자 수 제한 가드 포함)
ordered_results = [worker_results_dict["k8s"], worker_results_dict["metric"], worker_results_dict["log"]]
worker_results_str = "\n\n".join(ordered_results)
```

*   **최종 결론 생성 프롬프트 원문**:
```text
당신은 최종 답변을 정리하는 Synthesizer입니다.
Orchestrator가 작업자(Worker)들에게 지시를 내렸고, 그 결과가 아래와 같습니다.

[Worker 실행 결과 보고서]
{worker_results_str}

[작성 규칙]
1. 각 전문가의 분석 결과를 인용하여 논리적으로 설명하세요.
2. 결과를 바탕으로 원인을 진단하고, 해결책을 제안하세요.
3. **핵심 분석 룰**: 도구 실행 결과가 "[빈 결과 반환...]" 형태로 왔다면, 절대 권한 부족이나 통신 장애로 오해하지 마세요! 오류 필터(예: Failed 파드 제한)에 걸리는 안 좋은 리소스가 아예 없어서 클러스터가 매우 건강하다는 뜻입니다. 이를 분석하여 사용자에게 "에러 파드가 하나도 없이 건강하다"고 보고하세요.
4. **추가 건강성 룰**: K8s 전문의 보고서가 단순히 파드 이름 목록만 나열하고 특별한 에러 메시지가 없다면, 그 리소스들은 정상적으로 띄워져 있는 것(Running)으로 확신하고 설명하세요.
```
이 프롬프트를 받은 **Thinking 모델**(DeepSeek-r1이나 QwQ 등 추론 특화 LLM)이 심도 깊은 고민(`.astream`을 통한 실시간 `<think>` 과정)을 끝내면, 완성된 문장이 `AIMessage`에 담기면서 StateGraph가 `END` 상태에 도달합니다.

---

## 5. 실제 도구 프로세스 (`mcp_client.py` -> `call_mcp_tool`)

위 4-3 단계에서 `selected_tool.ainvoke`를 불렀을 때, 그 요청이 최종적으로 K8s 서버나 로그 서버로 넘어가는 구간입니다.

```python
# mcp_client.py 내부
async def call_mcp_tool(self, name: str, arguments: dict) -> str:
    try:
        # 여기서 mcp SDK를 통해 실제 서버(NodeJS 등)로 RPC 호출이 이루어짐
        result: CallToolResult = await self.session.call_tool(name, arguments)
        
        output_text = []
        if result.content:
            for content in result.content:
                if content.type == "text":
                    output_text.append(content.text)
        
        final_output = "\n".join(output_text)
        
        # 🌟 시스템 터짐 방지 로직 (Truncation)
        # 만약 `kubectl get all -A` 등을 쳐서 어마어마한 텍스트가 반환되면 
        # Python 메모리가 터지거나 LLM의 Input Token 제한을 가볍게 넘어갑니다.
        MAX_OUTPUT_LENGTH = 10000 
        if len(final_output) > MAX_OUTPUT_LENGTH:
            # 10,000자로 강제 컷오프!
            final_output = final_output[:MAX_OUTPUT_LENGTH] + \
                f"\n... (⚠️ Output truncated by {len(final_output) - MAX_OUTPUT_LENGTH} chars. Use specific filters to see more.)"
        
        # 💡 [왜 잘라내야 하는가? (Why?)]
        # K8s나 VictoriaLogs는 매우 방대한 시스템입니다. 실수로 필터를 잘못 넣은 쿼리 하나가 수 메가바이트의 텍스트를 반환할 수 있습니다.
        # 이를 LLM에 밀어넣으면 즉시 "최대 초과 에러(Rate Limit 혹은 Context Limit)"가 발생하여 전체 시스템이 뻗어버립니다. 
        # 이를 막는 가장 원초적이고 강력한 방어막입니다.
                
        return final_output
        
    except Exception as e:
        error_str = str(e)
        # 네트워크 소켓 버퍼 한계치 에러 대응
        if "ENOBUFS" in error_str:
            return "❌ [System Limit] ENOBUFS: 데이터가 너무 많습니다. 범위를 좁히세요."
        return f"Error executing {name}: {error_str}"
```
이로써 MCP 호출이 마무리되고 그 반환 텍스트가 LangGraph의 Worker로 돌아가 요약에 사용됩니다.

---

이 거대한 파이프라인 덕분에, 단순한 질문-답변 봇이 아니라, **"질문 해석 -> 업무 분담 -> 분산 병렬 작업(도구 실행) -> 보고서 취합 및 요약 -> 최종 종합 분석 및 제안"** 이라는 완벽한 엔터프라이즈 레벨의 다중 에이전트 워크플로우를 완벽하게 수행합니다.

# 🔌 3. MCP Dynamic Schema Binding (심화)

이 문서는 코어 파이썬(Core Python)의 강력 기능 중 하나인 **런타임 메타프로그래밍(Runtime Metaprogramming)** 기법이 `mcp_client.py`에서 Model Context Protocol(MCP) 서버의 도구(Tool)들을 어떻게 LangChain의 스키마로 형변환(Casting)하는지 다루는 고급 문서입니다.

---

## 🎭 1. Dynamic Schema Builder (메타프로그래밍)

AIOps의 특성상 우리는 K8s, Logs 등 별도의 Go/Node.js로 짜여진 수많은 MCP 원격 서버들과 통신해야 합니다.
**문제는, 런타임 이전(코드를 짜는 시점)에는 저쪽 서버에 파라미터가 뭐가 있는지 파이썬이 알 방도가 없다는 점입니다.**
하지만 LangChain에 도구를 인식시키려면 엄격한 Pydantic BaseModel (Schema)가 코드상에 존재해야만 LLM이 `tool_calls` 인자를 제대로 맞춰서 내려줍니다.

### 🛠️ Pydantic `create_model`의 강림
`mcp_client.py`의 `refresh_tools` 메서드는 서버 접속 직후 한 번 호출되어, JSON 스키마 명세서를 받아 실시간 메모리 상에 파이썬 클래스(Class)를 직조(Weaving)해냅니다.

```python
async def refresh_tools(self):
    # mcp_tools_list는 원격 SSE 통신으로 가져온 JSON 응답 객체입니다.
    mcp_tools_list = await self.session.list_tools()

    for tool in mcp_tools_list.tools:
        # [1] JSON Schema 파싱
        schema = tool.inputSchema
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        fields = {}
        for prop_name, prop_schema in properties.items():
            # [2] JSON Type -> Python Type 매핑
            py_type = Any
            if prop_schema.get("type") == "string": py_type = str
            elif prop_schema.get("type") == "integer": py_type = int
            elif prop_schema.get("type") == "boolean": py_type = bool

            # [3] 필드 정의 (타입, 기본값 생성)
            # Tuple: (Type, value_or_ellipsis) - Ellipsis(...)는 Pydantic에서 "필수값"을 의미
            if prop_name in required:
                fields[prop_name] = (py_type, ...)
            else:
                fields[prop_name] = (py_type, None)
        
        # [핵심] Pydantic 동적 모델 생성 (메타 프로그래밍)
        # 런타임에 메모리에 "class K8s_get_pods_input(BaseModel): ..." 형태가 짠! 하고 생겨납니다.
        InputModel = create_model(f"{self.name}_{tool.name}_input", **fields)

        # [4] LangChain StructuredTool로 포장 (Namespace 추가)
        # ...
```

**[🔥 아키텍처적 의의]**
하드코딩(Hard-coding)된 Pydantic 클래스가 없으므로, 원격 K8s MCP 서버 개발자가 도구의 인자(파라미터)를 내일 당장 바꿔도 **우리 에이전트단의 코드는 단 한 줄도 핫픽스(Hotfix) 할 필요 없이 서버를 재기동(또는 refresh)하는 즉시 완벽한 스펙으로 동기화됩니다.**

---

## 🔒 2. AsyncExitStack과 영속화 세션 관리

SSE(Server-Sent Events) 커넥션은 무한 스트림입니다. 연결이 끊기면 대참사가 일어납니다. 자원(Resource) 반환을 안전하게 보장하기 위해 `try-finally` 블록의 깔끔한 비동기 진화형인 `AsyncExitStack`을 도입했습니다.

```python
class MCPClient:
    def __init__(self, name: str, server_url: str):
        self.exit_stack = AsyncExitStack()
        # ...

    async def connect(self):
        # AsyncExitStack.enter_async_context: 
        # 이 객체가 소멸(cleanup)될 때 알아서 블록을 닫아줍니다. (Resource Leak 우주방어)
        transport = await self.exit_stack.enter_async_context(
            sse_client(self.server_url, sse_read_timeout=3600)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(transport[0], transport[1])
        )
```

이 패턴은 객체지향의 **RAII(Resource Acquisition Is Initialization)** 패턴을 파이썬 비동기 생태계에 모방한 것입니다.

### 💖 Keepalive 매커니즘
SSE의 가장 큰 고질병인 **Idle Timeout (아무런 트래픽이 없으면 로드밸런서/방화벽이 세션을 절단하는 현상)**을 방어하기 위해 하트비트(Heartbeat)를 구현했습니다.

```python
async def _keepalive(self):
    while True:
        await asyncio.sleep(45) # 45초마다 Ping
        if self.session:
            try:
                await self.session.send_ping()
            except Exception:
                pass # Ping 실패는 무시 (진짜 단절은 Adapter의 Call 단에서 재연결 로직이 처리)
```

이 백그라운드 태스크 덕분에 에이전트가 긴 시간 "Thinking"을 하고 있어도 뒷단에 연결된 MCP 서버들과의 네트워크 파이프프라인이 마르지 않고 좀비처럼 유지됩니다.

---
👉 **[이전으로 돌아가기 (초보자용 3장: 코드 쓰윽 훑어보기)](../paper/3_CODE_WALKTHROUGH.md)**

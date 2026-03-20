import asyncio
from contextlib import AsyncExitStack
from typing import TypedDict, Annotated, List, Any

# =================================================================
# [라이브러리 설명]
# mcp: Model Context Protocol의 약자로, AI와 외부 시스템을 연결하는 표준 프로토콜입니다.
# ClientSession: 서버와 대화를 나누는 주인공(클라이언트)입니다.
# StdioServerParameters: (여기선 안쓰지만) 로컬 프로그램을 실행할 때 쓰는 설정입니다.
# sse_client: 웹(HTTP)을 통해 서버와 연결할 때 쓰는 연결 도구입니다.
# =================================================================
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.types import CallToolResult

# =================================================================
# [LangChain 관련 라이브러리]
# =================================================================
from langchain_core.tools import StructuredTool
from pydantic import create_model
from config import RUNTIME_LIMITS

# =================================================================
# 1. MCP Client Adapter 클래스
# -----------------------------------------------------------------
# [표준 패턴] Adapter 패턴
# 왜 쓰는가?: 복잡한 외부 시스템(MCP 서버)과의 통신 로직을 이 클래스 안에 가둬두고(캡슐화),
# 밖에서는 .connect(), .call_tool() 같이 단순한 함수만 쓰기 위함입니다.
# 이렇게 해야 나중에 서버 통신 방식이 바뀌어도 이 클래스만 고치면 됩니다.
# =================================================================
class MCPClientAdapter:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session = None
        # AsyncExitStack: 비동기 연결(네트워크 등)을 안전하게 관리하는 도구입니다.
        # 에러가 나서 프로그램이 멈춰도, 열려있는 연결을 확실하게 닫아줍니다. (리소스 누수 방지 표준)
        self.exit_stack = AsyncExitStack()
        self.tools = []

    async def connect(self):
        """MCP 서버에 연결하는 함수"""
        print(f"🔌 MCP 서버 연결 시도: {self.server_url} ...")
        try:
            # [ SSE 연결 ]
            # sse_client를 사용해 서버와 지속적인 연결 통로(Transport)를 엽니다.
            # enter_async_context는 "이 연결을 사용하는 동안에는 절대 끊지 마"라고 보호막을 치는 것과 같습니다.
            transport = await self.exit_stack.enter_async_context(
                sse_client(self.server_url)
            )
            
            # [ 세션 생성 ]
            # 연결 통로(transport) 위에서 실제로 대화를 나눌 세션(Session)을 만듭니다.
            # ClientSession은 MCP 프로토콜의 규칙들을 처리해줍니다.
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(transport[0], transport[1])
            )
            
            # [ 초기화 ]
            # "안녕? 나 연결됐어. 통신 시작하자."라고 서버에 악수를 청합니다.
            await self.session.initialize()
            print(f"✅ MCP 서버 연결 성공! ({self.server_url})")
            
            # 연결되자마자 도구 목록을 가져옵니다.
            await self.refresh_tools()
            
        except Exception as e:
            print(f"❌ 연결 실패 ({self.server_url}): {e}")
            raise e  # 에러가 나면 숨기지 않고 밖으로 던져서 알립니다.

    async def refresh_tools(self):
        """
        [핵심 로직] 서버에 있는 도구들을 가져와서 LangChain이 이해할 수 있게 변환합니다.
        
        왜 복잡한가?:
        LangChain은 도구를 쓸 때 "입력값의 규칙(Schema)"을 엄격하게 요구합니다.
        하지만 서버에 있는 도구가 뭔지 미리 알 수 없으므로,
        실행 중에(Runtime) 코드로 규칙을 즉석에서 만들어내야 합니다.
        """
        if not self.session:
            raise RuntimeError("Session not initialized")

        # 1. 서버에게 도구 목록 요청 ("메뉴판 주세요")
        mcp_tools_list = await self.session.list_tools()
        self.tools = []

        # 2. 각 도구별로 포장을 새로 합니다.
        for tool in mcp_tools_list.tools:
            # --- [동적 스키마 생성 시작] ---
            # 도구의 설명서(Schema)를 뜯어봅니다.
            schema = tool.inputSchema
            properties = schema.get("properties", {})
            required_fields = schema.get("required", [])

            # Pydantic 모델을 만들기 위한 필드 정보를 수집합니다.
            fields = {}
            for prop_name, _ in properties.items():
                if prop_name in required_fields:
                    # 필수 항목이면: 반드시 값이 있어야 함 (Any, ...)
                    fields[prop_name] = (Any, ...)
                else:
                    # 선택 항목이면: 값이 없으면 None으로 자동 처리해라 (Any, None)
                    # [Why?] AI는 가끔 선택 항목을 빼먹고 요청합니다. 이때 에러가 나지 않게 유연성을 주는 것입니다.
                    fields[prop_name] = (Any, None)
            
            # create_model: 마법 같은 함수입니다.
            # 코드를 미리 짜두지 않아도, 실행 중에 "InputModel"이라는 클래스를 즉석에서 만들어냅니다.
            InputModel = create_model(f"{tool.name}_input", **fields)
            # --- [동적 스키마 생성 끝] ---

            # 3. 도구를 실행할 때 중간에서 가로채는 래퍼(Wrapper) 함수
            async def _run_tool(tool_name=tool.name, **kwargs):
                # [데이터 청소]
                # 값이 None인 친구들은 아예 딕셔너리에서 빼버립니다.
                # 왜?: 어떤 서버는 None 값을 보내면 "이게 왜 들어있어?" 하고 에러를 낼 수 있기 때문입니다.
                clean_args = {k: v for k, v in kwargs.items() if v is not None}
                return await self.call_mcp_tool(tool_name, clean_args)

            # 4. 최종적으로 LangChain이 쓸 수 있는 도구(StructuredTool)로 포장
            # 이렇게 포장하면 AI가 이 도구의 이름, 설명, 입력 규칙을 다 알 수 있게 됩니다.
            langchain_tool = StructuredTool.from_function(
                func=None,  # 동기 함수는 없으므로 None
                coroutine=_run_tool,  # 비동기 함수 등록
                name=tool.name,
                description=tool.description[:1024],  # 설명이 너무 길면 자름 (토큰 절약)
                args_schema=InputModel  # 아까 만든 규칙 적용
            )
            self.tools.append(langchain_tool)
        
        print(f"🛠️  로드된 Tools ({len(self.tools)}개): {[t.name for t in self.tools]}")

    async def call_mcp_tool(self, name: str, arguments: dict, max_retries: int = 1) -> str:
        """
        실제로 도구를 실행하고 결과를 받아오는 함수입니다.
        (네트워크 단절 시 자동 재연결 로직 포함)
        """
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"🔄 [MCP Reconnect] 서버와의 통신이 끊어졌습니다. 자동 재연결을 시도합니다... ({attempt}/{max_retries})")
                try:
                    await self.cleanup()
                except Exception:
                    pass
                from contextlib import AsyncExitStack
                self.exit_stack = AsyncExitStack()
                try:
                    await self.connect()
                except Exception as ce:
                    print(f"❌ [MCP Reconnect Failed] 재연결 실패: {ce}")
                    return f"Error executing tool {name} (Reconnect Failed): {str(ce) or repr(ce)}"

            if attempt == 0:
                print(f"\n🚀 [MCP Call] {name} 실행... Args: {arguments}")
            else:
                print(f"🚀 [MCP Call] {name} 재실행... Args: {arguments}")

            try:
                # MCP 클라이언트에게 "이 도구 실행해줘"라고 명령
                result: CallToolResult = await self.session.call_tool(name, arguments)
                
                # 결과 처리
                output_text = []
                if result.content:
                    for content in result.content:
                        if content.type == "text":
                            output_text.append(content.text)
                
                final_output = "\n".join(output_text)
                
                # [최적화] Tool Output Truncation (토큰 폭탄 방지)
                max_output_length = RUNTIME_LIMITS["mcp_tool_max_output_chars"]
                if len(final_output) > max_output_length:
                    truncated_len = len(final_output) - max_output_length
                    final_output = final_output[:max_output_length] + \
                        f"\n... (⚠️ Output truncated by {truncated_len} chars. Use specific filters to see more.)"
                    print(f"✂️ [Truncation] 결과가 너무 길어 잘랐습니다. ({len(final_output)} chars)")

                print(f"✅ [MCP Result] 성공 (길이: {len(final_output)})")
                return final_output
            except Exception as e:
                error_str = str(e) or repr(e)
                
                # [에러 핸들링 강화] 애플리케이션 레벨 에러는 즉시 반환
                if "ENOBUFS" in error_str:
                    guide_msg = (
                        f"❌ [시스템 감지] 데이터가 너무 많아서 버퍼가 터졌습니다 (ENOBUFS).\n"
                        f"절대로 똑같은 명령을 다시 시도하지 마세요.\n"
                        f"대신 '모든 네임스페이스(--all-namespaces)' 옵션을 끄거나,\n"
                        f"특정 네임스페이스만 지정해서 다시 시도하세요."
                    )
                    print(f"⚠️ [MCP Error Handled] {guide_msg}")
                    return guide_msg
                
                if attempt < max_retries:
                    print(f"⚠️ [MCP System Error] 통신 오류 감지: {error_str}")
                    continue
                
                error_msg = f"Error executing tool {name}: {error_str}"
                print(f"❌ [MCP Error] {error_msg}")
                return error_msg

    async def cleanup(self):
        """프로그램 종료 시 연결을 깔끔하게 정리하는 함수"""
        await self.exit_stack.aclose()

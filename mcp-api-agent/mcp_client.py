import asyncio
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult

from langchain_core.tools import StructuredTool
from pydantic import create_model

from config import logger

class MCPClient:
    def __init__(self, name: str, server_url: str):
        self.name = name  # 서버 별칭 (Namespace용)
        self.server_url = server_url
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.tools = []
        self._ping_task = None

    async def _keepalive(self):
        """서버와의 연결 유지를 위한 주기적인 핑 전송 (SSE Idle Timeout 방지)"""
        while True:
            await asyncio.sleep(45) # 45초마다 핑 전송
            if self.session:
                try:
                    await self.session.send_ping()
                except Exception as e:
                    # 핑 실패는 무시 (연결이 끊어졌다면 메인 흐름에서 에러 처리됨)
                    pass

    async def connect(self):
        """MCP 서버에 연결"""
        logger.info(f"🔌 [{self.name}] 서버 연결 시도: {self.server_url} ...")
        try:
            # 1시간(3600초)의 넉넉한 SSE 읽기 타임아웃
            transport = await self.exit_stack.enter_async_context(
                sse_client(self.server_url, sse_read_timeout=3600)
            )
            # mcp 1.2.x 버전 호환성: transport[0], transport[1] 사용
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(transport[0], transport[1])
            )
            await self.session.initialize()
            logger.info(f"✅ [{self.name}] 연결 성공!")
            
            # 연결 성공 후 Keep-Alive Task 시작
            self._ping_task = asyncio.create_task(self._keepalive())
            
            await self.refresh_tools()
            
        except Exception as e:
            logger.error(f"❌ [{self.name}] 연결 실패: {e}")
            await self.cleanup()
            raise e

    async def refresh_tools(self):
        """도구 목록을 가져와서 Namespace를 적용하여 변환"""
        if not self.session:
            raise RuntimeError("Session not initialized")

        mcp_tools_list = await self.session.list_tools()
        self.tools = []

        for tool in mcp_tools_list.tools:
            # 1. Pydantic 모델 동적 생성
            schema = tool.inputSchema
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            fields = {}
            for prop_name, prop_schema in properties.items():
                py_type = Any
                if prop_schema.get("type") == "string":
                    py_type = str
                elif prop_schema.get("type") == "integer":
                    py_type = int
                elif prop_schema.get("type") == "boolean":
                    py_type = bool

                if prop_name in required:
                    fields[prop_name] = (py_type, ...)
                else:
                    fields[prop_name] = (py_type, None)
            
            # 모델 이름에도 접두사 포함
            InputModel = create_model(f"{self.name}_{tool.name}_input", **fields)

            # 2. 실행 래퍼 함수
            async def _run_tool(tool_name=tool.name, **kwargs):
                clean_args = {k: v for k, v in kwargs.items() if v is not None}
                return await self.call_mcp_tool(tool_name, clean_args)

            # 3. 도구 이름에 접두사(Namespace) 적용!
            namespaced_tool_name = f"{self.name}_{tool.name}"

            langchain_tool = StructuredTool.from_function(
                func=None,
                coroutine=_run_tool,
                name=namespaced_tool_name,
                description=f"[{self.name}] {tool.description[:1000]}",
                args_schema=InputModel
            )
            self.tools.append(langchain_tool)
        
        logger.debug(f"   └─ 🛠️  [{self.name}] 도구 {len(self.tools)}개 로드 완료")

    async def call_mcp_tool(self, name: str, arguments: dict) -> str:
        """도구 실행"""
        logger.debug(f"🚀 [{self.name}] Tool Call: {name} (Args: {arguments})")
        try:
            result: CallToolResult = await self.session.call_tool(name, arguments)
            
            output_text = []
            if result.content:
                for content in result.content:
                    if content.type == "text":
                        output_text.append(content.text)
            
            final_output = "\n".join(output_text)
            
            # [최적화] Tool Output Truncation (토큰 폭탄 및 LLM 뻗음 방지)
            # 50,000자는 너무 길어 LLM이 느려지거나 컨텍스트 한계로 에러(Crash)를 유발합니다.
            # 속도 최적화 및 안정성을 위해 10,000자(약 3,000토큰)로 제한합니다.
            MAX_OUTPUT_LENGTH = 10000 
            if len(final_output) > MAX_OUTPUT_LENGTH:
                final_output = final_output[:MAX_OUTPUT_LENGTH] + \
                    f"\n... (⚠️ Output truncated by {len(final_output) - MAX_OUTPUT_LENGTH} chars. Use specific filters to see more.)"
                logger.warning(f"✂️ [{self.name}] Truncation: 결과가 너무 길어 잘랐습니다. ({len(final_output)} chars)")

            # [변경] 디버깅을 위해 결과의 앞부분을 보여줌
            preview = final_output[:200].replace("\n", " ") + "..." if len(final_output) > 200 else final_output.replace("\n", " ")
            logger.debug(f"✅ [{self.name}] 성공 (Return: {preview})")
            return final_output
        except Exception as e:
            error_str = str(e) or repr(e)
            if "ENOBUFS" in error_str:
                return "❌ [System Limit] ENOBUFS: 데이터가 너무 많습니다. 범위를 좁히세요."
            
            logger.error(f"❌ [{self.name}] Error: {error_str}")
            return f"Error executing {name}: {error_str}"

    async def cleanup(self):
        """자원 정리: 오류 발생 시 무시하고 안전하게 종료"""
        # 백그라운드 핑 태스크 취소
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        try:
            await self.exit_stack.aclose()
        except RuntimeError as e:
            if "cancel scope" in str(e):
                pass
            else:
                logger.warning(f"⚠️ [{self.name}] Cleanup Warning: {e}")
        except Exception as e:
            logger.error(f"⚠️ [{self.name}] Cleanup Error: {e}")

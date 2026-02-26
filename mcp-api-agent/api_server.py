import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn
from langchain_core.messages import HumanMessage
import json

import warnings
# Pydantic 필드 이름 충돌 경고 무시
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from config import MCP_SERVERS, logger
from mcp_client import MCPClient
from agent_graph import create_agent_app

from contextlib import asynccontextmanager

# FastAPI 앱의 생명주기(Lifecycle) 관리
@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 기동 시 초기화 및 종료 시 정리 로직"""
    global agent_app, mcp_clients
    
    logger.info("🚀 [System] FastAPI 기반 MCP Agent 기동 시작...")
    all_tools = []
    
    # 1. 기동 시: MCP 서버 연결 및 에이전트 초기화
    for server_conf in MCP_SERVERS:
        client = MCPClient(server_conf["name"], server_conf["url"])
        try:
            await client.connect()
            mcp_clients.append(client)
            all_tools.extend(client.tools)
        except Exception as e:
            logger.error(f"MCP Connection failed ({server_conf['name']}): {e}")
            
    if not mcp_clients:
        logger.warning("❌ 연결된 서버가 없습니다. (도구 없이 초기화됩니다)")
    else:
        logger.info(f"✨ 총 {len(mcp_clients)}개 서버 연결 완료. (도구 {len(all_tools)}개 사용 가능)")
        
    # 에이전트 앱 생성
    agent_app = create_agent_app(all_tools)
    logger.info("✅ API Server: Agent initialized with tools.")
    
    yield  # 서버 실행 중 (이 시점에 요청을 받습니다)
    
    # 2. 종료 시: MCP 연결 정리
    logger.info("🧹 연결 종료 중...")
    for client in mcp_clients:
        await client.cleanup()
    logger.info("👋 Bye!")

# FastAPI 앱 생성
app = FastAPI(title="K8s MCP Agent API", lifespan=lifespan)

# 전역 변수로 에이전트 앱과 클라이언트 관리
agent_app = None
mcp_clients = []

# ========================================================
# 자체 Web을 위한 일반 API 엔드포인트
# ========================================================
@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """일반적인 자체 개발 웹페이지에서 호출하기 쉬운 모드"""
    data = await request.json()
    user_input = data.get("message", "")
    
    logger.info(f"User > {user_input}")
    logger.debug("--- 🔄 처리 중... ---")
    
    # LangGraph 실행 및 최종 결과만 반환 (스트리밍이 아닐 경우)
    inputs = {"messages": [HumanMessage(content=user_input)]}
    result = await agent_app.ainvoke(inputs)
    
    # 결과 파싱하여 반환
    final_message = result["messages"][-1].content
    return {"reply": final_message}

# ========================================================
# 커스텀 React Flow 대시보드 연동을 위한 전용 SSE 스트리밍
# ========================================================
@app.post("/api/stream_chat")
async def react_flow_stream_endpoint(request: Request):
    """React Flow 기반의 2D 시각화 대시보드와 통신하기 위한 Vercel AI SDK Data Stream 호환 엔드포인트"""
    data = await request.json()
    messages = data.get("messages", [])
    user_input = messages[-1]["content"] if messages else data.get("message", "")
    
    logger.info(f"[ReactFlow UI] User > {user_input}")

    async def stream_generator():
        inputs = {"messages": [HumanMessage(content=user_input)]}
        from config import stream_queue
        
        # Vercel AI SDK 호환 Data Stream Chunk 생성 함수
        def make_text_chunk(text: str):
            return f'0:{json.dumps(text, ensure_ascii=False)}\n'
            
        def make_data_status(node_id: str, status: str, node_type: str = "agent", error: str = None):
            data_obj = {
                "type": "data-node-execution-status",
                "data": {
                    "nodeId": node_id,
                    "nodeType": node_type,
                    "status": status,
                }
            }
            if error:
                data_obj["data"]["error"] = error
            return f'8:[{json.dumps(data_obj, ensure_ascii=False)}]\n'
        
        import asyncio
        graph_task = None
        
        async def run_graph():
            try:
                # 초기 상태: Router 시작
                await stream_queue.put(make_data_status("start", "success"))
                await stream_queue.put(make_data_status("router", "running"))
                
                async for event in agent_app.astream(inputs):
                    for key, value in event.items():
                        if key == "router":
                            await stream_queue.put(make_data_status("router", "success"))
                        elif key == "orchestrator":
                            await stream_queue.put(make_data_status("orchestrator", "running"))
                        elif key == "workers":
                            # 개별 이벤트(LogSpecialist 등)가 EVENT 큐로 들어오므로 여기서는 전역 상태만 관리
                            await stream_queue.put(make_data_status("orchestrator", "success"))
                        elif key == "synthesizer":
                            await stream_queue.put(make_data_status("synthesizer", "running"))
                        elif key == "simple_agent":
                            await stream_queue.put(make_data_status("router", "success"))
                            await stream_queue.put(make_data_status("simple_agent", "running"))
                            msg = value["messages"][-1].content
                            await stream_queue.put(make_data_status("simple_agent", "success"))
                            await stream_queue.put(make_data_status("end", "success"))
                            await stream_queue.put(make_text_chunk(msg))
                            
            except Exception as e:
                logger.error(f"❌ [Graph] 실행 중 오류 발생: {e}")
                await stream_queue.put(make_data_status("router", "error", error=str(e)))
            finally:
                await stream_queue.put("EOF")

        graph_task = asyncio.create_task(run_graph())
        import time
        token_buffer = ""
        last_flush = time.time()

        while True:
            if await request.is_disconnected():
                logger.warning("⚠️ [API] 클라이언트 연결 끊김")
                if graph_task and not graph_task.done():
                    graph_task.cancel()
                break

            try:
                msg = await asyncio.wait_for(stream_queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                if token_buffer:
                    yield make_text_chunk(token_buffer)
                    token_buffer = ""
                    last_flush = time.time()
                yield " \n"
                continue

            if msg == "EOF":
                if token_buffer:
                    yield make_text_chunk(token_buffer)
                yield 'd:{"finishReason":"stop"}\n'
                break
                
            elif msg.startswith("0:") or msg.startswith("8:"):
                yield msg
                
            elif msg.startswith("TOKEN:"):
                token_buffer += msg.replace("TOKEN:", "", 1)
                now = time.time()
                if now - last_flush >= 0.1:
                    yield make_text_chunk(token_buffer)
                    token_buffer = ""
                    last_flush = now
                    
            elif msg.startswith("FINAL:"):
                text = msg.replace("FINAL:", "", 1)
                yield make_data_status("agent", "success")
                yield make_data_status("end", "success")
                yield make_text_chunk(text)

            else:
                if msg.startswith("EVENT:"):
                    action_text = msg.replace("EVENT:", "", 1).strip()
                    
                    target_node = "tools" # Default
                    if "LogSpecialist" in action_text:
                        target_node = "worker_log"
                    elif "MetricSpecialist" in action_text:
                        target_node = "worker_metric"
                    elif "K8sSpecialist" in action_text:
                        target_node = "worker_k8s"
                    elif "synthesizer" in action_text.lower():
                        target_node = "synthesizer"
                        
                    # Tool completion usually has '완료' or '결과' in Korean logs
                    if "완료" in action_text or "결과" in action_text:
                        yield make_data_status(target_node, "success")
                        if target_node == "synthesizer":
                            yield make_data_status("end", "success")
                    else:
                        yield make_data_status(target_node, "running")
                    
                    yield make_text_chunk(f"[과정] {action_text}\n")

    return StreamingResponse(
        stream_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# ========================================================
# OpenWebUI 연동을 위한 OpenAI 호환 API (스트리밍 지원)
# ========================================================
@app.post("/v1/chat/completions")
async def openai_compatible_endpoint(request: Request):
    """OpenWebUI 등 OpenAI 규격을 요구하는 클라이언트를 위한 엔드포인트"""
    data = await request.json()
    
    # messages 배열에서 마지막 사용자의 질문을 추출
    messages = data.get("messages", [])
    user_input = messages[-1]["content"] if messages else ""
    model_name = data.get("model", "qwen-k8s-agent")
    
    logger.info(f"[OpenWebUI] User > {user_input}")

    async def stream_generator():
        inputs = {"messages": [HumanMessage(content=user_input)]}
        from config import stream_queue
        
        # 내부 진행 상황을 OpenWebUI에도 보여주기 위한 헬퍼 함수
        def make_chunk(text):
            chunk = {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "model": model_name,
                "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}]
            }
            return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        
        # OpenWebUI 호환성을 위한 "단일 Think Block" 전송 헬퍼
        # 여러 번 열고 닫으면 렌더러에 심한 렉이 걸리므로, 한 번만 열고 내부에서 줄바꿈을 통해 추가합니다.
        
        # --- 복합 스트리밍 로직 ---
        # 1. LangGraph의 astream 이벤트 스트림
        # 2. 백그라운드 Worker의 진행 상태를 담는 stream_queue 
        
        import asyncio
        queue_task = None
        graph_task = None
        
        async def run_graph():
            try:
                async for event in agent_app.astream(inputs):
                    for key, value in event.items():
                        if key == "router":
                            await stream_queue.put("EVENT:🔄 `[System]` 라우터 모드 결정 중...")
                        elif key == "orchestrator":
                            await stream_queue.put("EVENT:📋 `[System]` 작업 계획 수립 중...")
                        elif key == "workers":
                            results = value.get("worker_results", [])
                            await stream_queue.put(f"EVENT:👷 `[System]` {len(results)}개 병렬 작업 실행 완료.")
                        elif key == "synthesizer":
                            pass
                        elif key == "simple_agent":
                            msg = value["messages"][-1].content
                            await stream_queue.put(f"FINAL:{msg}")
            except Exception as e:
                logger.error(f"❌ [Graph] 실행 중 오류 발생: {e}")
                # 에러 발생 시 UI에 명시적으로 알림
                await stream_queue.put(f"FINAL:\n\n⚠️ **에이전트 실행 중 오류가 발생하여 중단되었습니다:**\n```\n{str(e)}\n```")
            finally:
                # 정상/비정상 종료 상관없이 반드시 스트림 종료 시그널 전송
                await stream_queue.put("EOF")

        graph_task = asyncio.create_task(run_graph())
        
        has_started_thinking = False
        has_finished_thinking = False
        import time
        token_buffer = ""
        last_flush_time = time.time()

        while True:
            # 클라이언트 연결 끊김(새로고침, 중지버튼, 타임아웃 재시도 등) 감지
            if await request.is_disconnected():
                logger.warning("⚠️ [API] 클라이언트(OpenWebUI) 연결이 끊어졌습니다. 작업을 취소합니다.")
                if graph_task and not graph_task.done():
                    graph_task.cancel()
                break

            try:
                # 잔여 토큰이 있으면 짧게 대기, 없으면 5초 대기(Keep-Alive용)
                timeout_val = 0.05 if token_buffer else 5.0
                msg = await asyncio.wait_for(stream_queue.get(), timeout=timeout_val)
            except asyncio.TimeoutError:
                if token_buffer:
                    yield make_chunk(token_buffer)
                    token_buffer = ""
                    last_flush_time = time.time()
                else:
                    yield ": keep-alive\n\n"
                continue

            if msg == "EOF":
                if token_buffer:
                    yield make_chunk(token_buffer)
                    token_buffer = ""
                if has_started_thinking and not has_finished_thinking:
                    yield make_chunk("\n</think>\n\n")
                break
                
            elif msg.startswith("EVENT:"):
                if token_buffer:
                    yield make_chunk(token_buffer)
                    token_buffer = ""
                    
                text = msg.replace("EVENT:", "", 1)
                if not has_started_thinking:
                    yield make_chunk("<think>\n" + text + "\n")
                    has_started_thinking = True
                else:
                    yield make_chunk(text + "\n")
                    
            elif msg.startswith("TOKEN:"):
                if has_started_thinking and not has_finished_thinking:
                    yield make_chunk("\n</think>\n\n")
                    has_finished_thinking = True
                
                # 브라우저 UI 렉(Lag)을 방지하기 위해 토큰을 모읍니다.
                token_buffer += msg.replace("TOKEN:", "", 1)
                now = time.time()
                # 0.05초(초당 20프레임) 간격으로 모아서 화면에 송출합니다.
                if now - last_flush_time >= 0.05:
                    yield make_chunk(token_buffer)
                    token_buffer = ""
                    last_flush_time = now
                
            elif msg.startswith("FINAL:"):
                if token_buffer:
                    yield make_chunk(token_buffer)
                    token_buffer = ""
                    
                if has_started_thinking and not has_finished_thinking:
                    yield make_chunk("\n</think>\n\n")
                    has_finished_thinking = True
                    
                yield make_chunk(msg.replace("FINAL:", "", 1))
                
            else:
                if token_buffer:
                    yield make_chunk(token_buffer)
                    token_buffer = ""
                    
                if not has_started_thinking:
                    yield make_chunk("<think>\n" + msg + "\n")
                    has_started_thinking = True
                else:
                    yield make_chunk(msg + "\n")
                
        # 스트리밍 종료
        end_chunk = {
            "id": "chatcmpl-123",
            "object": "chat.completion.chunk",
            "model": model_name,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
        }
        yield f"data: {json.dumps(end_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # Nginx/K8s Ingress의 SSE 버퍼링 강제 비활성화
        }
    )

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)

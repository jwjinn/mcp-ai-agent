import asyncio
from langchain_core.messages import HumanMessage

# 모듈 임포트
import warnings
# Pydantic 필드 이름 충돌 경고 무시 (예: 'validate' 필드)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from config import MCP_SERVERS
from mcp_client import MCPClient
from agent_graph import create_agent_app

async def main():
    print("\n🚀 [System] MCP Agent 기동 시작...")
    
    # 1. 클라이언트 초기화 및 연결
    clients = []
    all_tools = []
    
    for server_conf in MCP_SERVERS:
        client = MCPClient(server_conf["name"], server_conf["url"])
        try:
            await client.connect()
            clients.append(client)
            all_tools.extend(client.tools)
        except Exception:
            # 실패해도 계속 진행 (로그는 client 내부에서 찍음)
            pass

    if not clients:
        print("❌ 연결된 서버가 없습니다. 종료합니다.")
        return

    print(f"\n✨ 총 {len(clients)}개 서버 연결 완료. (도구 {len(all_tools)}개 사용 가능)")

    # 2. 에이전트 앱 생성 (두뇌 조립)
    app = create_agent_app(all_tools)

    # 3. 사용자 입력 루프
    print("\n🤖 Qwen K8s Agent (Modular Version) 준비 완료 (종료: q)")
    
    while True:
        try:
            user_input = input("\nUser > ")
            if user_input.lower() in ["q", "quit"]:
                break
            
            print("--- 🔄 처리 중... ---")
            inputs = {"messages": [HumanMessage(content=user_input)]}
            
            async for event in app.astream(inputs):
                for key, value in event.items():
                    # 새로 추가된 노드들의 출력을 처리합니다.
                    if key == "router":
                        mode = value.get("mode", "UNKNOWN")
                        print(f"🔄 [Router] 모드 결정: {mode}")
                    
                    elif key == "orchestrator":
                        plans = value.get("worker_plans", {})
                        import json
                        print(f"📋 [Orchestrator] 작업 계획:\n{json.dumps(plans, ensure_ascii=False, indent=2)}")
                    
                    elif key == "workers":
                        results = value.get("worker_results", [])
                        # 결과 내용이 너무 길 수 있으므로 요약만 출력
                        print(f"👷 [Workers] 총 {len(results)}개 작업 실행 완료.")
                        for res in results:
                            # 앞부분 일부만 출력
                            preview = res.split('\n')[0]
                            print(f"   └─ {preview}...")

                    elif key == "synthesizer":
                        # 스트리밍으로 이미 출력되었으므로 여기서는 줄바꿈만 처리
                        print("\n✨ [Synthesizer] 답변 완료.")

                    elif key == "simple_agent":
                        msg = value["messages"][-1]
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            print(f"🛠️  [Simple] 도구 호출: {msg.tool_calls[0]['name']}")
                        else:
                            print(f"💬 [Simple] 답변: {msg.content}")
                            
                    elif key == "tools":
                        print(f"   └─ [System] 도구 실행 완료")
                        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ 에러 발생: {e}")

    # 4. 종료 처리
    print("\n🧹 연결 종료 중...")
    for client in clients:
        await client.cleanup()
    print("👋 Bye!")

if __name__ == "__main__":
    asyncio.run(main())

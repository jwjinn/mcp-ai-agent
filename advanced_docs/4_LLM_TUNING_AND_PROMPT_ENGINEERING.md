# 🧠 4. LLM Tuning & Prompt Engineering (심화)

이 문서는 본 시스템이 **최적의 모델 성능(Model Performance)과 치명적 파싱(Parsing) 에러 제로화**를 달성하기 위해 도입한 LLM 이원화(Dichotomy) 원리와 프롬프트 엔지니어링의 정수를 다루는 아키텍처 가이드입니다.

> 이 문서는 **모델 전략 심화 문서**입니다. 현재 모델 역할 분리와 토큰 보호값 운영 방식은 [`mcp-api-agent/DEPLOYMENT_GUIDE.md`](../mcp-api-agent/DEPLOYMENT_GUIDE.md), [`mcp-api-agent/NPU_QWEN3_REFERENCE.md`](../mcp-api-agent/NPU_QWEN3_REFERENCE.md)를 참고하세요.

---

## 🎭 1. 모델 이원화의 딜레마 (Instruct vs Thinking)

AIOps 시스템 초창기에는 모든 노드를 강력한 **Thinking 모델 (ex. Qwen-Thinking/DeepSeek-R1)** 하나로 통일했습니다. 하지만 이 방식은 두 가지 끔찍한 부작용을 낳았습니다.

1.  **JSON 형식 파괴 (The `<think>` parsing nightmare)**
    *   Orchestrator는 워커들에게 JSON 형태(`{"k8s": "...", "log": "..."}`)의 지시서를 내려야 합니다.
    *   하지만 Thinking 모델은 대답을 내놓기 전 `"<think> 흐음... k8s를 써야겠군... </think> {"k8s": "..."}"` 이런 식으로 자기 독백을 앞에 무조건 붙입니다.
    *   파이썬 인터프리터가 이 텍스트 전체를 `json.loads`에 태우는 순간 바로 **JSON Decode Crash**가 발생하며 컨테이너가 뻗어버렸습니다. 정규식(Regex)으로 태그를 파싱해 빼내려 해도 태그가 깨지거나 포맷이 일그러지는 경우가 허다했습니다.

2.  **연산 비용 최적화 실패 (Wasted FLOPs)**
    *   라우터(Router) 노드는 "단순조회(SIMPLE)인가, 심층분석(COMPLEX)인가?" 라는 1차원적 판단만 하면 됩니다. 여기에 Thinking 모델을 쓰면 2초면 끝날 판단에 20초간 `<think>`를 하며 사용자의 지연 시간(Latency)을 희생시킵니다.

### 💡 솔루션: "규칙"과 "추론"의 철저한 격리
시스템 프롬프트의 지시사항(Instruction)을 기계처럼 완벽히 따르고 JSON Schema를 기가 막히게 출력해 내는 **Instruct 모델**을 전진 배치 (Router, Orchestrator, Worker) 했습니다.
그리고 오직 정제된 정보들만이 모여 최종 결론(Root Cause)을 도출해야 하는 대단원(Synthesizer 노드)에만 자본(시간과 추론력)이 집중된 **Thinking 모델**을 배치해 완벽한 하이브리드(Hybrid)를 완성했습니다.

---

## 🚫 2. 무한 루프 차단 (Anti-Hallucination Deduplication)

과거 순수 ReAct 에이전트들은 자신이 방금 사용한 도구(Tool)를 잊어버리고 "다시 사용해볼까?" 하며 무한 루프에 빠져 서버 크래시를 유도했습니다.
우리는 `check_and_filter_duplicate_tools` 함수를 통해 LLM의 의사결정에 외과적 수술을 단행했습니다.

```python
def check_and_filter_duplicate_tools(history_messages: list, new_msg: BaseMessage):
    # 직전 AI 메시지가 없거나 툴 호출이 아니면 통과
    last_ai_msg = list(filter(lambda x: isinstance(x, AIMessage) and x.tool_calls, history_messages))
    if not last_ai_msg: return new_msg
    
    # 1. 이전(직전) 메시지가 사용했던 도구의 이름과 인자 셋을 문자열 해싱(Hashing)하여 세트에 담습니다.
    # 2. 이번(현재) 메시지가 사용하려는 도구의 해시셋과 대조합니다.
    # 3. 100% 일치한다면, LLM이 반환한 객체에서 해당 툴을 삭제(DROP)해버립니다.
    
    # [방어 로직] 툴이 날아간 자리에 오류 메세지가 뜨지 않도록 시스템 프롬프트를 강제 삽입
    new_msg.content += "\n[System: 동일한 도구/인자 실행이 시스템에 의해 차단되었습니다.] "
```

이 알고리즘 덕분에 에이전트가 단기 기억 상실에 걸려도, 강제로 리젝트(Reject)당한 사실을 주입받아 다음 행동(다른 도구 쓰기 또는 요약 단계)으로 넘어갈 수밖에 없도록 강제 유도됩니다.

---

## 🌊 3. 콜백 가로채기 (Callback Interception for Thinking Stream)

`api_server.py`에서 SSE 기반으로 스트리밍을 쏠 때, Thinking 모델의 수십 줄짜리 `<think> ... </think>` 텍스트가 화면에 쏟아지는 것은 매우 지저분한 UX(사용자 경험)를 줍니다.
그래서 **`AsyncThinkingStreamCallback`**이라는 커스텀 핸들러를 구현했습니다.

```python
class AsyncThinkingStreamCallback(AsyncCallbackHandler):
    # Langchain의 on_llm_new_token 훅을 오버라이딩(Overriding)
    async def on_llm_new_token(self, token: str, **kwargs):
        self.buffer += token
        
        # 만약 아직 생각 중(<think> 구역 내부)이라면, 
        # 토큰을 모으기만 하고 버퍼 밖(Queue)으로 절대 방출(Yield)하지 않음!
        if self.in_thinking:
            if "</think>" in self.buffer:
                self.in_thinking = False
                # 태그 이후의 본론만 방출 시작
                remaining = self.buffer.split("</think>")[-1]
                if remaining: await self.target_queue.put(remaining)
            return

        # 생각이 끝난 후(본론 구역)부터는 즉시 즉시 Queue에 Push
        await self.target_queue.put(token)
```

이 로직을 통해 뇌(LLM)는 자유롭게 수백 문장의 독백을 뱉어도, 입(API Output)은 오직 최종 답변(Diagnosis)의 첫 글자부터만 사용자 브라우저에 렌더링되도록 **필터 드레인(Filter drain)** 현상을 구현했습니다.

---
👉 **[이전으로 돌아가기 (초보자용 1장: 배경 이야기)](../paper/1_BACKGROUND_AND_WHY.md)**

# 🚀 4. 실전! 내 컴퓨터에서 돌려보기 (HOW TO START)

자, 1~3장까지 머리 아픈 이론과 코드를 가볍게 훑어보았습니다.
이제 진짜로 내 컴퓨터(로컬)에서 이 엄청난 AI 비서를 깨워볼 시간입니다. 
초보자라도 천천히 따라 할 수 있도록 "떠먹여 드리는" 형태로 진행합니다.

---

## 🛠️ Step 1. 파이썬 마법 지팡이(환경) 준비하기

먼저 컴퓨터에 파이썬(Python 3.10 이상)이 깔려 있어야 합니다. 
(복잡하게 꼬이는 것을 막기 위해 `Conda` 같은 가상환경을 쓰는 것을 아주 강.력.히 추천합니다!)

터미널(또는 CMD)을 열고 아래 명령어를 순서대로 복사해서 붙여넣고 엔터를 치세요!

```bash
# 1. 'mcp-agent'라는 이름의 깨끗한 파이썬 3.11 방을 하나 만듭니다.
conda create -n mcp-agent python=3.11 -y

# 2. 그 방으로 들어갑니다. (프롬프트 왼쪽에 (mcp-agent)라고 뜰 거예요!)
conda activate mcp-agent

# 3. 프로젝트 폴더로 이동합니다. (여러분이 다운로드 받은 경로)
# cd c:/.../mcp-ai-agent/mcp-api-agent

# 4. 이 코드가 돌아가는데 필요한 부품(라이브러리)들을 한 방에 설치합니다.
pip install -r requirements_api.txt
```

---

## ⚙️ Step 2. AI 두뇌 연결선 꼽아주기 (설정 파일 만들기)

우리의 AI 비서는 빈 깡통입니다. K8s 도구(MCP 서버)가 어디 있는지, 그리고 대답을 내려줄 GPT 두뇌(명령용/추론용)의 주소는 어디인지 알려주어야 합니다!

1. `mcp-api-agent/` 폴더 안을 쓱 둘러보면 `config.example.py`와 `config.example.json` 이 보일 겁니다.
2. 둘 다 복사해서 똑같은 자리에 두고, 이름에서 `.example` 글자만 빼주세요. (`config.py`, `config.json` 만들기)

### 👉 `config.json` 수정하기 (어디서 데이터를 캘 것인가? 어디 뇌를 쓸 것인가?)

만들어진 `config.json` 파일을 열어서 메모장(또는 VSCode)으로 엽니다.
초보자분들은 로컬 K8s에 띄워진 도구(NodePort) 주소랑, 여러분이 쓰는 LLM(Qwen 등)의 주소만 박아주면 됩니다.

```json
{
  "MCP_SERVERS": [
    {"name": "k8s",             "url": "http://여러분의_K8s_서버IP:NodePort/sse"},
    {"name": "VictoriaLog",     "url": "http://여러분의_K8s_서버IP:NodePort/sse"}
  ],
  "INSTRUCT_CONFIG": {
    "base_url": "http://여러분의_명령어용_AI주소/v1",
    "model_name": "qwen-custom",
    "api_key": "YOUR_API_KEY"
  },
  "THINKING_CONFIG": {
    "base_url": "http://여러분의_셜록홈즈용_AI주소/v1",
    "model_name": "qwen-thinking",
    "api_key": "YOUR_API_KEY"
  }
}
```

> 💡 **Tip:** 만약 "어? 나는 지금 연결할 K8s나 외부 API 키가 당장 없는데?" 하시면, 에이전트가 돌긴 하지만 도구를 못 가져와서 **"도구를 찾을 수 없습니다"**라고 슬퍼할 수 있습니다. ㅠㅠ

---

## 🔥 Step 3. 서버 심장 켜기!

드디어 모든 셋팅이 끝났습니다. 터미널(가상환경 상태)에서 다음 명령어 한 줄이면 마법이 시작됩니다.

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

*   `uvicorn`: 파이썬이 만든 빠르고 강력한 웹 서버 실행기입니다.
*   `api_server:app`: "야! api_server.py 안에 있는 app(FastAPI 객체)을 찾아서 켜라!"
*   `--reload`: 코드를 수정하고 저장(`Ctrl+S`)하면 서버를 안 껐다 켜도 자동으로 새로고침 해줍니다. (개발할 때 꿀입니다!)

짜잔! 터미널에 알록달록한 글씨들로 **`[k8s] 도구 N개 로드 완료...`** 같은 메시지가 좌르륵 뜬다면? 완벽하게 무기를 장착하고 명령을 기다리고 있는 상태입니다!

---

## 🤖 Step 4. 비서 부려먹기 (테스트 해보기)

이제 우리가 만든 셜록 홈즈에게 말을 걸어볼 차례입니다.
Postman을 쓰셔도 되고, 터미널을 새로 열어서 명령어를 쳐도 됩니다.

### 질문 1: "단순한 조회" (Simple Path 타는지 보기)
```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
           "messages": [{"role": "user", "content": "지금 쿠버네티스 파드 목록 좀 줘."}],
           "stream": true
         }'
```
*   **관전 포인트**: 팀장(Orchestrator) 부르지도 않고, 터미널 로그를 보면 Router가 바로 Simple Agent한테 일 시켜서 순식간에 끝내버릴 겁니다!

### 질문 2: "셜록 홈즈 출동!" (Complex Path 타는지 보기)
```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
           "messages": [{"role": "user", "content": "결제 파드가 갑자기 죽었는데, OOM(메모리 부족)인지 로그랑 메트릭 좀 다 털어서 분석해줘."}],
           "stream": true
         }'
```
*   **관전 포인트**: 우와아아! 터미널 로그를 유심히 보세요.
    1. Router가 "헉, 이건 단순 조회가 아니구먼!" 하고 `COMPLEX` 모드로 전환합니다.
    2. 팀장(Orchestrator)이 JSON으로 K8s팀, Log팀에게 내릴 지시서를 만듭니다.
    3. `asyncio.gather`가 발동하며 여러 도구가 **"동시에"** 파바박 실행됩니다.
    4. 요약 요정들이 핵심만 뽑는 게 로그로 보입니다.
    5. 마지막으로 우리의 최고급 셜록 홈즈(Thinking 모델)가 `<think>` 태그를 뿜어내며 장고에 돌입하고 엄청난 원인 분석 리포트를 내려줄 겁니다!!

---

## 🎉 마무리하며 (졸업을 축하합니다!)

고생하셨습니다! 여기까지 오셨다면, 여러분은 단순한 웹 개발을 넘어 **최신 트렌드인 "다중 AI 에이전트 분산 아키텍처"** 가 어떻게 설계되고 돌아가는지 그 험난한(?) 과정을 모두 마스터하신 겁니다.

앞으로 새로운 MCP 서버(ex. 슬랙 메시지 알림, 지라 이슈 생성기 등)를 만들게 되더라도, 그저 `config.json`에 줄 하나만 찍 추가하면 우리 똑똑한 비서들이 알아서 도구를 장착하고 놀라운 일들을 해낼 거예요.

여러분의 AIOps 영웅이 되실 준비가 되셨습니다. 코드를 맘껏 부수고(?) 개선해 보세요!

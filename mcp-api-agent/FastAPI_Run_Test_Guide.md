# FastAPI MCP Agent Run & Test Guide

이 문서는 **현재 구조 기준**으로 FastAPI 기반 MCP Agent 서버를 실행하고 테스트하는 방법을 설명합니다.

이 문서를 먼저 보면 좋은 경우:

- 로컬에서 서버를 띄우고 싶은 경우
- `/api/chat`, `/api/stream_chat`, `/v1/chat/completions` 차이를 알고 싶은 경우
- 실제 운영 환경 배포 전 API 테스트를 먼저 해보고 싶은 경우

운영 배포 자체는 [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md)를 우선 참고하세요.

## 1. 현재 구조에서 먼저 알아둘 것

이 애플리케이션은 직접 모델을 서빙하지 않습니다.

역할은 아래와 같습니다.

- MCP 서버(K8s, Logs, Metrics, Traces)에 연결
- Instruct / Thinking 모델 endpoint에 HTTP 요청
- LangGraph로 요청 흐름을 오케스트레이션

즉 테스트 전에 반드시 아래가 준비되어 있어야 합니다.

- `config.json`에 올바른 `MCP_SERVERS`가 들어가 있음
- `INSTRUCT_CONFIG`가 유효한 모델 endpoint를 가리킴
- `THINKING_CONFIG`가 유효한 모델 endpoint를 가리킴

## 2. 환경 준비

```bash
cd mcp-api-agent
pip install -r requirements_api.txt
```

설정 파일이 없다면 먼저 복사합니다.

```bash
cp config.example.py config.py
cp config.example.json config.json
```

## 3. 설정 파일에서 꼭 채워야 하는 것

현재 `config.json`에서 중요한 섹션은 4개입니다.

- `MCP_SERVERS`
- `INSTRUCT_CONFIG`
- `THINKING_CONFIG`
- `RUNTIME_LIMITS`

의미:

- `MCP_SERVERS`: 어디서 K8s / Logs / Metrics / Traces 데이터를 가져올지
- `INSTRUCT_CONFIG`: Router, Worker, Tool Calling에 쓰는 모델
- `THINKING_CONFIG`: 최종 종합 진단에 쓰는 모델
- `RUNTIME_LIMITS`: 모델 입력 과다, 긴 raw output, 긴 worker summary를 제어하는 보호값

## 4. 서버 실행

### 기본 실행

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

의미:

- `--reload`: 개발 중 코드 변경 시 자동 재시작
- `--host 0.0.0.0`: 외부 접근 허용

### Python으로 직접 실행

```bash
python api_server.py
```

## 5. 어떤 엔드포인트를 언제 테스트하나

현재 기준으로는 아래 순서를 권장합니다.

### 1순위: `/api/chat`

가장 먼저 테스트하기 좋은 엔드포인트입니다.

이유:

- 가장 단순합니다
- 내부 에이전트 동작을 빠르게 검증하기 좋습니다
- 실운영에서 "기본 질의가 되는지" 확인하기 쉽습니다

예시:

```bash
curl http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"현재 NPU inference 환경 전반 상태를 진단해줘"}'
```

### 2순위: `/api/stream_chat`

UI 스트리밍이나 진행 상태 표시를 확인할 때 씁니다.

이유:

- Router / Worker / Synthesizer 진행 상태를 UI 친화적으로 내보냅니다
- 커스텀 프론트엔드와 맞출 때 유용합니다

### 3순위: `/v1/chat/completions`

OpenAI 호환 인터페이스가 필요한 경우에 사용합니다.

이유:

- OpenWebUI 같은 도구와 연동할 수 있습니다
- 다만 실제 tool calling 호환성은 **모델 서버(vLLM 등)의 설정**에 영향을 받을 수 있습니다

예시:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"qwen-k8s-agent",
    "messages":[
      {"role":"user","content":"현재 NPU inference 환경 전반 상태를 진단해줘"}
    ]
  }'
```

## 6. 권장 테스트 순서

### Step 1. 단순 조회

```bash
curl http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"현재 mcp 네임스페이스 파드 목록 보여줘"}'
```

확인할 것:

- Router가 `simple`로 가는지
- K8s MCP 서버 연결이 되는지

### Step 2. 가벼운 분석

```bash
curl http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"worker-01 쪽 vllm 상태를 요약해줘"}'
```

확인할 것:

- Logs / Metrics / K8s 중 필요한 도구만 잘 선택하는지

### Step 3. 종합 진단

```bash
curl http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"현재 NPU inference 환경 전반 상태를 진단해줘"}'
```

확인할 것:

- Orchestrator + Workers + Thinking synthesizer 경로가 다 정상인지
- 응답이 너무 짧거나, 중간에 잘리지 않는지

## 7. Kubernetes에서 빠르게 테스트하는 방법

### 방법 1. 포트포워딩

```bash
kubectl port-forward -n mcp svc/mcp-agent-npu 8000:80
```

그 다음 로컬에서:

```bash
curl http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"현재 NPU inference 환경 전반 상태를 진단해줘"}'
```

### 방법 2. 클러스터 내부 호출

```bash
curl http://mcp-agent-npu.mcp/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"현재 NPU inference 환경 전반 상태를 진단해줘"}'
```

또는:

```bash
curl http://mcp-agent-npu.mcp.svc.cluster.local/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"현재 NPU inference 환경 전반 상태를 진단해줘"}'
```

## 8. 정상 로그는 어떻게 보이나

기동 시 정상 패턴:

- `Loading configuration from /app/config/config.json`
- `MCP Agent 기동 시작`
- 각 MCP 서버에 대해 `연결 성공`
- `총 N개 서버 연결 완료`
- `API Server: Agent initialized with tools`

예상과 다르게 동작하면 먼저 아래를 보세요.

- `kubectl logs deployment/mcp-agent-npu -n mcp`
- MCP 서버 연결 성공 여부
- 모델 endpoint 연결 성공 여부

## 9. 문제 해결 체크포인트

### MCP 서버가 안 붙는 경우

- `MCP_SERVERS.url`이 맞는지
- 서비스 DNS가 맞는지
- `/sse` endpoint가 실제로 살아 있는지

### 응답이 너무 잘리는 경우

- `THINKING_CONFIG.max_input_tokens`
- `THINKING_CONFIG.max_output_tokens`
- `RUNTIME_LIMITS.worker_summary_quota`
- `RUNTIME_LIMITS.max_total_context`

### tool calling 오류가 나는 경우

- 앱 코드가 아니라 모델 서버(vLLM 등) 설정 문제일 수 있습니다
- 특히 OpenAI 호환 경로는 모델 서버의 tool calling 옵션에 영향을 받을 수 있습니다

## 10. 한 줄 추천

현재 버전에서는 **먼저 `/api/chat`으로 성공을 확인하고**, 그 다음에 스트리밍 UI나 OpenAI 호환 경로를 테스트하는 것이 가장 안정적입니다.

# MCP API Agent Deployment Guide

이 문서는 `ghcr.io/jwjinn/mcp-api-agent:latest` 이미지를 기준으로 MCP API Agent를 Kubernetes에 배포하는 방법을 자세히 설명합니다.

핵심 원칙은 간단합니다.

- 코드는 하나의 공통 코드베이스를 유지합니다.
- A100, NPU 차이는 코드 브랜치가 아니라 `설정`과 `배포 오버레이`로 분리합니다.
- 모델별 컨텍스트 길이, 입력 토큰 한도, 출력 토큰 한도, 도구 결과 절단 길이 같은 보호값도 모두 배포 설정에서 관리합니다.

---

## 1. 이 애플리케이션이 하는 일

이 컨테이너는 FastAPI 서버를 띄우고, 시작 시 다음 두 가지를 수행합니다.

1. `config.json`에 정의된 MCP 서버들에 연결합니다.
2. Instruct/Thinking 모델 endpoint 정보를 읽어 LangGraph 기반 에이전트를 초기화합니다.

즉 이 애플리케이션은 자체적으로 대형 모델을 직접 서빙하는 컨테이너가 아니라, 외부 MCP 서버와 외부 LLM endpoint를 연결해주는 오케스트레이션 API 서버입니다.

그래서 배포 시 가장 중요한 것은 다음 3가지입니다.

- MCP 서버 주소가 올바른가
- Instruct / Thinking 모델 endpoint가 올바른가
- 모델별 보호값(context, input/output token, truncation)이 현재 환경과 맞는가

---

## 2. 배포에 필요한 구성 요소

Kubernetes 배포 시 이 프로젝트는 아래 리소스를 사용합니다.

### ConfigMap

애플리케이션이 읽을 `config.json`을 넣습니다.

이 파일에는 아래 정보가 들어갑니다.

- `MCP_SERVERS`: 어떤 MCP 서버에 붙을지
- `INSTRUCT_CONFIG`: 빠르고 형식 안정적인 모델 설정
- `THINKING_CONFIG`: 복합 분석용 깊은 추론 모델 설정
- `RUNTIME_LIMITS`: 컨텍스트 보호, 토큰 보호, 도구 결과 절단 같은 운영 보호값

### Deployment

실제 컨테이너를 띄우는 리소스입니다.

여기서 주로 정하는 값은 아래입니다.

- 어떤 이미지를 쓸지
- 몇 개의 replica를 띄울지
- ConfigMap을 어디에 마운트할지
- 어떤 환경변수를 넘길지
- 필요하다면 어떤 노드나 런타임에 스케줄할지

### Service

클러스터 내부에서 이 API 서버에 접근하기 위한 Kubernetes Service입니다.

기본 예시는 `ClusterIP`입니다.

- 내부 UI나 다른 서비스만 붙으면 `ClusterIP`
- 외부에서 직접 열어야 하면 `NodePort`, `LoadBalancer`, 또는 `Ingress`

---

## 3. 사용할 이미지

이미지는 GHCR에서 바로 가져옵니다.

```bash
docker pull ghcr.io/jwjinn/mcp-api-agent:latest
```

이 이미지는 FastAPI 기반 MCP Agent 서버를 실행하는 런타임 이미지입니다.

컨테이너 시작 시 기본 실행 명령은 다음과 같습니다.

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

컨테이너 내부에서 애플리케이션은 기본적으로 `CONFIG_FILE_PATH` 환경변수가 가리키는 JSON 파일을 읽습니다.

기본 배포에서는 이 값을 아래처럼 둡니다.

```yaml
env:
  - name: CONFIG_FILE_PATH
    value: /app/config/config.json
```

그리고 ConfigMap을 `/app/config`에 read-only로 마운트합니다.

---

## 4. 권장 디렉토리 구조

이 저장소는 환경별 차이를 아래 구조로 분리하는 방식을 권장합니다.

```text
mcp-api-agent/k8s/
  base/
  overlays/
    a100/
    npu/
```

의미는 다음과 같습니다.

- `base/`: 모든 환경에서 공통인 Deployment, Service, ConfigMap 기본형
- `overlays/a100/`: A100 환경에서만 다른 값
- `overlays/npu/`: NPU 환경에서만 다른 값

즉 코드 분기가 아니라 배포 설정 분기입니다.

실제 NPU vLLM 환경에 맞춘 구체적인 추천값이 필요하면 아래 레퍼런스를 함께 보세요.

👉 **[NPU Qwen3 실환경 레퍼런스](NPU_QWEN3_REFERENCE.md)**

---

## 5. 가장 중요한 설정 파일 설명

ConfigMap 안의 `config.json`은 아래 4개 섹션으로 구성됩니다.

### 5.1 `MCP_SERVERS`

예시:

```json
"MCP_SERVERS": [
  {"name": "k8s", "url": "http://mcp-k8s-svc.mcp/sse"},
  {"name": "vlogs", "url": "http://mcp-vlogs-svc.mcp/sse"},
  {"name": "vm", "url": "http://mcp-vm-svc.mcp/sse"},
  {"name": "vtraces", "url": "http://mcp-vtraces-svc.mcp/sse"}
]
```

의미:

- `name`: 내부에서 도구 namespace처럼 사용되는 별칭
- `url`: MCP 서버의 SSE endpoint

주의:

- 이 값이 틀리면 서버는 기동되더라도 MCP 도구를 못 불러옵니다.
- `url`은 반드시 실제 서비스 DNS 또는 접근 가능한 endpoint여야 합니다.

### 5.2 `INSTRUCT_CONFIG`

예시:

```json
"INSTRUCT_CONFIG": {
  "base_url": "http://llm-gateway.example.local/v1",
  "model_name": "qwen-custom",
  "api_key": "EMPTY",
  "default_headers": {"Host": "qwen-instruct.example.com"},
  "temperature": 0,
  "context_window": null,
  "max_input_tokens": null,
  "max_output_tokens": null
}
```

의미:

- `base_url`: OpenAI-compatible endpoint 주소
- `model_name`: 실제 호출할 모델 이름
- `api_key`: 인증 키
- `default_headers.Host`: ingress나 gateway 환경에서 Host 라우팅이 필요할 때 사용
- `temperature`: 출력 다양성
- `context_window`: 모델의 전체 context 길이 개념상 값
- `max_input_tokens`: 이 모델에 넣을 입력 최대 예산
- `max_output_tokens`: 모델의 출력 최대 예산

현재 코드 기준에서 실제 동작상 중요한 값은 `max_input_tokens`, `max_output_tokens`입니다.

- `max_output_tokens`: LangChain `max_tokens`로 연결됩니다.
- `max_input_tokens`: worker summarization 입력이 너무 길 때 잘라내는 보호값으로 사용됩니다.

### 5.3 `THINKING_CONFIG`

예시:

```json
"THINKING_CONFIG": {
  "base_url": "http://llm-gateway.example.local/v1",
  "model_name": "qwen-thinking",
  "api_key": "EMPTY",
  "default_headers": {"Host": "qwen-thinking.example.com"},
  "temperature": 0,
  "context_window": 32768,
  "max_input_tokens": 28672,
  "max_output_tokens": 4096
}
```

의미는 `INSTRUCT_CONFIG`와 같지만, 역할은 다릅니다.

- `INSTRUCT`: 빠른 분류, 툴 호출, JSON 생성
- `THINKING`: 최종 진단, 복합 추론

실무적으로는 `THINKING_CONFIG.max_input_tokens`가 가장 중요할 수 있습니다.
과거처럼 thinking 모델에 너무 큰 입력이 들어가 터지는 문제를 막는 핵심 방어선이기 때문입니다.

### 5.4 `RUNTIME_LIMITS`

예시:

```json
"RUNTIME_LIMITS": {
  "router_keep_last": 5,
  "simple_keep_last": 15,
  "max_ai_steps": 10,
  "worker_summary_quota": 2000,
  "max_total_context": 10000,
  "mcp_tool_max_output_chars": 10000,
  "worker_raw_result_max_chars": 8000
}
```

각 값의 의미:

- `router_keep_last`: Router가 최근 몇 개의 메시지를 볼지
- `simple_keep_last`: Simple agent가 최근 몇 개의 메시지를 볼지
- `max_ai_steps`: 도구 재호출 루프가 너무 길어질 때 끊는 안전장치
- `worker_summary_quota`: 각 worker 결과를 synthesizer에 넘길 때 최대 몇 글자까지 허용할지
- `max_total_context`: synthesizer에 최종적으로 넘길 전체 worker 결과 최대 글자 수
- `mcp_tool_max_output_chars`: MCP tool 원본 결과를 몇 글자에서 자를지
- `worker_raw_result_max_chars`: worker가 요약 전에 다룰 raw 결과 최대 글자 수

이 값들은 모두 과거 장애 경험을 바탕으로 둔 보호장치라고 이해하면 됩니다.

---

## 6. A100 / NPU 환경별로 무엇을 다르게 잡아야 하나

보통 아래 값들이 환경마다 달라집니다.

### A100 환경에서 주로 다른 것

- LLM gateway 주소
- 모델 이름
- `THINKING_CONFIG.max_input_tokens`
- `THINKING_CONFIG.max_output_tokens`

### NPU 환경에서 주로 다른 것

- LLM gateway 주소
- 모델 이름
- ingress host header
- 스케줄링 라벨
- NPU 모델 특성에 맞는 input/output token 보호값

예를 들어 NPU 환경에서 같은 모델명을 써도 실제 서빙 엔진(vLLM 대체 런타임, 전용 추론기 등) 설정이 다르면 입력 허용량이 달라질 수 있습니다. 이럴 때는 브랜치를 나누는 대신 `overlays/npu/configmap-patch.yaml`만 다르게 가져가면 됩니다.

---

## 7. 실제 배포 절차

### 7.1 사전 확인

먼저 아래 항목이 준비되어 있어야 합니다.

- Kubernetes 클러스터 접근 가능
- `kubectl` 사용 가능
- MCP 서버들이 이미 배포되어 있고 접근 가능
- Instruct / Thinking 모델 endpoint 준비 완료

### 7.2 이미지 확인

원하면 사전에 이미지 pull 테스트를 할 수 있습니다.

```bash
docker pull ghcr.io/jwjinn/mcp-api-agent:latest
docker image inspect ghcr.io/jwjinn/mcp-api-agent:latest
```

### 7.3 A100용 설정 적용

파일:

- `mcp-api-agent/k8s/overlays/a100/configmap-patch.yaml`
- `mcp-api-agent/k8s/overlays/a100/deployment-patch.yaml`

수정할 내용:

- MCP 서버 주소
- Instruct / Thinking endpoint
- model_name
- Host header
- token 보호값

배포:

```bash
kubectl apply -k mcp-api-agent/k8s/overlays/a100
```

### 7.4 NPU용 설정 적용

파일:

- `mcp-api-agent/k8s/overlays/npu/configmap-patch.yaml`
- `mcp-api-agent/k8s/overlays/npu/deployment-patch.yaml`

수정할 내용:

- NPU 모델 endpoint
- NPU에 맞는 `max_input_tokens`, `max_output_tokens`
- 필요하다면 NPU 관련 스케줄링 정책

배포:

```bash
kubectl apply -k mcp-api-agent/k8s/overlays/npu
```

---

## 8. Deployment 예시에서 꼭 봐야 하는 항목

예시:

```yaml
containers:
  - name: mcp-agent
    image: ghcr.io/jwjinn/mcp-api-agent:latest
    imagePullPolicy: Always
    env:
      - name: LANGCHAIN_TRACING_V2
        value: "true"
      - name: LOG_LEVEL
        value: "INFO"
      - name: CONFIG_FILE_PATH
        value: "/app/config/config.json"
    volumeMounts:
      - name: config-volume
        mountPath: /app/config
        readOnly: true
```

각 항목의 의미:

- `image`: 실행할 컨테이너 이미지
- `imagePullPolicy: Always`: 배포 때마다 최신 이미지를 다시 확인
- `LANGCHAIN_TRACING_V2`: LangChain tracing 사용 여부
- `LOG_LEVEL`: 로그 레벨
- `CONFIG_FILE_PATH`: 앱이 읽을 실제 설정 파일 경로
- `volumeMounts`: ConfigMap을 컨테이너 파일시스템에 마운트

즉 이 앱은 `env`와 `config.json`을 함께 사용합니다.

- 구조화된 큰 설정은 `config.json`
- 빠르게 override할 값은 `env`

---

## 9. 환경변수 override 방식

현재 코드는 ConfigMap JSON 외에도 환경변수 override를 지원합니다.

예시:

```yaml
env:
  - name: THINKING_MODEL_MAX_INPUT_TOKENS
    value: "24576"
  - name: THINKING_MODEL_MAX_OUTPUT_TOKENS
    value: "3072"
  - name: MCP_TOOL_MAX_OUTPUT_CHARS
    value: "8000"
```

대표적으로 지원하는 변수:

- `INSTRUCT_MODEL_CONTEXT_WINDOW`
- `INSTRUCT_MODEL_MAX_INPUT_TOKENS`
- `INSTRUCT_MODEL_MAX_OUTPUT_TOKENS`
- `THINKING_MODEL_CONTEXT_WINDOW`
- `THINKING_MODEL_MAX_INPUT_TOKENS`
- `THINKING_MODEL_MAX_OUTPUT_TOKENS`
- `ROUTER_KEEP_LAST`
- `SIMPLE_KEEP_LAST`
- `MAX_AI_STEPS`
- `WORKER_SUMMARY_QUOTA`
- `MAX_TOTAL_CONTEXT`
- `MCP_TOOL_MAX_OUTPUT_CHARS`
- `WORKER_RAW_RESULT_MAX_CHARS`

권장 방식:

- 기본 운영값은 ConfigMap JSON에 둡니다.
- 긴급 튜닝이나 환경별 미세 조정은 env로 override합니다.

---

## 10. 장애가 날 때 가장 먼저 볼 포인트

### MCP 도구가 하나도 안 뜨는 경우

확인:

- `MCP_SERVERS.url`이 맞는가
- 해당 서비스가 실제로 `/sse` endpoint를 제공하는가
- 네트워크 정책 때문에 막히지 않았는가

### Thinking 모델에서 자주 실패하는 경우

확인:

- `THINKING_CONFIG.max_input_tokens`가 너무 큰지
- `THINKING_CONFIG.max_output_tokens`가 너무 큰지
- 실제 모델 서버의 context 제한보다 앱 설정이 더 크지 않은지

### 응답이 너무 잘리는 경우

확인:

- `MCP_TOOL_MAX_OUTPUT_CHARS`
- `WORKER_RAW_RESULT_MAX_CHARS`
- `WORKER_SUMMARY_QUOTA`
- `MAX_TOTAL_CONTEXT`

### 무한 루프처럼 보이는 경우

확인:

- `MAX_AI_STEPS`
- 중복 tool 호출 방지 로직이 정상 동작 중인지

---

## 11. 추천 운영 방식

실무적으로는 아래처럼 운영하는 것이 가장 깔끔합니다.

1. 공통 코드는 `master` 브랜치에서 유지
2. 이미지도 공통 이미지 사용
3. 하드웨어 차이는 `overlays/a100`, `overlays/npu`로 분리
4. 모델별 컨텍스트/토큰 차이도 ConfigMap과 env로 분리
5. 문제가 생기면 코드 분기보다 먼저 설정값을 조정

이 방식의 장점:

- 기능 추가를 한 곳에서만 하면 됨
- A100/NPU 배포 절차가 비슷해짐
- 장애 대응 시 코드 수정 없이 설정만 바꿔 빠르게 튜닝 가능

---

## 12. 빠른 시작 요약

### A100

```bash
docker pull ghcr.io/jwjinn/mcp-api-agent:latest
kubectl apply -k mcp-api-agent/k8s/overlays/a100
```

### NPU

```bash
docker pull ghcr.io/jwjinn/mcp-api-agent:latest
kubectl apply -k mcp-api-agent/k8s/overlays/npu
```

배포 후 확인:

```bash
kubectl get pods -n mcp
kubectl logs deployment/mcp-agent-a100 -n mcp
kubectl logs deployment/mcp-agent-npu -n mcp
```

환경에 따라 deployment 이름 suffix는 실제 overlay 결과에 맞춰 확인하세요.

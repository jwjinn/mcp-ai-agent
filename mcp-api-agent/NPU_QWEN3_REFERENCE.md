# NPU Qwen3 Reference Deployment

이 문서는 다음 실제 운영 조건을 기준으로 MCP API Agent를 어떻게 설정하면 좋은지 정리한 레퍼런스입니다.

## 기준 환경

- Kubernetes `v1.29.12`
- control-plane 1대, worker 2대
- NPU vLLM 파드 2개
- `worker-01`: Instruct 역할
- `worker-02`: Thinking 역할
- Observability 및 MCP 서버는 별도 네임스페이스/서비스로 이미 동작 중

사용자가 제공한 정보 기준으로 핵심 조건은 아래와 같습니다.

- Instruct endpoint:
  - 서비스: `qwen3-vllm-worker01.npu-dashboard`
  - 모델: `/compiled/qwen3-8b-instruct`
  - vLLM: `--max-model-len 8192 --max-num-seqs 4`
- Thinking endpoint:
  - 서비스: `qwen3-vllm-worker02.npu-dashboard`
  - 모델: `/compiled/qwen3-8b-thinking`
  - vLLM: `--max-model-len 8192 --max-num-seqs 4`

즉, A100 시절보다 훨씬 보수적으로 토큰 예산을 잡아야 하는 환경입니다.

---

## 1. 이 앱에서 Instruct / Thinking은 자동 선택인가

결론부터 말하면, `모델 서버가 알아서 역할을 선택하는 구조는 아닙니다`.

이 애플리케이션은 코드 내부에서 역할을 분리합니다.

- `Router`, `SimpleAgent`, `Orchestrator`, `Workers`는 `INSTRUCT_CONFIG`를 사용
- `Synthesizer`는 `THINKING_CONFIG`를 사용

즉 "어떤 모델을 어떤 역할에 쓸지"는 Kubernetes 설정의 `INSTRUCT_CONFIG`, `THINKING_CONFIG`가 결정합니다.

그래서 지금 환경에서는 아래처럼 명시적으로 나누는 것이 가장 안전합니다.

- `INSTRUCT_CONFIG.model_name = /compiled/qwen3-8b-instruct`
- `THINKING_CONFIG.model_name = /compiled/qwen3-8b-thinking`

이유:

- Instruct 모델은 빠른 분류, 툴 호출, JSON 생성에 적합
- Thinking 모델은 최종 종합 진단에 적합
- 두 vLLM 파드가 이미 역할별로 분리되어 있어 구조가 코드와 잘 맞음

---

## 2. 왜 토큰 값을 줄여야 하나

주어진 vLLM 설정은 두 모델 모두 아래와 같습니다.

```bash
--max-model-len 8192
--max-num-seqs 4
```

여기서 중요한 것은 `max-model-len=8192`입니다.

이 값 안에 다음이 모두 들어가야 합니다.

- 시스템 프롬프트
- 사용자 질문
- worker 결과 요약
- 모델 출력 토큰

즉 `출력`을 너무 크게 잡으면 `입력`이 부족해지고,
`입력`을 너무 크게 잡으면 `출력` 시점에 터질 수 있습니다.

또한 NPU 환경에서는 A100 시절보다 "큰 컨텍스트를 한 번에 밀어넣는 전략"보다
"조금 더 자주 자르더라도 안정적으로 응답하는 전략"이 훨씬 안전합니다.

---

## 3. 추천 설정값

아래 값은 "첫 배포용 안전한 시작점"입니다.

### 추천 `config.json`

```json
{
  "MCP_SERVERS": [
    {"name": "k8s", "url": "http://mcp-k8s-svc.mcp/sse"},
    {"name": "vlogs", "url": "http://mcp-vlogs-svc.mcp/sse"},
    {"name": "vm", "url": "http://mcp-vm-svc.mcp/sse"},
    {"name": "vtraces", "url": "http://mcp-vtraces-svc.mcp/sse"}
  ],
  "INSTRUCT_CONFIG": {
    "base_url": "http://qwen3-vllm-worker01.npu-dashboard.svc.cluster.local/v1",
    "model_name": "/compiled/qwen3-8b-instruct",
    "api_key": "EMPTY",
    "default_headers": {},
    "temperature": 0,
    "context_window": 8192,
    "max_input_tokens": 4096,
    "max_output_tokens": 1024
  },
  "THINKING_CONFIG": {
    "base_url": "http://qwen3-vllm-worker02.npu-dashboard.svc.cluster.local/v1",
    "model_name": "/compiled/qwen3-8b-thinking",
    "api_key": "EMPTY",
    "default_headers": {},
    "temperature": 0,
    "context_window": 8192,
    "max_input_tokens": 6144,
    "max_output_tokens": 1536
  },
  "RUNTIME_LIMITS": {
    "router_keep_last": 5,
    "simple_keep_last": 10,
    "max_ai_steps": 10,
    "worker_summary_quota": 1500,
    "max_total_context": 6000,
    "mcp_tool_max_output_chars": 6000,
    "worker_raw_result_max_chars": 5000
  }
}
```

---

## 4. 왜 이 값을 추천하나

### `INSTRUCT_CONFIG.context_window = 8192`

이건 vLLM의 `--max-model-len 8192`와 맞춰주는 값입니다.

의미:

- 운영자가 "이 모델은 8k급으로 다룬다"는 것을 설정상 명확히 남기는 용도

### `INSTRUCT_CONFIG.max_input_tokens = 4096`

Instruct 경로는 Router, Worker, 요약 프롬프트 등 짧고 빈번한 호출이 많습니다.

너무 크게 두면:

- worker summarization 입력이 커져 지연이 길어짐
- JSON 생성 안정성이 떨어질 수 있음

그래서 8k 전체를 다 쓰지 않고 절반 수준인 `4096`으로 시작하는 것이 안전합니다.

### `INSTRUCT_CONFIG.max_output_tokens = 1024`

Instruct 쪽은 긴 문학적 답변보다 다음이 중요합니다.

- 분류
- 도구 호출
- 짧은 JSON
- 구조화된 요약

즉 출력은 길지 않아도 충분합니다.

1024면 충분한 경우가 대부분이고, 입력 예산도 더 확보됩니다.

### `THINKING_CONFIG.max_input_tokens = 6144`

Thinking 쪽은 최종 Synthesizer에서 worker 결과를 모아 종합할 때 가장 많은 입력을 씁니다.

하지만 `8192`를 전부 입력으로 주면 출력 공간이 부족해집니다.

그래서:

- 입력 6144
- 출력 1536
- 나머지는 프롬프트 오버헤드 및 여유

처럼 잡는 것이 첫 시작점으로 안전합니다.

### `THINKING_CONFIG.max_output_tokens = 1536`

Thinking 모델은 너무 짧으면 분석이 잘리지만,
너무 길면 NPU 환경에서 응답 시간이 길어지고 불안정해질 수 있습니다.

`1536`은 다음 균형을 고려한 값입니다.

- 진단형 답변을 하기엔 충분
- 8k 한도 안에서 입력을 너무 잠식하지 않음

처음에는 `1536`으로 시작하고, 답변이 너무 짧게 끊기면 `2048`까지 올려보는 것을 추천합니다.

### `simple_keep_last = 10`

기존 15보다 줄였습니다.

이유:

- 8k 컨텍스트에서는 대화 기록을 너무 많이 들고 가면 실제 툴 결과보다 히스토리가 더 큰 비중을 차지할 수 있음
- Simple path는 긴 문맥보다 "최근 대화 + 현재 요청"이 더 중요함

### `worker_summary_quota = 1500`

기존 2000보다 줄였습니다.

이유:

- worker 3개 결과가 모두 길면 Thinking 입력이 빠르게 커짐
- 1500 x 3 = 4500자 수준이면 최종 synthesizer가 아직 안정적으로 다룰 가능성이 높음

### `max_total_context = 6000`

기존 10000보다 줄였습니다.

이유:

- NPU 8k 환경에서 최종 Thinking prompt가 너무 커지지 않도록 전역 상한을 낮춰야 함

### `mcp_tool_max_output_chars = 6000`
### `worker_raw_result_max_chars = 5000`

기존 A100 계열 기본값보다 줄였습니다.

이유:

- Observability 결과는 매우 쉽게 길어짐
- 긴 raw output은 결국 worker summarization 단계에서 다시 잘리므로, 초기에 더 보수적으로 자르는 편이 전체 안정성에 유리함

---

## 5. 왜 `mcp-agent`를 NPU 노드에 강제로 올리지 않는가

중요한 포인트입니다.

`mcp-agent` 컨테이너는 직접 NPU 연산을 하지 않습니다.

이 컨테이너가 하는 일은:

- MCP 서버에 HTTP/SSE 연결
- vLLM endpoint에 HTTP 요청
- LangGraph 오케스트레이션

즉 NPU가 필요한 것은 `qwen3-vllm-worker01`, `qwen3-vllm-worker02`이고,
`mcp-agent` 자체는 CPU만 있어도 됩니다.

그래서 기본 권장값은:

- `mcp-agent`에는 NPU 리소스 요청을 걸지 않음
- `mcp-agent`를 NPU 노드로 강제 pinning하지 않음

이유:

- 스케줄링이 더 유연해짐
- NPU 노드 자원을 추론 파드에 집중 가능
- `accelerator=npu` 같은 라벨이 없을 때 배포 실패를 피할 수 있음

정말 같은 노드에 붙여 네트워크 locality를 노리고 싶을 때만 별도 nodeSelector를 고려하세요.

---

## 6. 실제 배포 순서

### 6.1 `configmap-patch.yaml` 수정

`mcp-api-agent/k8s/overlays/npu/configmap-patch.yaml`에 위 추천값을 반영합니다.

핵심 포인트:

- `base_url`은 서비스 FQDN 사용
- `default_headers`는 비워도 됨
- 모델명은 pod 내 실제 vLLM serve 경로와 동일하게 설정

### 6.2 `deployment-patch.yaml` 확인

기본 권장:

- nodeSelector 없음

즉 mcp-agent는 아무 일반 노드에서 떠도 됩니다.

### 6.3 배포

```bash
kubectl apply -k mcp-api-agent/k8s/overlays/npu
```

### 6.4 확인

```bash
kubectl get pods -n mcp
kubectl logs deployment/mcp-agent-npu -n mcp
kubectl get svc -n npu-dashboard
```

로그에서 먼저 볼 것:

- MCP 서버 연결 성공 여부
- Instruct endpoint 연결 성공 여부
- Thinking endpoint 연결 성공 여부

---

## 7. 첫 테스트 시나리오

처음에는 무거운 종합 진단보다 아래 순서가 좋습니다.

### 1단계

단순 질의:

- "현재 시간 알려줘"
- "mcp 네임스페이스 파드 목록 보여줘"

목적:

- Router / SimpleAgent / MCP server 연결 검증

### 2단계

가벼운 분석:

- "worker-01 쪽 vLLM 상태 요약해줘"

목적:

- Instruct + MCP 툴 조합 검증

### 3단계

종합 진단:

- "현재 NPU inference 환경 전반 상태를 진단해줘"

목적:

- Thinking 모델 입력 길이, synthesizer 안정성 검증

---

## 8. 문제가 생기면 어떻게 조정할까

### 응답이 너무 잘리면

순서:

1. `THINKING_CONFIG.max_output_tokens`를 `1536 -> 2048`
2. 그래도 불충분하면 `worker_summary_quota`를 `1500 -> 1800`

### Thinking이 자주 터지면

순서:

1. `THINKING_CONFIG.max_input_tokens`를 `6144 -> 5120`
2. `max_total_context`를 `6000 -> 5000`
3. `worker_summary_quota`를 `1500 -> 1200`

### Worker 요약이 자주 잘리면

순서:

1. `INSTRUCT_CONFIG.max_input_tokens`를 `4096 -> 4608`
2. `worker_raw_result_max_chars`를 `5000 -> 6000`

단, 이 경우 전체 latency는 늘어날 수 있습니다.

---

## 9. 최종 추천 요약

이 환경에서는 아래 방향이 가장 합리적입니다.

1. `worker01 = instruct`, `worker02 = thinking`으로 명시적 분리
2. `max-model-len=8192`에 맞춰 A100 때보다 보수적으로 설정
3. `mcp-agent`는 NPU 노드에 강제 배치하지 않음
4. 처음에는 작은 context로 안정성 확보 후 점진적으로 완화

이 문서의 값은 "첫 배포용 안정 설정"입니다.
한 번 띄운 뒤 실제 로그와 응답 길이를 보고 미세 조정하면 됩니다.

# Documentation Map

이 문서는 현재 기준으로 "어떤 문서를 먼저 읽어야 하는지"를 정리한 안내서입니다.

## 먼저 읽기

### 1. 전체 개요

- [`README.md`](../README.md)

이 문서에서 알 수 있는 것:

- 이 프로젝트가 무엇인지
- 현재 구조가 왜 `공통 코드 + 환경별 설정`인지
- 지금 어디서부터 읽으면 되는지

### 2. 실제 배포 절차

- [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md)

이 문서에서 알 수 있는 것:

- `ghcr.io/jwjinn/mcp-api-agent:latest` 이미지를 어떻게 배포하는지
- `ConfigMap`, `Deployment`, `Service`가 각각 무슨 역할인지
- 왜 `INSTRUCT_CONFIG`, `THINKING_CONFIG`, `RUNTIME_LIMITS`가 필요한지
- 왜 A100/NPU를 브랜치가 아니라 overlay로 분리하는지

### 3. 실제 NPU 레퍼런스

- [`NPU_QWEN3_REFERENCE.md`](NPU_QWEN3_REFERENCE.md)

이 문서에서 알 수 있는 것:

- 실제 `qwen3-vllm-worker01`, `qwen3-vllm-worker02` 구조에서 어떤 값을 추천하는지
- 왜 `8192` 기준에서 A100 때보다 더 보수적으로 설정해야 하는지
- 왜 `mcp-agent`는 NPU 노드에 강제 배치하지 않는지

### 4. 로컬 실행 / API 테스트

- [`FastAPI_Run_Test_Guide.md`](FastAPI_Run_Test_Guide.md)

이 문서에서 알 수 있는 것:

- 로컬에서 어떻게 서버를 띄우는지
- `/api/chat`, `/api/stream_chat`, `/v1/chat/completions`를 어떻게 테스트하는지
- 현재 어떤 테스트 경로를 우선 추천하는지

## 그 다음 읽기

### 초보자용 설명 문서

- [`paper/1_BACKGROUND_AND_WHY.md`](../paper/1_BACKGROUND_AND_WHY.md)
- [`paper/2_CORE_ARCHITECTURE.md`](../paper/2_CORE_ARCHITECTURE.md)
- [`paper/3_CODE_WALKTHROUGH.md`](../paper/3_CODE_WALKTHROUGH.md)
- [`paper/4_HOW_TO_START_AND_TEST.md`](../paper/4_HOW_TO_START_AND_TEST.md)

용도:

- 프로젝트의 배경과 큰 흐름을 천천히 이해하고 싶을 때

주의:

- 현재 운영 구조보다 설명 중심입니다
- 최신 배포 절차는 반드시 `DEPLOYMENT_GUIDE.md`를 우선 기준으로 삼으세요

## 심화 문서

- [`MCP_Develop_History.md`](MCP_Develop_History.md)
- [`advanced_docs/`](../advanced_docs)
- [`code_advanced_docs/`](../code_advanced_docs)

용도:

- 과거 문제를 어떻게 해결했는지
- 내부 최적화와 프롬프트 설계
- LangGraph 구성 요소 세부 구현

주의:

- 이 문서들은 "왜 이렇게 됐는가"를 이해하는 데 좋지만
- 현재 배포/운영 기준 문서로 바로 사용하진 않는 것이 좋습니다

## 한 줄 요약

현재 운영 기준으로는 아래 순서가 가장 좋습니다.

1. `README.md`
2. `mcp-api-agent/DEPLOYMENT_GUIDE.md`
3. `mcp-api-agent/NPU_QWEN3_REFERENCE.md`
4. `mcp-api-agent/FastAPI_Run_Test_Guide.md`

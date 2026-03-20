# MCP AI Agent

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

[English version](README_en.md) | [한국어버전](README.md)

## 🌟 Introduction

**MCP AI Agent**는 LangGraph 기반의 AI 워크플로우와 **Model Context Protocol (MCP)**를 결합한 지능형 마이크로서비스 및 인프라 오케스트레이션 미들웨어입니다. 이 에이전트는 사용자와의 자연어 대화를 통해 쿠버네티스(Kubernetes) 클러스터, 로그 통합 시스템, 가상 머신(VM) 등의 다양한 백엔드 엔드포인트 도구들을 자율적으로 제어하고 진단할 수 있습니다.

특히, 이중 LLM 모델 환경(**Thinking Model**을 활용한 깊은 추론 및 계획 세우기와 **Instruct Model**을 활용한 빠르고 정확한 도구 실행)을 지원하여, 기존의 단순한 대시보드를 넘어서는 자동화된 인프라 AIOps(Artificial Intelligence for IT Operations) 솔루션을 제공합니다.

---

## � 데모 영상 (Demo Video)

<div align="center">
  <a href="https://youtu.be/isRjLnMHajs">
    <img src="https://img.youtube.com/vi/isRjLnMHajs/maxresdefault.jpg" width="80%" alt="MCP AI Agent Demo">
  </a>
</div>

---

## 📚 문서 읽는 순서

현재 구조 기준으로 가장 먼저 볼 문서는 아래 순서입니다.

👉 **[문서 안내 지도](mcp-api-agent/DOCS_MAP.md)**  
👉 **[운영 배포 가이드](mcp-api-agent/DEPLOYMENT_GUIDE.md)**  
👉 **[NPU Qwen3 실환경 레퍼런스](mcp-api-agent/NPU_QWEN3_REFERENCE.md)**  
👉 **[로컬 실행 / API 테스트 가이드](mcp-api-agent/FastAPI_Run_Test_Guide.md)**

초보자용 설명형 문서는 여전히 유효하지만, 현재 운영 배포 기준은 위 4개 문서를 우선으로 보시는 것을 권장합니다.

👉 **[1. 배경 및 도입 목적 알아보기](paper/1_BACKGROUND_AND_WHY.md)**  
👉 **[2. 핵심 아키텍처 원리](paper/2_CORE_ARCHITECTURE.md)**  
👉 **[3. 코드 투어](paper/3_CODE_WALKTHROUGH.md)**  
👉 **[4. 실전! 내 컴퓨터에서 돌려보기](paper/4_HOW_TO_START_AND_TEST.md)**

## ⚡ 시니어 및 코어 개발자를 위한 딥-다이브 (Advanced Docs)

단순한 튜토리얼을 넘어 **LangGraph의 상태 제어, 메모리 최적화, 비동기 병렬 처리, 그리고 동적 메타프로그래밍**의 정수를 맛보고 싶으시다면 프로젝트 루트의 `advanced_docs/` 디렉토리를 열어보세요.

*   🧠 **[1. State Management & Graph Lifecycle](advanced_docs/1_STATE_MANAGEMENT_AND_GRAPH.md)**: AgentState의 Reducer 설계와 토큰 윈도우 폭발을 막는 Smart Sliding Window 알고리즘.
*   ⚡ **[2. Parallel Workers & Map-Reduce Architecture](advanced_docs/2_PARALLEL_WORKERS_AND_MAP_REDUCE.md)**: `asyncio.gather`를 통한 O(1) 통신 최적화와 Sub-Agent 필터링 기법.
*   🔌 **[3. MCP Dynamic Schema Binding](advanced_docs/3_MCP_CLIENT_DYNAMIC_BINDING.md)**: `pydantic.create_model`을 이용한 런타임 스키마 직조(Metaprogramming) 메커니즘.
*   🎭 **[4. LLM Tuning & Prompt Engineering](advanced_docs/4_LLM_TUNING_AND_PROMPT_ENGINEERING.md)**: 완벽한 JSON 파싱을 위한 Instruct 모델 강제화 및 무한 루프(Hallucination) 차단 튜닝.
*   🔍 **[5. Code Walkthrough (상세 구조 투어)](code_advanced_docs/1_code_walkthrough.md)**: Router부터 Synthesizer까지 LangGraph 오케스트레이션 구성요소 완전 해부.
*   🛠️ **[6. System Architecture & Prompts Deep-Dive](code_advanced_docs/2_system_architecture_deep_dive.md)**: 노드별 숨겨진 프롬프트 원문과 무한 루프, Truncation 보호 메커니즘 분석.
*   🔬 **[7. Detailed Code Execution Flow](code_advanced_docs/3_detailed_code_execution_flow.md)**: 실제 코드를 따라가는 완벽한 변수 추적 및 함수 콜스택 흐름도.

## 🚀 현재 구조 한눈에 보기

현재 버전의 핵심 구조는 아래와 같습니다.

- 공통 코드는 하나의 `master` 기준 코드베이스로 유지합니다.
- A100 / NPU 차이는 브랜치가 아니라 `mcp-api-agent/k8s/overlays/`로 분리합니다.
- 모델별 차이는 `INSTRUCT_CONFIG`, `THINKING_CONFIG`로 분리합니다.
- 과거 장애 경험으로 생긴 보호값은 `RUNTIME_LIMITS`에서 관리합니다.
- 큰 설정은 `ConfigMap(config.json)`에서 관리하고, 급한 조정은 `env`로 override할 수 있습니다.

---

## Architecture

이 프로젝트는 프로덕션 환경에서 원격 Web UI 혹은 다른 서비스들과 통신하기 위한 FastAPI 기반 백엔드 애플리케이션(`mcp-api-agent/`)을 메인으로 제공합니다. 모니터링 대시보드에서 활용할 수 있는 SSE(Server-Sent Events) 스트리밍 기능과 도커(Docker)/쿠버네티스 배포를 지원합니다.

### 요청이 처리되는 방식

현재 요청 흐름은 아래처럼 생각하시면 가장 이해가 쉽습니다.

1. FastAPI 서버가 사용자 요청을 받습니다.
2. `Router`가 이 요청이 단순 조회인지, 종합 진단인지 판단합니다.
3. 단순 조회면 `Instruct 모델`이 바로 도구를 호출합니다.
4. 종합 진단이면 `Orchestrator + Workers`가 병렬로 K8s / Logs / Metrics / Traces를 조회합니다.
5. 마지막에 `Thinking 모델`이 결과를 종합해 최종 진단을 만듭니다.

### 왜 설정이 복잡한가

현재 설정이 `MCP_SERVERS`, `INSTRUCT_CONFIG`, `THINKING_CONFIG`, `RUNTIME_LIMITS`로 나뉘는 이유는 각각 역할이 다르기 때문입니다.

- `MCP_SERVERS`: 어디서 데이터를 가져올지
- `INSTRUCT_CONFIG`: 빠른 분류, JSON 생성, tool calling용 모델 설정
- `THINKING_CONFIG`: 최종 종합 진단용 모델 설정
- `RUNTIME_LIMITS`: 토큰 폭주, context overflow, 무한 루프, 긴 raw output을 막는 보호값

특히 GPU/NPU 환경에서는 모델 서버(vLLM 등)의 `max-model-len`, 응답 특성, 안정성이 다를 수 있어서 이 보호값들을 코드 안이 아니라 배포 설정에서 조정할 수 있게 두는 것이 중요합니다.

### Supported MCP Servers (지원 도구)
에이전트는 다음과 같은 여러 개의 MCP 서버와 동적으로 연결되어 작업합니다:
- **k8s**: 쿠버네티스 클러스터 자원 관리 (Pod 배포, 스케줄링 현황 조회, 삭제 등)
- **VictoriaLog**: 컨테이너 로그 조회 및 시스템 로그 분석
- **VictoriaMetrics**: 가상 머신 프로비저닝 상태 관리
- **VictoriaTrace**: 분산 트레이싱 기록 조회 및 병목 구간 성능 파악

## Prerequisites

오픈소스 환경에서 직접 실행해보기 위해 다음 항목들이 필요합니다:
- Python >= 3.10
- (API 버전의 경우) Docker 및 Kubernetes (>= 1.20)
- 활용 가능한 LLM Endpoint (ex. OpenAI 호환 API 지원 모델, 커스텀 모델 등)

## Quick Start
*(로컬 실행과 실제 API 테스트는 `mcp-api-agent/FastAPI_Run_Test_Guide.md`를 우선 참고하세요.)*

### 1. Configuration Setup (설정 파일 구성)
기본적인 레포지토리를 클론받은 후, 사용자의 환경에 맞게 제공된 템플릿 파일에서 IP 주소 및 API Key를 교체합니다.

```bash
# FastAPI 설정 복사
cp mcp-api-agent/config.example.py mcp-api-agent/config.py
cp mcp-api-agent/config.example.json mcp-api-agent/config.json
```

### 2. Local PC Testing (FastAPI 로컬 환경 테스트)
가장 빠르게 에이전트의 워크플로우를 동작 확인하는 방법입니다. 

1. **Python 가상환경(Conda 등) 구성 및 의존성 추가**
```bash
# Conda 환경 생성 및 활성화
conda create -n mcp-agent python=3.11
conda activate mcp-agent

cd mcp-api-agent
pip install -r requirements_api.txt
```

2. **설정 파일(config.json) 작성**
미리 복사해 둔 `config.json` 파일 내에서 다음 4개 영역을 채웁니다.

- `MCP_SERVERS`
- `INSTRUCT_CONFIG`
- `THINKING_CONFIG`
- `RUNTIME_LIMITS`

가장 중요한 개념은 아래입니다.

- `INSTRUCT_CONFIG`: 빠르게 도구를 호출하고 구조화된 응답을 만드는 모델
- `THINKING_CONFIG`: 최종 종합 진단을 담당하는 모델
- `RUNTIME_LIMITS`: 모델 입력 과다, 긴 로그, 큰 메트릭 응답 때문에 시스템이 터지는 것을 막는 안전장치

`MCP_SERVERS` URL은 **쿠버네티스의 실제 서비스 주소 또는 접근 가능한 SSE endpoint**로 변경합니다.
```json
// mcp-api-agent/config.json 수정 예시
"MCP_SERVERS": [
    {"name": "k8s",             "url": "http://<K8S_NODE_IP>:<NODE_PORT>/sse"},
    {"name": "VictoriaLog",     "url": "http://<K8S_NODE_IP>:<NODE_PORT>/sse"},
]
```

3. **에이전트 API 서버 실행**
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

### 3. Deploying via GHCR (Kubernetes 배포)

운영 배포는 소스 실행보다 `ghcr.io/jwjinn/mcp-api-agent:latest` 이미지를 사용하는 방식을 권장합니다.

현재 권장 방식은 `base + overlays` 구조입니다.

```bash
docker pull ghcr.io/jwjinn/mcp-api-agent:latest

# A100
kubectl apply -k mcp-api-agent/k8s/overlays/a100

# NPU
kubectl apply -k mcp-api-agent/k8s/overlays/npu
```

문서 역할은 이렇게 나뉩니다.

- 실제 배포 절차: `mcp-api-agent/DEPLOYMENT_GUIDE.md`
- NPU Qwen3 실환경 예시: `mcp-api-agent/NPU_QWEN3_REFERENCE.md`
- Kustomize 구조 설명: `mcp-api-agent/k8s/README.md`

현재 버전에서는 단일 YAML보다 `base + overlays` 구조를 기준으로 운영하는 것을 권장합니다.

---
> 현재 운영 기준 문서는 `mcp-api-agent/DOCS_MAP.md`, `mcp-api-agent/DEPLOYMENT_GUIDE.md`, `mcp-api-agent/NPU_QWEN3_REFERENCE.md`입니다.  
> `paper/`, `advanced_docs/`, `MCP_Develop_History.md`는 설명/심화/이력 문서로 보시면 됩니다.

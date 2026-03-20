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

## �📖 초보자 및 기여자를 위한 완벽 가이드 (필독!)

프로젝트의 전체 흐름, 병렬 처리 아키텍처 원리, 그리고 코드가 어떻게 유기적으로 동작하는지 궁금하신가요? 
**초보자분들을 위해 아주 쉽고 친절한 동화책 같은 문서(Paper) 세트를 준비했습니다!** 아래 순서대로 읽어보시는 것을 강력히 권장합니다.

👉 **[1. 배경 및 도입 목적 알아보기 (BACKGROUND AND WHY)](paper/1_BACKGROUND_AND_WHY.md)**  
👉 **[2. 핵심 아키텍처 원리 (CORE ARCHITECTURE)](paper/2_CORE_ARCHITECTURE.md)**  
👉 **[3. 코드 투어 (CODE WALKTHROUGH)](paper/3_CODE_WALKTHROUGH.md)**  
👉 **[4. 실전! 내 컴퓨터에서 돌려보기 (HOW TO START)](paper/4_HOW_TO_START_AND_TEST.md)**

## ⚡ 시니어 및 코어 개발자를 위한 딥-다이브 (Advanced Docs)

단순한 튜토리얼을 넘어 **LangGraph의 상태 제어, 메모리 최적화, 비동기 병렬 처리, 그리고 동적 메타프로그래밍**의 정수를 맛보고 싶으시다면 프로젝트 루트의 `advanced_docs/` 디렉토리를 열어보세요.

*   🧠 **[1. State Management & Graph Lifecycle](advanced_docs/1_STATE_MANAGEMENT_AND_GRAPH.md)**: AgentState의 Reducer 설계와 토큰 윈도우 폭발을 막는 Smart Sliding Window 알고리즘.
*   ⚡ **[2. Parallel Workers & Map-Reduce Architecture](advanced_docs/2_PARALLEL_WORKERS_AND_MAP_REDUCE.md)**: `asyncio.gather`를 통한 O(1) 통신 최적화와 Sub-Agent 필터링 기법.
*   🔌 **[3. MCP Dynamic Schema Binding](advanced_docs/3_MCP_CLIENT_DYNAMIC_BINDING.md)**: `pydantic.create_model`을 이용한 런타임 스키마 직조(Metaprogramming) 메커니즘.
*   🎭 **[4. LLM Tuning & Prompt Engineering](advanced_docs/4_LLM_TUNING_AND_PROMPT_ENGINEERING.md)**: 완벽한 JSON 파싱을 위한 Instruct 모델 강제화 및 무한 루프(Hallucination) 차단 튜닝.
*   🔍 **[5. Code Walkthrough (상세 구조 투어)](code_advanced_docs/1_code_walkthrough.md)**: Router부터 Synthesizer까지 LangGraph 오케스트레이션 구성요소 완전 해부.
*   🛠️ **[6. System Architecture & Prompts Deep-Dive](code_advanced_docs/2_system_architecture_deep_dive.md)**: 노드별 숨겨진 프롬프트 원문과 무한 루프, Truncation 보호 메커니즘 분석.
*   🔬 **[7. Detailed Code Execution Flow](code_advanced_docs/3_detailed_code_execution_flow.md)**: 실제 코드를 따라가는 완벽한 변수 추적 및 함수 콜스택 흐름도.

## 🚀 배포 가이드

운영 배포 절차와 설정값의 의미를 자세히 보고 싶다면 아래 문서를 참고하세요.

👉 **[Kubernetes 배포 가이드](mcp-api-agent/DEPLOYMENT_GUIDE.md)**

---

## Architecture

이 프로젝트는 프로덕션 환경에서 원격 Web UI 혹은 다른 서비스들과 통신하기 위한 FastAPI 기반 백엔드 애플리케이션(`mcp-api-agent/`)을 메인으로 제공합니다. 모니터링 대시보드에서 활용할 수 있는 SSE(Server-Sent Events) 스트리밍 기능과 도커(Docker)/쿠버네티스 배포를 지원합니다.

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
*(로컬 실행 튜토리얼을 더 깊게 이해하고 싶다면 `paper/4_HOW_TO_START_AND_TEST.md`를 참고하세요.)*

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
미리 복사해 둔 `config.json` 파일 내의 `MCP_SERVERS` URL을 **쿠버네티스의 NodePort 주소**로 변경합니다.
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
실제 운영 환경이나 원격 서버에 배포할 때는 소스코드를 직접 실행하지 않고 **빌드된 공식 퍼블릭 패키지 이미지**를 이용합니다. `mcp-api-agent` 폴더 내에 변경 사항이 발생하면 GitHub Actions를 통해 자동으로 GHCR(GitHub Container Registry)에 최신 Docker 이미지가 배포됩니다.

하드웨어별 배포 차이는 `mcp-api-agent/k8s/` 아래의 Kustomize overlay로 분리해 두는 것을 권장합니다.

```bash
# A100 환경
kubectl apply -k mcp-api-agent/k8s/overlays/a100

# NPU 환경
kubectl apply -k mcp-api-agent/k8s/overlays/npu
```

`base/`에는 공통 Deployment/Service/ConfigMap을 두고, `overlays/a100`, `overlays/npu`에서는 모델 endpoint, 헤더, 스케줄링 정책 같은 환경별 값만 덮어씁니다.

기존처럼 단일 YAML로 관리하고 싶다면 아래 예시를 참고할 수 있지만, 신규 운영 환경 추가 시에는 overlay 구조가 훨씬 관리하기 쉽습니다.

아래 통합 배포 가이드(ConfigMap + Deployment) 매니페스트 예시는 레거시 단일 매니페스트 예시입니다.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-api-agent-config
  namespace: mcp
  labels:
    app: mcp-api-agent
data:
  config.json: |
    {
      "MCP_SERVERS": [
        {"name": "k8s",             "url": "http://mcp-k8s-svc.mcp/sse"},
        {"name": "VictoriaLog",     "url": "http://mcp-vlogs-svc.mcp/sse"},
        {"name": "VictoriaMetrics", "url": "http://mcp-vm-svc.mcp/sse"},
        {"name": "VictoriaTrace",   "url": "http://mcp-vtraces-svc.mcp/sse"}
      ],
      "INSTRUCT_CONFIG": {
        "base_url": "http://127.0.0.1:80/v1",
        "model_name": "qwen-custom",
        "api_key": "EMPTY",
        "default_headers": {"Host": "qwen-instruct.example.com"},
        "temperature": 0
      },
      "THINKING_CONFIG": {
        "base_url": "http://127.0.0.1:80/v1",
        "model_name": "qwen-thinking",
        "api_key": "EMPTY",
        "default_headers": {"Host": "qwen-thinking.example.com"},
        "temperature": 0
      }
    }
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-api-agent-deployment
  namespace: mcp
  labels:
    app: mcp-api-agent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mcp-api-agent
  template:
    metadata:
      labels:
        app: mcp-api-agent
    spec:
      containers:
      - name: mcp-api-agent
        # 생성된 공식 패키지 이미지를 사용합니다.
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
        ports:
        - containerPort: 8000
      volumes:
      - name: config-volume
        configMap:
          name: mcp-api-agent-config
```

작성한 매니페스트를 쿠버네티스 클러스터에 적용합니다:

```bash
kubectl apply -f manifest.yaml
```

---
> 과거 개발 프로세스, 트러블슈팅 이력 및 쿠버네티스 YAML 배포에 관한 심화 내용은 `mcp-api-agent/MCP_Develop_History.md`를 참고해 주시고, 영문 문서는 `README_en.md`를 확인하세요.

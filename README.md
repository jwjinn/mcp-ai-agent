# MCP AI Agent

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

[English version](#) | [한국어버전](#)

## Introduction

**MCP AI Agent**는 LangGraph 기반의 AI 워크플로우와 **Model Context Protocol (MCP)**를 결합한 지능형 마이크로서비스 및 인프라 오케스트레이션 미들웨어입니다. 이 에이전트는 사용자와의 자연어 대화를 통해 쿠버네티스(Kubernetes) 클러스터, 로그 통합 시스템, 가상 머신(VM) 등의 다양한 백엔드 엔드포인트 도구들을 자율적으로 제어하고 진단할 수 있습니다.

특히, 이중 LLM 모델 환경(**Thinking Model**을 활용한 깊은 추론 및 계획 세우기와 **Instruct Model**을 활용한 빠르고 정확한 도구 실행)을 지원하여, 기존의 단순한 대시보드를 넘어서는 자동화된 인프라 AIOps(Artificial Intelligence for IT Operations) 솔루션을 제공합니다.

## Architecture

프로젝트는 용도에 맞게 두 개의 주요 컴포넌트로 나뉘어져 있습니다:

- **`mcp-cli-agent/`**: 터미널에서 에이전트와 직접 상호작용하고, 툴이나 프롬프트 변경사항을 즉각적으로 테스트하기 위한 경량화된 파이썬 CLI 환경입니다.
- **`mcp-dockerized-api/`**: 프로덕션 환경에서 원격 Web UI 혹은 다른 서비스들과 통신하기 위한 FastAPI 기반 백엔드 애플리케이션입니다. 모니터링 대시보드에서 활용할 수 있는 SSE(Server-Sent Events) 스트리밍 기능과 도커(Docker)/쿠버네티스 배포를 지원합니다.

### Supported MCP Servers (지원 도구)
에이전트는 다음과 같은 여러 개의 MCP 서버와 동적으로 연결되어 작업합니다:
- **k8s**: 쿠버네티스 클러스터 자원 관리 (Pod 배포, 스케줄링 현황 조회, 삭제 등)
- **vlogs**: 컨테이너 로그 조회 및 시스템 로그 분석
- **vm**: 가상 머신 프로비저닝 상태 관리
- **vtraces**: 분산 트레이싱 기록 조회 및 병목 구간 성능 파악

## Prerequisites

오픈소스 환경에서 직접 실행해보기 위해 다음 항목들이 필요합니다:
- Python >= 3.10
- (API 버전의 경우) Docker 및 Kubernetes (>= 1.20)
- 활용 가능한 LLM Endpoint (ex. OpenAI 호환 API 지원 모델, 커스텀 모델 등)

## Quick Start

### 1. Configuration Setup (설정 파일 구성)
기본적인 레포지토리를 클론받은 후, 사용자의 환경에 맞게 제공된 템플릿 파일에서 IP 주소 및 API Key를 교체합니다.

```bash
# CLI 버전 설정 복사
cp mcp-cli-agent/config.example.py mcp-cli-agent/config.py

# FastAPI 버전 설정 복사
cp mcp-dockerized-api/config.example.py mcp-dockerized-api/config.py
cp mcp-dockerized-api/config.example.json mcp-dockerized-api/config.json
```

### 2. Running the CLI Agent (로컬에서 CLI 실행)
가장 빠르게 에이전트의 워크플로우를 동작 확인하는 방법입니다.

```bash
cd mcp-cli-agent
pip install -r requirements.txt
python main.py
```

### 3. Deploying the API Server (도커 및 K8s 배포)
프론트엔드 대시보드와 연동하기 위한 REST & SSE API 서버를 배포합니다.

```bash
cd mcp-dockerized-api

# Docker 이미지 빌드 및 단일 실행
docker build -t mcp-ai-agent:latest .
docker run -p 8000:8000 -v $(pwd)/config.json:/app/config/config.json mcp-ai-agent:latest

# 쿠버네티스로 배포하는 경우 (제공된 매니페스트 활용)
kubectl apply -f k8s-manifest.yaml
```

## Monitor & WebUI Integration

`mcp-dockerized-api`는 백엔드 내부에서 발생하고 있는 복잡한 에이전트 호출 및 도구 연계 과정을 실시간 스트리밍(Streaming)으로 프론트엔드에 전달합니다. 내부 API에서는 상태 메시지 방송(Broadcast) 큐를 통해 다음과 같은 처리 상황을 사용자가 볼 수 있게 합니다.
* *"k8s 도구를 사용하여 Pod 리스트를 조회 중입니다..."*
* *"로그 분석을 위해 최대 4k 토큰 이내로 요약을 진행하고 있습니다..."*

이와 관련된 디버깅 로그를 파악하고 싶다면 컨테이너 환경변수에 `LOG_LEVEL=DEBUG`를 추가하세요.

## Notes
- 보안 목적으로 초기 구성 파일들은 `.gitignore`에 등록되어 있습니다. K8s의 경우, K8s Manifest 파일 내 ConfigMap으로 덮어씌워 사용할 수 있습니다.
- 현재 버전에선 Thinking 모델과 Instruct 모델을 혼합 사용하는 구조를 기본으로 설계했습니다. `max_tokens` 제어 등을 통해 메모리 초과를 방지합니다.

## RoadMap, Governance & Contributing

- 현재 개발 로드맵으로는 더 많은 프로바이더(플러그인) 지원 확장 및 모니터링 시스템 스케줄 최적화가 계획되어 있습니다.
- 기여(Contribution) 및 패치 작성을 희망하시는 분들은 이슈와 PR(Pull Request)을 이용해 주세요. 어떠한 피드백이나 개선안 제안도 환영합니다. 

## License
MCP AI Agent 프로젝트는 [Apache 2.0 license](LICENSE) 정책을 따릅니다. 상세한 부분은 프로젝트에 포함된 라이선스 문서를 참조해 주시길 바랍니다.

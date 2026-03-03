# MCP AI Agent

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

[English version](README_en.md) | [한국어버전](README.md)

## 🌟 Introduction

**MCP AI Agent**는 LangGraph 기반의 AI 워크플로우와 **Model Context Protocol (MCP)**를 결합한 지능형 마이크로서비스 및 인프라 오케스트레이션 미들웨어입니다.

기존의 답답하고 수동적인 모니터링 대시보드를 넘어, 대화 한 번으로 쿠버네티스 장애 원인을 꿰뚫어 보는 **혁신적인 AIOps(Artificial Intelligence for IT Operations) 솔루션**입니다.

## 📖 초보자 및 기여자를 위한 완벽 가이드 (필독!)

이 프로젝트에 처음 오셨나요? 코드가 어떻게 돌아가는지, 왜 이런 아키텍처를 만들었는지 궁금하신가요? 

**저희가 초보자분들을 위해 아주 쉽고 친절한 동화책 같은 문서(Paper) 세트를 준비했습니다!** 아래 순서대로 읽어보시는 것을 강력히 권장합니다.

👉 **[1. 배경 및 도입 목적 알아보기 (BACKGROUND AND WHY)](paper/1_BACKGROUND_AND_WHY.md)**
- 왜 단순한 ChatGPT로는 인프라 진단을 못 하는지, 우리가 겪은 3가지 끔찍한 문제와 해결책을 아주 쉽게 설명합니다.

👉 **[2. 핵심 아키텍처 원리 (CORE ARCHITECTURE)](paper/2_CORE_ARCHITECTURE.md)**
- 팀장, 요약 요정, 셜록 홈즈? 재미있는 다이어그램과 함께 이 AI 비서들이 어떻게 "동시에" 협력해서 진단하는지 구경하세요!

👉 **[3. 코드 투어 (CODE WALKTHROUGH)](paper/3_CODE_WALKTHROUGH.md)**
- 방금 본 아키텍처가 실제 파이썬 코드(`agent_graph.py`, `api_server.py`)로 어떻게 구현되어 있는지 옆에서 과외하듯 훑어줍니다.

👉 **[4. 실전! 내 컴퓨터에서 돌려보기 (HOW TO START)](paper/4_HOW_TO_START_AND_TEST.md)**
- 이론은 끝났습니다! 파이썬 가상환경 셋팅부터 실제 터미널을 열고 질문을 던져보는 가장 꼼꼼한 튜토리얼입니다.

---

## ⚡ 시니어 및 코어 개발자를 위한 딥-다이브 (Advanced Docs)

단순한 튜토리얼을 넘어 **LangGraph의 상태 제어, 메모리 최적화, 비동기 병렬 처리, 그리고 동적 메타프로그래밍**의 정수를 맛보고 싶으시다면 프로젝트 루트의 `advanced_docs/` 디렉토리를 열어보세요.

*   🧠 **[1. State Management & Graph Lifecycle](advanced_docs/1_STATE_MANAGEMENT_AND_GRAPH.md)**: AgentState의 Reducer 설계와 토큰 윈도우 폭발을 막는 Smart Sliding Window 알고리즘.
*   ⚡ **[2. Parallel Workers & Map-Reduce Architecture](advanced_docs/2_PARALLEL_WORKERS_AND_MAP_REDUCE.md)**: `asyncio.gather`를 통한 O(1) 통신 최적화와 Sub-Agent 필터링 기법.
*   🔌 **[3. MCP Dynamic Schema Binding](advanced_docs/3_MCP_CLIENT_DYNAMIC_BINDING.md)**: `pydantic.create_model`을 이용한 런타임 스키마 직조(Metaprogramming) 메커니즘.
*   🎭 **[4. LLM Tuning & Prompt Engineering](advanced_docs/4_LLM_TUNING_AND_PROMPT_ENGINEERING.md)**: 완벽한 JSON 파싱을 위한 Instruct 모델 강제화 및 무한 루프(Hallucination) 차단 튜닝.

---

> 과거 개발 프로세스, 트러블슈팅 이력 및 쿠버네티스 YAML 배포에 관한 심화 내용은 `mcp-api-agent/MCP_Develop_History.md`를 참고해 주시고, 영문 문서는 `README_en.md`를 확인하세요.

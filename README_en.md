# MCP AI Agent

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

[English version](README_en.md) | [한국어버전](README.md)

## 🌟 Introduction

**MCP AI Agent** is an intelligent microservice and infrastructure orchestration middleware that combines LangGraph-based AI workflows with the **Model Context Protocol (MCP)**. This agent allows users to autonomously control and diagnose various backend endpoint tools—such as Kubernetes clusters, unified logging systems, and Virtual Machines (VMs)—through natural language conversations.

Notably, it supports a dual LLM environment: a **Thinking Model** for deep reasoning and planning, and an **Instruct Model** for fast and precise tool execution. This provides an automated AIOps (Artificial Intelligence for IT Operations) solution that goes far beyond traditional static dashboards.

---

## 📺 Demo Video

<div align="center">
  <a href="https://youtu.be/isRjLnMHajs">
    <img src="https://img.youtube.com/vi/isRjLnMHajs/maxresdefault.jpg" width="80%" alt="MCP AI Agent Demo">
  </a>
</div>

---

## 📚 Reading Order

For the current production-oriented structure, start with these documents first:

👉 **[Documentation Map](mcp-api-agent/DOCS_MAP.md)**  
👉 **[Deployment Guide](mcp-api-agent/DEPLOYMENT_GUIDE.md)**  
👉 **[NPU Qwen3 Reference](mcp-api-agent/NPU_QWEN3_REFERENCE.md)**  
👉 **[FastAPI Run / API Test Guide](mcp-api-agent/FastAPI_Run_Test_Guide.md)**

The beginner-friendly paper series is still useful, but the documents above are the current operational baseline.

👉 **[1. Background and Why](paper/1_BACKGROUND_AND_WHY.md)**  
👉 **[2. Core Architecture](paper/2_CORE_ARCHITECTURE.md)**  
👉 **[3. Code Walkthrough](paper/3_CODE_WALKTHROUGH.md)**  
👉 **[4. How to Start and Test](paper/4_HOW_TO_START_AND_TEST.md)**

## ⚡ Deep-Dive for Senior & Core Developers (Advanced Docs)

If you want to go beyond the tutorial and taste the essence of **LangGraph state control, memory optimization, asynchronous parallel processing, and dynamic metaprogramming**, open the `advanced_docs/` directory at the project root.

*   🧠 **[1. State Management & Graph Lifecycle](advanced_docs/1_STATE_MANAGEMENT_AND_GRAPH_en.md)**: AgentState Reducer design and the Smart Sliding Window algorithm to prevent Token Window overflow.
*   ⚡ **[2. Parallel Workers & Map-Reduce Architecture](advanced_docs/2_PARALLEL_WORKERS_AND_MAP_REDUCE_en.md)**: O(1) communication optimization via `asyncio.gather` and Sub-Agent filtering techniques.
*   🔌 **[3. MCP Dynamic Schema Binding](advanced_docs/3_MCP_CLIENT_DYNAMIC_BINDING_en.md)**: Runtime schema weaving (Metaprogramming) mechanisms using `pydantic.create_model`.
*   🎭 **[4. LLM Tuning & Prompt Engineering](advanced_docs/4_LLM_TUNING_AND_PROMPT_ENGINEERING_en.md)**: Forcing Instruct models for perfect JSON parsing and defense tuning against infinite loops (Hallucination).
*   🔍 **[5. Code Walkthrough](code_advanced_docs/1_code_walkthrough_en.md)**: A complete anatomy of the LangGraph orchestration components, from Router to Synthesizer.
*   🛠️ **[6. System Architecture & Prompts Deep-Dive](code_advanced_docs/2_system_architecture_deep_dive_en.md)**: Analysis of hidden raw prompts per node, loop prevention, and Truncation protection mechanisms.
*   🔬 **[7. Detailed Code Execution Flow](code_advanced_docs/3_detailed_code_execution_flow_en.md)**: A perfect variable tracking and function call-stack flow chart following the actual code.

## 🚀 Current Structure At A Glance

The current version is organized around a few simple rules:

- Keep one shared codebase on `master`
- Separate A100 / NPU differences with `mcp-api-agent/k8s/overlays/`
- Separate model roles with `INSTRUCT_CONFIG` and `THINKING_CONFIG`
- Keep runtime guardrails in `RUNTIME_LIMITS`
- Store the main settings in `ConfigMap(config.json)` and use `env` only for targeted overrides

---

## Architecture

This project primarily provides a FastAPI-based backend application (`mcp-api-agent/`) designed for production environments to communicate with remote Web UIs or other services. It supports Server-Sent Events (SSE) streaming for monitoring dashboards and is fully ready for Docker/Kubernetes deployment.

### How A Request Flows

The current request flow is easiest to understand like this:

1. FastAPI receives a user request.
2. The `Router` decides whether it is a simple lookup or a full diagnosis.
3. For simple requests, the `Instruct` model calls tools directly.
4. For complex requests, `Orchestrator + Workers` query K8s / Logs / Metrics / Traces in parallel.
5. The `Thinking` model synthesizes the final diagnosis.

### Why The Settings Are Split

The current configuration is split because each section has a different responsibility:

- `MCP_SERVERS`: where the data comes from
- `INSTRUCT_CONFIG`: fast routing, JSON generation, and tool-calling model settings
- `THINKING_CONFIG`: final diagnosis model settings
- `RUNTIME_LIMITS`: guardrails against token overflow, long raw outputs, loops, and unstable prompts

This matters especially in GPU/NPU environments where model-serving limits such as `max-model-len` and real runtime stability can differ across clusters.

### Supported MCP Servers
The agent dynamically connects and operates with several MCP servers as follows:
- **k8s**: Kubernetes cluster resource management (Pod deployment, scheduling status lookups, deletions, etc.)
- **VictoriaLog**: Container log retrieval and system log analysis
- **VictoriaMetrics**: Virtual machine provisioning status management
- **VictoriaTrace**: Distributed tracing record retrieval and bottleneck performance identification

## Prerequisites

To run the agent directly in an open-source environment, you will need:
- Python >= 3.10
- Docker and Kubernetes (>= 1.20) (for the API version)
- An available LLM Endpoint (e.g., OpenAI-compatible API supported models, custom models, etc.)

## Quick Start
*(For the current local run and API test flow, use `mcp-api-agent/FastAPI_Run_Test_Guide.md` first.)*

### 1. Configuration Setup
After cloning the repository, replace the IP addresses and API Keys in the provided template files to match your environment.

```bash
# Copy FastAPI version configuration
cp mcp-api-agent/config.example.py mcp-api-agent/config.py
cp mcp-api-agent/config.example.json mcp-api-agent/config.json
```

### 2. Local PC Testing
The fastest way to verify the agent's API server locally.

1. **Set up a Python Virtual Environment (e.g., Conda) and Install Dependencies**
```bash
# Create and activate a Conda environment
conda create -n mcp-agent python=3.11
conda activate mcp-agent

cd mcp-api-agent
pip install -r requirements_api.txt
```

2. **Configure Settings (config.json)**
Fill in these four sections in `config.json`:

- `MCP_SERVERS`
- `INSTRUCT_CONFIG`
- `THINKING_CONFIG`
- `RUNTIME_LIMITS`

The core idea is:

- `INSTRUCT_CONFIG`: the model used for fast tool usage and structured responses
- `THINKING_CONFIG`: the model used for final synthesis and diagnosis
- `RUNTIME_LIMITS`: the safety layer that prevents prompt explosions, oversized logs, and unstable long-context calls

Point `MCP_SERVERS` to your actual reachable SSE endpoints or in-cluster service addresses.
```json
// mcp-api-agent/config.json modification example
"MCP_SERVERS": [
    {"name": "k8s",             "url": "http://<K8S_NODE_IP>:<NODE_PORT>/sse"},
    {"name": "VictoriaLog",     "url": "http://<K8S_NODE_IP>:<NODE_PORT>/sse"},
]
```

3. **Run the API Server**
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

### 3. Deploying via GHCR (Kubernetes)

For production deployment, prefer the published runtime image:

```bash
docker pull ghcr.io/jwjinn/mcp-api-agent:latest

# A100
kubectl apply -k mcp-api-agent/k8s/overlays/a100

# NPU
kubectl apply -k mcp-api-agent/k8s/overlays/npu
```

Document roles:

- Real deployment steps: `mcp-api-agent/DEPLOYMENT_GUIDE.md`
- Practical NPU Qwen3 example: `mcp-api-agent/NPU_QWEN3_REFERENCE.md`
- Kustomize layout notes: `mcp-api-agent/k8s/README.md`

In the current version, the recommended baseline is the `base + overlays` deployment structure rather than a single YAML manifest.

---
> The current operational baseline is `mcp-api-agent/DOCS_MAP.md`, `mcp-api-agent/DEPLOYMENT_GUIDE.md`, and `mcp-api-agent/NPU_QWEN3_REFERENCE.md`.  
> `paper/`, `advanced_docs/`, and `MCP_Develop_History.md` are best treated as explanatory, historical, or deep-dive materials.

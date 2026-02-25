# MCP AI Agent

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

[English version](README_en.md) | [한국어버전](README.md)

## Introduction

**MCP AI Agent** is an intelligent microservice and infrastructure orchestration middleware that combines LangGraph-based AI workflows with the **Model Context Protocol (MCP)**. This agent allows users to autonomously control and diagnose various backend endpoint tools—such as Kubernetes clusters, unified logging systems, and Virtual Machines (VMs)—through natural language conversations.

### Demo
<!-- 💡 Tip: You can drag and drop your .mp4 video file directly into the GitHub web editor to embed a native video player automatically. -->
[🎥 Watch Demo Video Here](#)

Notably, it supports a dual LLM environment: a **Thinking Model** for deep reasoning and planning, and an **Instruct Model** for fast and precise tool execution. This provides an automated AIOps (Artificial Intelligence for IT Operations) solution that goes far beyond traditional static dashboards.

## Architecture

The project is divided into two primary components based on their use cases:

- **`mcp-cli-agent/`**: A lightweight Python CLI environment for interacting directly with the agent in the terminal, allowing for immediate testing of tool or prompt changes.
- **`mcp-api-agent/`**: A FastAPI-based backend application designed for production environments to communicate with remote Web UIs or other services. It supports Server-Sent Events (SSE) streaming for monitoring dashboards and is fully ready for Docker/Kubernetes deployment.

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

### 1. Configuration Setup
After cloning the repository, replace the IP addresses and API Keys in the provided template files to match your environment.

```bash
# Copy CLI version configuration
cp mcp-cli-agent/config.example.py mcp-cli-agent/config.py

# Copy FastAPI version configuration
cp mcp-api-agent/config.example.py mcp-api-agent/config.py
cp mcp-api-agent/config.example.json mcp-api-agent/config.json
```

### 2. Local PC Testing
The fastest way to verify the agent's workflow directly from your CLI. This method is ideal when actively modifying and testing source code.

1. **Set up a Python Virtual Environment (e.g., Conda) and Install Dependencies**
```bash
# Create and activate a Conda environment
conda create -n mcp-agent python=3.11
conda activate mcp-agent

cd mcp-cli-agent
pip install -r requirements.txt
```

2. **Configure Settings (config.py)**
Modify the `MCP_SERVERS` URLs in your previously copied `config.py` to point to the **Kubernetes NodePort** addresses.
```python
# mcp-cli-agent/config.py modification example
MCP_SERVERS = [
    {"name": "k8s",             "url": "http://<K8S_NODE_IP>:<NODE_PORT>/sse"},
    {"name": "VictoriaLog",     "url": "http://<K8S_NODE_IP>:<NODE_PORT>/sse"},
    # ...
]
```

3. **Run the Agent**
```bash
python main.py
```

### 3. Deploying via GHCR (Kubernetes)
For staging or production environments, avoid running from source code and use the **pre-built official public package image**. The CLI Agent is automatically built and pushed to GitHub Container Registry (GHCR) upon any changes to the `mcp-cli-agent` directory.

You can reliably deploy it on your Kubernetes cluster using the following comprehensive guide (ConfigMap + Deployment).

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-cli-agent-config
  namespace: mcp
  labels:
    app: mcp-cli-agent
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
  name: mcp-cli-agent-deployment
  namespace: mcp
  labels:
    app: mcp-cli-agent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mcp-cli-agent
  template:
    metadata:
      labels:
        app: mcp-cli-agent
    spec:
      containers:
      - name: mcp-cli-agent
        # Using the official published package image
        image: ghcr.io/jwjinn/mcp-api-agent:latest
        imagePullPolicy: Always
        stdin: true
        tty: true
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
      volumes:
      - name: config-volume
        configMap:
          name: mcp-cli-agent-config
```

Apply the manifest to your Kubernetes cluster:

```bash
kubectl apply -f manifest.yaml
```

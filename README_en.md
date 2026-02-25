# MCP AI Agent

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

[English version](README_en.md) | [한국어버전](README.md)

## Introduction

**MCP AI Agent** is an intelligent microservice and infrastructure orchestration middleware that combines LangGraph-based AI workflows with the **Model Context Protocol (MCP)**. This agent allows users to autonomously control and diagnose various backend endpoint tools—such as Kubernetes clusters, unified logging systems, and Virtual Machines (VMs)—through natural language conversations.

### Demo
<video src="assets/demo.mp4" controls="controls" muted="muted" style="max-height:640px; min-height: 200px; width: 100%; object-fit: cover;"></video>

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

### 2. Running the CLI Agent
This is the fastest way to verify the agent's workflow locally.

```bash
cd mcp-cli-agent
pip install -r requirements.txt
python main.py
```

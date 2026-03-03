# MCP AI Agent

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

[English version](README_en.md) | [한국어버전](README.md)

## 🌟 Introduction

**MCP AI Agent** is an intelligent microservice and infrastructure orchestration middleware that combines LangGraph-based AI workflows with the **Model Context Protocol (MCP)**. 

Moving beyond frustrating, manual monitoring dashboards, this is an **innovative AIOps (Artificial Intelligence for IT Operations) solution** that pierces through the root causes of Kubernetes failures with a single conversation.

## 📖 Comprehensive Guide for Beginners & Contributors (Must Read!)

Are you new to this project? Wondering how the code works or why we chose this architecture?

**We've prepared a highly accessible, story-like set of "Paper" documents for beginners!** We strongly recommend reading them in the following order:

👉 **[1. Background and Why (BACKGROUND AND WHY)](paper/1_BACKGROUND_AND_WHY.md)**
- Discover why a simple ChatGPT model cannot diagnose infrastructure, and read about the 3 critical problems we faced and how we solved them in plain English.

👉 **[2. Core Architecture (CORE ARCHITECTURE)](paper/2_CORE_ARCHITECTURE.md)**
- Team Leader, Summary Fairy, Sherlock Holmes? Check out how these AI assistants cooperate "concurrently" to diagnose issues, complete with fun Mermaid diagrams!

👉 **[3. Code Walkthrough (CODE WALKTHROUGH)](paper/3_CODE_WALKTHROUGH.md)**
- A guided tour of how the architecture you just saw is actually implemented in Python (`agent_graph.py`, `api_server.py`) step-by-step.

👉 **[4. How to Start and Test (HOW TO START)](paper/4_HOW_TO_START_AND_TEST.md)**
- Enough theory! This is the most detailed tutorial on setting up a Python virtual environment, configuring `config.json`, launching the FastAPI server, and testing it with real prompts.

---

## ⚡ Deep-Dive for Senior & Core Developers (Advanced Docs)

If you want to go beyond the tutorial and taste the essence of **LangGraph state control, memory optimization, asynchronous parallel processing, and dynamic metaprogramming**, open the `advanced_docs/` directory at the project root.

*   🧠 **[1. State Management & Graph Lifecycle](advanced_docs/1_STATE_MANAGEMENT_AND_GRAPH.md)**: AgentState Reducer design and the Smart Sliding Window algorithm to prevent Token Window overflow.
*   ⚡ **[2. Parallel Workers & Map-Reduce Architecture](advanced_docs/2_PARALLEL_WORKERS_AND_MAP_REDUCE.md)**: O(1) communication optimization via `asyncio.gather` and Sub-Agent filtering techniques.
*   🔌 **[3. MCP Dynamic Schema Binding](advanced_docs/3_MCP_CLIENT_DYNAMIC_BINDING.md)**: Runtime schema weaving (Metaprogramming) mechanisms using `pydantic.create_model`.
*   🎭 **[4. LLM Tuning & Prompt Engineering](advanced_docs/4_LLM_TUNING_AND_PROMPT_ENGINEERING.md)**: Forcing Instruct models for perfect JSON parsing and defense tuning against infinite loops (Hallucination).

---

> For in-depth information regarding past development processes, troubleshooting history, and Kubernetes YAML deployment, please refer to `mcp-api-agent/MCP_Develop_History.md`.

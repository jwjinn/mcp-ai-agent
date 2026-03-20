# MCP AI Agent: System Architecture & Prompts Deep-Dive

This report provides an in-depth analysis of the `mcp-ai-agent`'s internal logic, specifically the **System Prompts** used at each stage and its detailed implementation mechanisms.

> This is a prompt/code deep-dive document. For the current operational baseline, see [`mcp-api-agent/DOCS_MAP.md`](../mcp-api-agent/DOCS_MAP.md) and [`mcp-api-agent/DEPLOYMENT_GUIDE.md`](../mcp-api-agent/DEPLOYMENT_GUIDE.md).

---

## 1. State Management

The agent shares data across all nodes via LangGraph's `AgentState`.

*   **messages**: Conversation history (Array of LangChain Message objects). In the current version, effective retention is controlled through `RUNTIME_LIMITS`.
*   **mode**: Routing result, either "SIMPLE" or "COMPLEX".
*   **worker_plans**: JSON instructions given by the Orchestrator to the Workers.
*   **worker_results**: A list of summarized reports produced by each specialist executing tools.

---

## 2. Detailed Node Logic & System Prompts

### 🔄 Router Node
**Purpose**: Determine the path for efficient resource utilization.
*   **Prompt**: 
    > "SIMPLE": Simple lookup of a specific single resource... (e.g., give me the pod list)
    > "COMPLEX": Complex reasoning, root cause analysis, resolving errors... (e.g., diagnose systematically)

### 🛠️ Simple Agent Node
**Purpose**: Provide fast, immediate answers and execute single tools.
*   **System Prompt Core**:
    > "You are a fast and accurate K8s and Observability administrator... Do not think, just call the tool immediately. Reply unconditionally in Korean." (Adapt to English as needed)
*   **Note**: All MCP tools are directly accessible via `bind_tools`.

### 🧠 Orchestrator Node
**Purpose**: Break down complex problems and delegate to the appropriate specialists.
*   **System Prompt Core**:
    > "Do not try to solve the problem yourself; make a plan on 'what information to collect' and delegate. When making a comprehensive diagnosis, you must call all 3 specialists: K8s, Log, and Metric."
*   **Output**: JSON format (`{"log": "...", "metric": "...", "k8s": "..."}`)

### 👷 Worker Node
**Purpose**: Perform in-depth analysis and summarize using ONLY assigned, specialized tools.
*   **Specialized Guides by Domain**:
    *   **LogSpecialist**: Use `| collapse_nums` for `vlogs_query` and recommends `limit: 50`.
    *   **MetricSpecialist**: Forces the use of `topk(10, ...)`, warns against using `| limit` in PromQL.
    *   **K8sSpecialist**: Data minimization strategy using `output="name"`, etc.
*   **Sub-Agent Summarization**: If tool results (Raw Data) are too large, the LLM first creates a summary extracting only core facts (error phrases, stack traces, etc.).

### 📝 Synthesizer Node
**Purpose**: Logically weave the reports of all specialists together to generate the final answer.
*   **System Prompt Core**:
    > "Rank importance in this order: K8s (foundation) -> Metric (symptom) -> Log (root cause). Remember that '[Empty result returned...]' does not signify an error, but that the cluster is healthy!"

---

## 3. Advanced Implementation Mechanisms

### 🚫 Loop Prevention
The `check_and_filter_duplicate_tools` function blocks the AI from repeatedly calling the same tool with the exact same arguments.
```python
if new_tc["name"] == old_tc["name"] and new_tc["args"] == old_tc["args"]:
    is_dup = True
```

### ✂️ Truncation Strategy
A multi-layer truncation strategy is used to prevent network buffer (ENOBUFS) errors and LLM context limits.
1.  **MCP Level**: Truncated at 10,000 characters in `call_mcp_tool`.
2.  **Worker Level**: If Raw Data before summarization exceeds 8,000 characters, preserves mainly the core parts (end of text, etc.).
3.  **Synthesizer Level**: Final truncation occurs if the completely aggregated text exceeds 10,000 characters.

### ⚡ Parallel Execution & Concurrency Control
Executes specialists concurrently via `asyncio.gather`, while protecting the API Rate Limit using `asyncio.Semaphore(2)`.

---

## 4. MCP Communication Details (`mcp_client.py`)

*   **Keep-Alive**: Runs a background task that sends a `ping` every 45 seconds to maintain the SSE connection.
*   **Dynamic Pydantic Model**: Converts the server's `inputSchema` to classes at runtime using `create_model`. This allows LangChain to validate tool arguments accurately.
*   **Namespace Application**: Uses `server_name` + `tool_name` format to prevent tools from multiple servers from mixing up.

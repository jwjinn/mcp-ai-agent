# MCP AI Agent: Detailed Code Execution Flow and System Prompt Analysis

This document traces step-by-step at the **actual code level** how internal functions and variables exchange values from the moment a user's question is input until the final answer is generated.

---

## 1. Server Startup and MCP Tool Initialization

When the program starts, it must first establish connections with external monitoring systems (Kubernetes, VictoriaLogs, etc.) and prepare "available tools" in a format LangChain can understand. This happens during global initialization in `main.py` (or `api_server.py`) and inside `mcp_client.py`.

### 1-1. Client Creation and Connection (`api_server.py` lifespan / `main.py`)
It iterates through the `MCP_SERVERS` array defined in `config.py` to create `MCPClient` objects.

```python
# Excerpt from main.py
clients = []
all_tools = []

for server_conf in MCP_SERVERS:
    client = MCPClient(server_conf["name"], server_conf["url"])
    await client.connect() # SSE connection to MCP server
    clients.append(client)
    all_tools.extend(client.tools) # Add tools provided by the server to the global list
```

### 1-2. Dynamic Tool Loading (`mcp_client.py` -> `refresh_tools()`)
One of the core features of this program is **dynamically converting the tool schemas of external MCP servers into Python code**.

```python
# Inside mcp_client.py
async def refresh_tools(self):
    # 1. Request tool list from server
    mcp_tools_list = await self.session.list_tools()
    
    for tool in mcp_tools_list.tools:
        # 2. Parse JSON Schema
        schema = tool.inputSchema
        properties = schema.get("properties", {})
        
        fields = {}
        for prop_name, prop_schema in properties.items():
            # ... Type mapping (string -> str, integer -> int, etc.) ...
            fields[prop_name] = (py_type, ...) # Pydantic field attribute definition
        
        # 3. Create Pydantic model dynamically at runtime (!Crucial!)
        # Add prefix (self.name) to prevent name collisions e.g., "k8s_k8s_kubectl_get_input"
        InputModel = create_model(f"{self.name}_{tool.name}_input", **fields)
        
        # 💡 [Why is this essential? (Why?)]
        # When using tools, LangChain's LLM needs to know clearly "what Arguments of what type are needed".
        # In typical code, you would predefine them, but since we only know what tools an MCP server provides at runtime,
        # we must instantly mold an instruction manual using Python's dynamic class generation (create_model).

        # 4. Create wrapper function: Called upon actual tool execution
        async def _run_tool(tool_name=tool.name, **kwargs):
            clean_args = {k: v for k, v in kwargs.items() if v is not None}
            # Finally proceed with MCP communication logic
            return await self.call_mcp_tool(tool_name, clean_args)
            
        # 5. Convert to LangChain's StructuredTool so the agent can use it
        namespaced_tool_name = f"{self.name}_{tool.name}"
        langchain_tool = StructuredTool.from_function(
            func=None,
            coroutine=_run_tool,
            name=namespaced_tool_name,
            description=f"[{self.name}] {tool.description[:1000]}",
            args_schema=InputModel
        )
        self.tools.append(langchain_tool)
```

---

## 2. Graph Assembly (`agent_graph.py` -> `create_agent_app`)

Based on the `all_tools` list secured above, we build the pipeline (LangGraph) where data will flow.

```python
# agent_graph.py
def create_agent_app(tools: list):
    workflow = StateGraph(AgentState) # State store
    
    # Add nodes (functions)
    workflow.add_node("router", router_node)
    workflow.add_node("simple_agent", simple_agent_wrapper)
    workflow.add_node("orchestrator", orchestrator_wrapper)
    workflow.add_node("workers", workers_wrapper)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("tools", ToolNode(tools)) # Standard tool executor for Simple Mode
    
    # Connect edges (Define execution order)
    workflow.add_edge(START, "router")
    
    # 🌟 Routing logic split point
    def route_decision(state):
        if state and state.get("mode") == "complex":
            return "orchestrator"
        return "simple_agent"
        
    workflow.add_conditional_edges("router", route_decision)
    
    # [Complex Path] Orchestrator -> Workers -> Synthesizer -> END
    workflow.add_edge("orchestrator", "workers")
    workflow.add_edge("workers", "synthesizer")
    workflow.add_edge("synthesizer", END)
    
    return workflow.compile()
```

---

## 3. Request Handling Starts

The user throws a question via the API. (`api_server.py`)

```python
# api_server.py
@app.post("/api/stream_chat")
async def react_flow_stream_endpoint(request: Request):
    # Extract user text
    user_input = messages[-1]["content"] if messages else data.get("message", "")
    
    # Set initial state (input values) to pass to LangGraph
    inputs = {"messages": [HumanMessage(content=user_input)]}
    
    # Start graph execution as a background task
    async for event in agent_app.astream(inputs):
        # ... Real-time log streaming logic ...
        pass
```

---

## 4. Detailed Operation Flow per Node (`agent_graph.py`)

Now the `inputs` traverse the nodes (functions) through the LangGraph pipeline. The `state` variable of the functions acts as the payload, updating at each step.

### 4-1. Router Node (`router_node`)
Determines the difficulty of the user's question.

> **💡 [Why Branch? (Why?)]**
> Waking up the Orchestrator and 3 specialists for a simple question asking for the status of a single pod causes a **massive token waste and response delay**. Therefore, we use a lightweight model to grasp the complexity first, and send simple questions straight to the `Simple Agent` to optimize speed (Latency) and cost.

*   **Input Variable**: `state["messages"][-1].content` (e.g., "Why is there an error in the payment pod?")
*   **Prompt Text passed to LLM**:
```text
You are an AI that classifies user intent.
Answer categorically whether the user's question falls into one of the following:

1. "SIMPLE": Simple lookup of a specific single resource or if an immediate answer is possible with a single tool.
2. "COMPLEX": If complex reasoning, root cause analysis (Diagnosis), error resolution, or multi-step tool use is needed. Classify comprehensive analysis requests like "diagnose systematically" as COMPLEX, but simple ranking/statistics like "Show me top 3 CPU pods" as "SIMPLE".

[User Question]
{last_msg.content}

[Response Format]
Answer ONLY with "SIMPLE" or "COMPLEX".
```
*   **Process Result**: If the LLM answers "COMPLEX", it returns the signal `return {"mode": "complex"}`, and the flow moves to the `Orchestrator` via the previously defined `add_conditional_edges`.

### 4-2. Orchestrator Node (`orchestrator_node`)
Sets up a plan dividing complex tasks and assigning them to sub-specialists (Workers).

> **💡 [Why do we need an Orchestrator? (Why?)]**
> If you give an LLM over 20 tools all at once, the LLM falls into **"Tool Confusion"**, using the wrong tools or hallucinating. To prevent this, we divide & conquer the problem, granting "Specialist Personas" (one sees only logs, one sees metrics, etc.) to maximize operational accuracy.

*   **Prompt Text passed to LLM (Excerpt)**:
```text
You are the 'Orchestrator' of an AIOps system.
To solve the user's request, you must issue instructions to sub-workers.
Do not try to solve the problem yourself; make a plan on "what information to collect" and delegate.

[List of Sub-Workers]
1. **LogSpecialist** (Logs): Log analysis expert.
    - Tip: Do not just look at errors (`level:error`); search for core keywords like 'cannot' or 'fail' alongside warnings. ...
2. **MetricSpecialist** (Metrics/Traces): Metric and trace analysis expert.
3. **K8sSpecialist** (K8s Config): K8s configuration and resource lookup expert.

[Output Example]
```json
{
    "log": "Query the error logs of backend-api for the last 1 hour and figure out the cause.",
    "metric": "Check if the memory usage of that pod has spiked.",
    "k8s": "Check the recently deployed image tag and Deployment config."
}
```
```
*   **Code Execution Trace**: 
    If the LLM returns JSON, it parses it using Regex and `json.loads`.
    The parsed dictionary is saved in the `worker_plans` variable and passed to the next node.
    ```python
    worker_plans = json.loads(json_str)
    return {"worker_plans": worker_plans, "messages": [...]}
    ```

### 4-3. Executing Workers (`workers_node` -> `run_single_worker`)
Based on the `worker_plans` created by the Orchestrator, **LLM Specialists simultaneously work using different tools.**

```python
# Inside workers_node function
tasks = []
if plans.get("log"):
    # Filter out only log analysis tools (vlogs_*)
    log_tools = filter_tools(tools, "log")
    tasks.append(run_single_worker("LogSpecialist", plans["log"], log_tools))

# ... Add tasks for Metric and K8s identically ...

# Parallel execution (Semaphore to protect Rate Limit - max 2 at a time)
sem = asyncio.Semaphore(2)
# Execute all tasks concurrently and wait until all results are gathered
results = await asyncio.gather(*safe_tasks) 

return {"worker_results": results}
```

#### 📌 Tool Execution and Summarization inside Worker (Map-Reduce Mechanism)
Let's look inside the `run_single_worker` function, the most complex and carefully crafted part of this project. A worker calls the LLM once to use a tool, and then **summarizes once more** the raw data obtained.

1.  **Dedicated Prompt and Tool Call**:
    ```python
    llm_with_tools = llm.bind_tools(tools)
    response = await llm_with_tools.ainvoke([sys_msg]) # Decide to use tool (e.g., "I'll use k8s_kubectl_get")
    ```
    
2.  **Manual Tool Execution**: (Executed directly instead of depending on LangChain's standard `ToolNode`)
    ```python
    tool_outputs = []
    for tc in response.tool_calls:
        # Find matching tool
        selected_tool = next((t for t in tools if t.name == tc["name"]), None)
        
        # Call actual tool function (this proceeds from _run_tool in mcp_client.py to call_mcp_tool)
        res = await selected_tool.ainvoke(tc["args"]) 
        tool_outputs.append(f"Output: {res}")
        
    raw_results = "\n\n".join(tool_outputs)
    ```
    
3.  **Result Summarization**:
    It compresses the `raw_results` (which could be thousands of lines) via the following prompt.
    ```text
    You are the summarizer for {worker_name}.
    Mission given by Orchestrator: {instruction}
    
    [Task Instructions]
    1. Extract ONLY the core facts necessary to answer the mission from the <raw_data>.
    2. NEVER omit discovered error phrases, warnings, or failed pod names; preserve them.
    3. Keep it concise, bullet points. Within 2,000 characters. Preserve error source texts exactly.
    ```
    Through this process, a string containing only core information is returned inside the `worker_results` list.
    
    > **💡 [Why does each expert summarize directly? (Why Map-Reduce?)]**
    > If we throw the K8s configs, massive server logs, and metric traces collected by the 3 specialists exactly as they are to the final Synthesizer model, it will exceed the LLM's **Context Window (Max character limit)** causing an error, or there will be so much noise that it misses the core.
    > Therefore, the Map-Reduce compression mechanism—filtering out noise at each specialist level and extracting only "pure signals"—is essential when dealing with large-scale cloud data.

### 4-4. Synthesizer Node (`synthesizer_node`)
Aggregates the summary reports uploaded by each Worker to generate the final answer.

```python
# 1. Sort report priority (K8s -> Metric -> Log)
# Reason: It's logical to lay base K8s resources -> see metric changes -> analyze cause (Log)
worker_results_dict = {}
for res in state["worker_results"]:
    if "[K8sSpecialist]" in res: worker_results_dict["k8s"] = res
    # ...
    
# 2. Generate aggregated payload (Includes character limit guards)
ordered_results = [worker_results_dict["k8s"], worker_results_dict["metric"], worker_results_dict["log"]]
worker_results_str = "\n\n".join(ordered_results)
```

*   **Prompt for Generating Final Conclusion**:
```text
You are the Synthesizer organizing the final answer.
The Orchestrator gave instructions to the Workers, and the results are below.

[Worker Execution Result Reports]
{worker_results_str}

[Writing Rules]
1. Logically explain by citing each specialist's analysis results.
2. Based on the results, diagnose the cause and propose a solution.
3. **Core Analysis Rule**: If a tool execution result comes in the form of "[Empty result returned...]", NEVER misunderstand it as lack of permissions or a communication failure! It means there are virtually NO bad resources caught by error filters (like Failed Pod limits), meaning the cluster is extremely healthy. Analyze this and report to the user that "It is healthy with zero error pods."
4. **Additional Health Rule**: If the K8s specialist's report simply lists pod names without any special error messages, be confident that those resources are deployed normally (Running) and explain it.
```
When the **Thinking model** (Reasoning specialized LLM like DeepSeek-r1 or QwQ) finishes its in-depth pondering (real-time `<think>` process via `.astream`), the completed sentence is placed in an `AIMessage` and the StateGraph reaches the `END` state.

---

## 5. Actual Tool Process (`mcp_client.py` -> `call_mcp_tool`)

When `selected_tool.ainvoke` is called in step 4-3, this is the section where the request finally passes to the K8s or log server.

```python
# Inside mcp_client.py
async def call_mcp_tool(self, name: str, arguments: dict) -> str:
    try:
        # RPC call to actual server (NodeJS, etc.) via MCP SDK happens here
        result: CallToolResult = await self.session.call_tool(name, arguments)
        
        output_text = []
        if result.content:
            for content in result.content:
                if content.type == "text":
                    output_text.append(content.text)
        
        final_output = "\n".join(output_text)
        
        # 🌟 System Crash Prevention Logic (Truncation)
        # If massive text is returned by running `kubectl get all -A`, 
        # Python memory bursts or it easily bypasses the LLM's Input Token limit.
        MAX_OUTPUT_LENGTH = 10000 
        if len(final_output) > MAX_OUTPUT_LENGTH:
            # Forced cutoff at 10,000 characters!
            final_output = final_output[:MAX_OUTPUT_LENGTH] + \
                f"\n... (⚠️ Output truncated by {len(final_output) - MAX_OUTPUT_LENGTH} chars. Use specific filters to see more.)"
        
        # 💡 [Why Must It Be Truncated? (Why?)]
        # K8s and VictoriaLogs are massive systems. One query with an accidental wrong filter can return megabytes of text.
        # Shoving this into an LLM instantly causes a "Rate Limit or Context Limit Exceeded Error," bringing down the whole system.
        # This is the most primal and powerful defense shield.
                
        return final_output
        
    except Exception as e:
        error_str = str(e)
        # Network socket buffer limit error response
        if "ENOBUFS" in error_str:
            return "❌ [System Limit] ENOBUFS: Too much data. Narrow the scope."
        return f"Error executing {name}: {error_str}"
```
With this, the MCP call concludes, and its returned text goes back to the LangGraph's Worker to be used for summarization.

---

Thanks to this massive pipeline, it flawlessly executes a perfect enterprise-level multi-agent workflow: **"Interpret Question -> Divide Labor -> Distributed Parallel Tasks (Tool Execution) -> Aggregate & Summarize Reports -> Final Comprehensive Analysis & Proposal"**, rather than being just a simple Q&A bot.

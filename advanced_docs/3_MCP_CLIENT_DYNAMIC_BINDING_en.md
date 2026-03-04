# 🔌 3. MCP Dynamic Schema Binding (Advanced)

This document is an advanced guide covering how one of the powerful features of Core Python—**Runtime Metaprogramming**—is utilized in `mcp_client.py` to cast the tools of Model Context Protocol (MCP) servers into LangChain schemas.

---

## 🎭 1. Dynamic Schema Builder (Metaprogramming)

Due to the nature of AIOps, we need to communicate with numerous separate remote MCP servers (like K8s, Logs) written in Go/Node.js.
**The problem is, before runtime (at the time the code is written), Python has no way of knowing what parameters exist on the remote server.**
However, for LangChain to recognize tools, a strict Pydantic BaseModel (Schema) must exist in the code so the LLM correctly outputs the `tool_calls` arguments.

### 🛠️ The Advent of Pydantic `create_model`
The `refresh_tools` method in `mcp_client.py` is called once right after connecting to the server. It receives the JSON Schema specifications and weaves a Python Class dynamically into real-time memory.

```python
async def refresh_tools(self):
    # mcp_tools_list is the JSON response object fetched via remote SSE communication.
    mcp_tools_list = await self.session.list_tools()

    for tool in mcp_tools_list.tools:
        # [1] Parse JSON Schema
        schema = tool.inputSchema
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        fields = {}
        for prop_name, prop_schema in properties.items():
            # [2] JSON Type -> Python Type Mapping
            py_type = Any
            if prop_schema.get("type") == "string": py_type = str
            elif prop_schema.get("type") == "integer": py_type = int
            elif prop_schema.get("type") == "boolean": py_type = bool

            # [3] Define fields (Type, default value generation)
            # Tuple: (Type, value_or_ellipsis) - Ellipsis(...) means "required value" in Pydantic
            if prop_name in required:
                fields[prop_name] = (py_type, ...)
            else:
                fields[prop_name] = (py_type, None)
        
        # [Core] Create dynamic Pydantic model (Metaprogramming)
        # At runtime, something like "class K8s_get_pods_input(BaseModel): ..." pops into memory!
        InputModel = create_model(f"{self.name}_{tool.name}_input", **fields)

        # [4] Wrap with LangChain StructuredTool (Add Namespace)
        # ...
```

**[🔥 Architectural Significance]**
Because there is no hard-coded Pydantic class, even if a remote K8s MCP Server developer changes the arguments (parameters) of a tool tomorrow, **our agent-side code doesn't need a single line of hotfix. As soon as the server is restarted (or refreshed), it syncs with perfect specs.**

---

## 🔒 2. AsyncExitStack and Persistent Session Management

An SSE (Server-Sent Events) connection is an infinite stream. Disconnecting it leads to a catastrophe. To safely guarantee Resource return, we introduced `AsyncExitStack`, a clean asynchronous evolution of the `try-finally` block.

```python
class MCPClient:
    def __init__(self, name: str, server_url: str):
        self.exit_stack = AsyncExitStack()
        # ...

    async def connect(self):
        # AsyncExitStack.enter_async_context: 
        # Closes the block automatically when this object is cleaned up. (Ultimate defense against Resource Leaks)
        transport = await self.exit_stack.enter_async_context(
            sse_client(self.server_url, sse_read_timeout=3600)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(transport[0], transport[1])
        )
```

This pattern mimics Object-Oriented **RAII (Resource Acquisition Is Initialization)** in the Python asynchronous ecosystem.

### 💖 Keepalive Mechanism
To defend against the most chronic disease of SSE, **Idle Timeout (when load balancers/firewalls cut off the session if there's no traffic)**, we implemented a Heartbeat.

```python
async def _keepalive(self):
    while True:
        await asyncio.sleep(45) # Ping every 45 seconds
        if self.session:
            try:
                await self.session.send_ping()
            except Exception:
                pass # Ignore Ping failures (Actual disconnections are handled by Reconnect logic at the Adapter's Call layer)
```

Thanks to this background task, even if the agent is "Thinking" for a long time, the network pipelines with the connected MCP backend servers don't dry up and are kept alive like zombies.

---
👉 **[Go Back (Beginner Chapter 3: Code Walkthrough)](../paper/3_CODE_WALKTHROUGH_en.md)**

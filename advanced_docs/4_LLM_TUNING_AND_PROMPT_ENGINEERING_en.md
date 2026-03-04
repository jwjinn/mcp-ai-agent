# 🧠 4. LLM Tuning & Prompt Engineering (Advanced)

This document is an architectural guide covering the essence of LLM Dichotomy and Prompt Engineering introduced by this system to achieve **optimal Model Performance and zero fatal Parsing Errors**.

---

## 🎭 1. The Dilemma of Model Dichotomy (Instruct vs Thinking)

In the early days of the AIOps system, all nodes were unified under one powerful **Thinking Model (e.g., Qwen-Thinking/DeepSeek-R1)**. However, this approach yielded two terrible side effects.

1.  **JSON Format Destruction (The `<think>` parsing nightmare)**
    *   The Orchestrator must give instructions to the workers in JSON format (`{"k8s": "...", "log": "..."}`).
    *   However, before providing the answer, Thinking models unconditionally attach a monologue at the front, like `"<think> Hmmm... I should use k8s... </think> {"k8s": "..."}"`.
    *   The moment the Python interpreter passes this entire text into `json.loads`, a **JSON Decode Crash** instantly occurs, killing the container. Even attempting to parse out the tags with Regex often resulted in broken tags or distorted formats.

2.  **Failed Computational Cost Optimization (Wasted FLOPs)**
    *   The Router node only needs to make a 1D judgment: "Is this a simple lookup (SIMPLE) or an in-depth analysis (COMPLEX)?" Using a Thinking model here sacrificed user Latency, undergoing `<think>` for 20 seconds for a judgment that should take 2 seconds.

### 💡 Solution: Strict Isolation of "Rules" and "Reasoning"
We deployed **Instruct models** at the front lines (Router, Orchestrator, Worker) because they perfectly follow the Instruction rules in system prompts and prodigiously output JSON Schemas just like machines.
And we deployed a **Thinking model** (where capital—time and reasoning power—is concentrated) exclusively for the finale (Synthesizer node), where refined information must be aggregated to deduce the final Root Cause, completing a perfect Hybrid.

---

## 🚫 2. Blocking Infinite Loops (Anti-Hallucination Deduplication)

In the past, pure ReAct agents would forget the Tool they just used and say, "Let's try that again," falling into infinite loops and causing server crashes.
We performed surgical intervention on the LLM's decision-making through the `check_and_filter_duplicate_tools` function.

```python
def check_and_filter_duplicate_tools(history_messages: list, new_msg: BaseMessage):
    # Pass if there is no previous AI message or it's not a tool call
    last_ai_msg = list(filter(lambda x: isinstance(x, AIMessage) and x.tool_calls, history_messages))
    if not last_ai_msg: return new_msg
    
    # 1. Hashes the string of the name and argument set of the tool used in the previous message, placing it into a set.
    # 2. Compares it with the hash set of the tool the current message attempts to use.
    # 3. If there is a 100% match, that tool is DROPPed from the object returned by the LLM.
    
    # [Defense Logic] Forcibly inject a system prompt so an error message doesn't appear where the tool disappeared
    new_msg.content += "\n[System: Execution of identical tools/arguments was blocked by the system.] "
```

Thanks to this algorithm, even if the agent suffers from short-term memory loss, it is forcibly informed that it was rejected and naturally steered to move on to the next action (using another tool or summarizing).

---

## 🌊 3. Callback Interception for Thinking Stream

When streaming via SSE from `api_server.py`, rendering the multi-line `<think> ... </think>` text from Thinking models onto the screen provides a very messy UX (User Experience).
So, we implemented a custom handler called **`AsyncThinkingStreamCallback`**.

```python
class AsyncThinkingStreamCallback(AsyncCallbackHandler):
    # Overriding Langchain's on_llm_new_token hook
    async def on_llm_new_token(self, token: str, **kwargs):
        self.buffer += token
        
        # If still thinking (inside the <think> zone), 
        # merely collect tokens and NEVER yield them out of the buffer (Queue)!
        if self.in_thinking:
            if "</think>" in self.buffer:
                self.in_thinking = False
                # Start yielding the main text after the tag
                remaining = self.buffer.split("</think>")[-1]
                if remaining: await self.target_queue.put(remaining)
            return

        # Give immediate pushes to the Queue once thinking is done (Main text zone)
        await self.target_queue.put(token)
```

Through this logic, even if the brain (LLM) freely spits out hundreds of sentences in its monologue, the mouth (API Output) acts as a **Filter drain**, ensuring that only the first character of the final Diagnosis is rendered to the user's browser.

---
👉 **[Go Back (Beginner Chapter 1: Background Story)](../paper/1_BACKGROUND_AND_WHY_en.md)**

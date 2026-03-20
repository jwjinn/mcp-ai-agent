# Kubernetes Layout

This directory separates deployment concerns from application code so that A100 and NPU environments can share one codebase.

## Structure

- `base/`: Common ConfigMap, Deployment, and Service shared by every environment.
- `overlays/a100/`: A100-oriented configuration and naming.
- `overlays/npu/`: NPU-oriented configuration defaults.

## Apply

```bash
kubectl apply -k mcp-api-agent/k8s/overlays/a100
kubectl apply -k mcp-api-agent/k8s/overlays/npu
```

## What to customize

- Update each overlay's `configmap-patch.yaml` with the correct model endpoint, host header, and model names.
- Tune `context_window`, `max_input_tokens`, `max_output_tokens`, and `RUNTIME_LIMITS` per hardware/model when A100 and NPU serve different model profiles.
- If you want scheduling constraints for a specific environment, add them in the overlay `deployment-patch.yaml`.
- If you need separate image tags per environment, update the image in the base or add an image override in the overlay kustomization.

## Environment Variable Overrides

The application keeps the current defaults if you do nothing, but you can override the runtime guardrails with Kubernetes `env` values.

- `INSTRUCT_MODEL_CONTEXT_WINDOW`
- `INSTRUCT_MODEL_MAX_INPUT_TOKENS`
- `INSTRUCT_MODEL_MAX_OUTPUT_TOKENS`
- `THINKING_MODEL_CONTEXT_WINDOW`
- `THINKING_MODEL_MAX_INPUT_TOKENS`
- `THINKING_MODEL_MAX_OUTPUT_TOKENS`
- `ROUTER_KEEP_LAST`
- `SIMPLE_KEEP_LAST`
- `MAX_AI_STEPS`
- `WORKER_SUMMARY_QUOTA`
- `MAX_TOTAL_CONTEXT`
- `MCP_TOOL_MAX_OUTPUT_CHARS`
- `WORKER_RAW_RESULT_MAX_CHARS`

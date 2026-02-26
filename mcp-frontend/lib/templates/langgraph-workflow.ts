import { WORKFLOW_MODELS } from "@/lib/workflow/models";
import type {
    FlowEdge,
    FlowNode,
} from "@/types/workflow";

export const LANGGRAPH_WORKFLOW: {
    nodes: FlowNode[];
    edges: FlowEdge[];
} = {
    nodes: [
        {
            id: "start",
            type: "start",
            position: { x: 0, y: 150 },
            data: {
                status: "idle",
                sourceType: { type: "text" },
            },
            measured: { width: 80, height: 40 },
        },
        {
            id: "router",
            type: "agent",
            position: { x: 150, y: 150 },
            data: {
                name: "Router Node",
                model: WORKFLOW_MODELS[0],
                systemPrompt: "Analyzes user intent and chooses path: SIMPLE or COMPLEX.",
                selectedTools: [],
                status: "idle",
                sourceType: { type: "text" },
                hideResponseInChat: false,
                excludeFromConversation: false,
                maxSteps: 1,
            },
            measured: { width: 180, height: 80 },
        },
        // Simple Path
        {
            id: "simple_agent",
            type: "agent",
            position: { x: 450, y: 50 },
            data: {
                name: "Simple Agent",
                model: WORKFLOW_MODELS[0],
                systemPrompt: "Handles direct tasks using tools.",
                selectedTools: [],
                status: "idle",
                sourceType: { type: "text" },
                hideResponseInChat: false,
                excludeFromConversation: false,
                maxSteps: 5,
            },
            measured: { width: 180, height: 80 },
        },
        {
            id: "tools",
            type: "agent",
            position: { x: 450, y: -50 },
            data: {
                name: "Tools Node",
                model: WORKFLOW_MODELS[0],
                systemPrompt: "Standard tool execution execution environment.",
                selectedTools: [],
                status: "idle",
                sourceType: { type: "text" },
                hideResponseInChat: false,
                excludeFromConversation: false,
                maxSteps: 1,
            },
            measured: { width: 180, height: 80 },
        },
        // Complex Path
        {
            id: "orchestrator",
            type: "agent",
            position: { x: 450, y: 250 },
            data: {
                name: "Orchestrator",
                model: WORKFLOW_MODELS[0],
                systemPrompt: "Plans complex tasks and dispatches workers.",
                selectedTools: [],
                status: "idle",
                sourceType: { type: "text" },
                hideResponseInChat: false,
                excludeFromConversation: false,
                maxSteps: 1,
            },
            measured: { width: 180, height: 80 },
        },
        // Workers Group
        {
            id: "worker_log",
            type: "agent",
            position: { x: 750, y: 150 },
            data: {
                name: "Log Specialist",
                model: WORKFLOW_MODELS[0],
                systemPrompt: "Analyzes logs for errors and anomalies.",
                selectedTools: [],
                status: "idle",
                sourceType: { type: "text" },
                hideResponseInChat: false,
                excludeFromConversation: false,
                maxSteps: 1,
            },
            measured: { width: 180, height: 80 },
        },
        {
            id: "worker_metric",
            type: "agent",
            position: { x: 750, y: 250 },
            data: {
                name: "Metric Specialist",
                model: WORKFLOW_MODELS[0],
                systemPrompt: "Analyzes resource metrics and patterns.",
                selectedTools: [],
                status: "idle",
                sourceType: { type: "text" },
                hideResponseInChat: false,
                excludeFromConversation: false,
                maxSteps: 1,
            },
            measured: { width: 180, height: 80 },
        },
        {
            id: "worker_k8s",
            type: "agent",
            position: { x: 750, y: 350 },
            data: {
                name: "K8s Specialist",
                model: WORKFLOW_MODELS[0],
                systemPrompt: "Inspects Kubernetes cluster state and events.",
                selectedTools: [],
                status: "idle",
                sourceType: { type: "text" },
                hideResponseInChat: false,
                excludeFromConversation: false,
                maxSteps: 1,
            },
            measured: { width: 180, height: 80 },
        },
        // Synthesizer
        {
            id: "synthesizer",
            type: "agent",
            position: { x: 1050, y: 250 },
            data: {
                name: "Synthesizer Node",
                model: WORKFLOW_MODELS[0],
                systemPrompt: "Aggregates worker summaries for deep diagnosis.",
                selectedTools: [],
                status: "idle",
                sourceType: { type: "text" },
                hideResponseInChat: false,
                excludeFromConversation: false,
                maxSteps: 1,
            },
            measured: { width: 180, height: 80 },
        },
        {
            id: "end",
            type: "end",
            position: { x: 1350, y: 150 },
            data: {},
            measured: { width: 80, height: 40 },
        }
    ],
    edges: [
        { id: "e-start-router", source: "start", target: "router", type: "status" },
        // Simple Flow
        { id: "e-router-simple", source: "router", target: "simple_agent", label: "SIMPLE", type: "status", animated: true },
        { id: "e-simple-tools", source: "simple_agent", target: "tools", label: "Tool Call", type: "status" },
        { id: "e-tools-simple", source: "tools", target: "simple_agent", type: "status" },
        { id: "e-simple-end", source: "simple_agent", target: "end", type: "status" },
        // Complex Flow
        { id: "e-router-orch", source: "router", target: "orchestrator", label: "COMPLEX", type: "status", animated: true },
        { id: "e-orch-log", source: "orchestrator", target: "worker_log", type: "status" },
        { id: "e-orch-metric", source: "orchestrator", target: "worker_metric", type: "status" },
        { id: "e-orch-k8s", source: "orchestrator", target: "worker_k8s", type: "status" },
        // Summary collection
        { id: "e-log-synth", source: "worker_log", target: "synthesizer", label: "Summary", type: "status" },
        { id: "e-metric-synth", source: "worker_metric", target: "synthesizer", label: "Summary", type: "status" },
        { id: "e-k8s-synth", source: "worker_k8s", target: "synthesizer", label: "Summary", type: "status" },
        { id: "e-synth-end", source: "synthesizer", target: "end", label: "Final Diagnosis", type: "status" },
    ],
};

export const LANGGRAPH_TEMPLATE = {
    id: "langgraph-agent",
    name: "MCP LangGraph Agent",
    description: "Detailed Multi-Agent Diagnostic Workflow",
    category: "Custom",
    nodes: LANGGRAPH_WORKFLOW.nodes,
    edges: LANGGRAPH_WORKFLOW.edges,
    suggestions: [
        "현재 Kubernetes 클러스터의 상태를 점검해줘",
        "최근 에러가 발생한 파드가 있는지 확인해줘",
        "리소스 사용량이 임계치를 넘은 서비스가 있어?",
    ],
};

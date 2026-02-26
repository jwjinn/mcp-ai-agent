import type { InferUITools, ToolUIPart, UIMessage } from "ai";
import type { workflowTools } from "@/lib/tools";
import type {
	FlowNode,
	NodeStatus,
} from "@/types/workflow";

type WorkflowAIMetadata = Record<string, unknown>;

type WorkflowAIDataPart = {
	"node-execution-status": {
		nodeId: string;
		nodeType: FlowNode["type"];
		name?: string;
		status: NodeStatus;
		error?: string;
	};
	"node-execution-state": {
		nodeId: string;
		nodeType: FlowNode["type"];
		data: FlowNode["data"];
	};
};

type WorkflowAgentToolSet = typeof workflowTools;
type WorkflowAITools = InferUITools<WorkflowAgentToolSet>;

export type WorkflowAIToolUIPart = ToolUIPart<WorkflowAITools>;

export type WorkflowUIMessage = UIMessage<
	WorkflowAIMetadata,
	WorkflowAIDataPart,
	WorkflowAITools
>;

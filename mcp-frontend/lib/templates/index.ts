import { LANGGRAPH_TEMPLATE } from "@/lib/templates/langgraph-workflow";
import type {
	FlowEdge,
	FlowNode,
} from "@/types/workflow";

export type WorkflowTemplate = {
	id: string;
	name: string;
	description: string;
	category: string;
	nodes: FlowNode[];
	edges: FlowEdge[];
	suggestions: string[];
};

export const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
	LANGGRAPH_TEMPLATE,
];

export function getTemplateById(id: string): WorkflowTemplate | undefined {
	return WORKFLOW_TEMPLATES.find((template) => template.id === id);
}

export const DEFAULT_TEMPLATE = WORKFLOW_TEMPLATES[0];

import { agentNodeDefinition } from "@/lib/workflow/nodes/agent";
import { endNodeDefinition } from "@/lib/workflow/nodes/end";
import { ifElseNodeDefinition } from "@/lib/workflow/nodes/if-else";
import { noteNodeDefinition } from "@/lib/workflow/nodes/note";
import { startNodeDefinition } from "@/lib/workflow/nodes/start";
import { waitNodeDefinition } from "@/lib/workflow/nodes/wait";
import type {
	AnyNodeDefinition,
	FlowNodeType,
} from "@/types/workflow";

const nodeDefinitions = {
	agent: agentNodeDefinition,
	"if-else": ifElseNodeDefinition,
	start: startNodeDefinition,
	end: endNodeDefinition,
	note: noteNodeDefinition,
	wait: waitNodeDefinition,
} as const;

export const nodeRegistry = nodeDefinitions;

export function getNodeDefinition<T extends FlowNodeType>(
	type: T,
): (typeof nodeRegistry)[T] {
	return nodeRegistry[type];
}

export function getAllNodeDefinitions(): AnyNodeDefinition[] {
	return Object.values(nodeRegistry);
}

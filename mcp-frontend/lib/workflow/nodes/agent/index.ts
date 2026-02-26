import { agentClientDefinition } from "@/lib/workflow/nodes/agent/agent.client";
import { agentServerDefinition } from "@/lib/workflow/nodes/agent/agent.server";
import {
	type AgentNode,
	agentSharedDefinition,
} from "@/lib/workflow/nodes/agent/agent.shared";
import type { NodeDefinition } from "@/types/workflow";

export const agentNodeDefinition: NodeDefinition<AgentNode> = {
	shared: agentSharedDefinition,
	client: agentClientDefinition,
	server: agentServerDefinition,
};

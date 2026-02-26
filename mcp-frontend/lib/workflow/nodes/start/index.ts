import { startClientDefinition } from "@/lib/workflow/nodes/start/start.client";
import { startServerDefinition } from "@/lib/workflow/nodes/start/start.server";
import {
	type StartNode,
	startSharedDefinition,
} from "@/lib/workflow/nodes/start/start.shared";
import type { NodeDefinition } from "@/types/workflow";

export const startNodeDefinition: NodeDefinition<StartNode> = {
	shared: startSharedDefinition,
	client: startClientDefinition,
	server: startServerDefinition,
};

import { endClientDefinition } from "@/lib/workflow/nodes/end/end.client";
import { endServerDefinition } from "@/lib/workflow/nodes/end/end.server";
import {
	type EndNode,
	endSharedDefinition,
} from "@/lib/workflow/nodes/end/end.shared";
import type { NodeDefinition } from "@/types/workflow";

export const endNodeDefinition: NodeDefinition<EndNode> = {
	shared: endSharedDefinition,
	client: endClientDefinition,
	server: endServerDefinition,
};

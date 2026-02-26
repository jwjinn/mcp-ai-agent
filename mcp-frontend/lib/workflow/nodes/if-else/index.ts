import { ifElseClientDefinition } from "@/lib/workflow/nodes/if-else/if-else.client";
import { ifElseServerDefinition } from "@/lib/workflow/nodes/if-else/if-else.server";
import {
	type IfElseNode,
	ifElseSharedDefinition,
} from "@/lib/workflow/nodes/if-else/if-else.shared";
import type { NodeDefinition } from "@/types/workflow";

export const ifElseNodeDefinition: NodeDefinition<IfElseNode> = {
	shared: ifElseSharedDefinition,
	client: ifElseClientDefinition,
	server: ifElseServerDefinition,
};

import { waitClientDefinition } from "@/lib/workflow/nodes/wait/wait.client";
import { waitServerDefinition } from "@/lib/workflow/nodes/wait/wait.server";
import {
	type WaitNode,
	waitSharedDefinition,
} from "@/lib/workflow/nodes/wait/wait.shared";
import type { NodeDefinition } from "@/types/workflow";

export const waitNodeDefinition: NodeDefinition<WaitNode> = {
	shared: waitSharedDefinition,
	client: waitClientDefinition,
	server: waitServerDefinition,
};

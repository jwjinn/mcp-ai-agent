import { noteClientDefinition } from "@/lib/workflow/nodes/note/note.client";
import { noteServerDefinition } from "@/lib/workflow/nodes/note/note.server";
import {
	type NoteNode,
	noteSharedDefinition,
} from "@/lib/workflow/nodes/note/note.shared";
import type { NodeDefinition } from "@/types/workflow";

export const noteNodeDefinition: NodeDefinition<NoteNode> = {
	shared: noteSharedDefinition,
	client: noteClientDefinition,
	server: noteServerDefinition,
};

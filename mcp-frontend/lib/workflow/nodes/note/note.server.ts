import type { NoteNode } from "@/lib/workflow/nodes/note/note.shared";
import type {
	ExecutionContext,
	NodeExecutionResult,
	NodeServerDefinition,
} from "@/types/workflow";

function executeNoteNode(
	_context: ExecutionContext<NoteNode>,
): NodeExecutionResult {
	throw new Error("Note nodes should not be executed");
}

export const noteServerDefinition: NodeServerDefinition<NoteNode> = {
	execute: executeNoteNode,
};

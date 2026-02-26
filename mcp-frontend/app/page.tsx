"use client";

import {
  Background,
  Controls,
  type EdgeTypes,
  MiniMap,
  type NodeTypes,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import { useEffect } from "react";
import { shallow } from "zustand/shallow";
import "@xyflow/react/dist/style.css";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { Workflow } from "lucide-react";
import { useTheme } from "next-themes";
import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  AppHeader,
  AppHeaderIcon,
  AppHeaderSeparator,
  AppHeaderTitle,
} from "@/components/app-header";
import {
  AppLayout,
  AppLayoutInset,
  AppLayoutSidebar,
} from "@/components/app-layout";
import { Chat } from "@/components/chat";
import { ThemeToggle } from "@/components/theme-toggle";
import { StatusEdge } from "@/components/workflow/status-edge";
import { useWorkflow } from "@/hooks/workflow/use-workflow";
import {
  DEFAULT_TEMPLATE,
  getTemplateById,
} from "@/lib/templates";
import { getAllNodeDefinitions } from "@/lib/workflow/nodes";
import type { WorkflowUIMessage } from "@/types/messages";
import type { FlowNode } from "@/types/workflow";

const nodeDefinitions = getAllNodeDefinitions();
const nodeTypes: NodeTypes = {} as NodeTypes;
for (const definition of nodeDefinitions) {
  // biome-ignore lint/suspicious/noExplicitAny: ReactFlow nodeTypes accepts any component type
  nodeTypes[definition.shared.type] = definition.client.component as any;
}

const edgeTypes: EdgeTypes = {
  status: StatusEdge,
};

export function Flow() {
  const { theme } = useTheme();
  const store = useWorkflow(
    (store) => ({
      nodes: store.nodes,
      edges: store.edges,
      onNodesChange: store.onNodesChange,
      onEdgesChange: store.onEdgesChange,
      onConnect: store.onConnect,
      createNode: store.createNode,
      initializeWorkflow: store.initializeWorkflow,
      updateNode: store.updateNode,
    }),
    shallow,
  );

  const { messages, sendMessage, status, stop, setMessages } =
    useChat<WorkflowUIMessage>({
      transport: new DefaultChatTransport({
        api: "/api/stream_chat",
      }),
      onData: (dataPart) => {
        if (dataPart.type === "data-node-execution-status") {
          store.updateNode({
            id: dataPart.data.nodeId,
            nodeType: dataPart.data.nodeType,
            data: { status: dataPart.data.status },
          });

          if (
            dataPart.data.status === "error" &&
            dataPart.data.error
          ) {
            console.error(
              `Node ${dataPart.data.nodeId} error:`,
              dataPart.data.error,
            );
          }
        }
      },
    });

  const isLoading = status === "streaming" || status === "submitted";

  // biome-ignore lint/correctness/useExhaustiveDependencies: We want to initialize the workflow only once
  useEffect(() => {
    store.initializeWorkflow({
      nodes: DEFAULT_TEMPLATE.nodes,
      edges: DEFAULT_TEMPLATE.edges,
    });
  }, []);

  return (
    <AppLayout>
      <AppLayoutInset>
        <AppHeader>
          <AppHeaderIcon>
            <Workflow />
          </AppHeaderIcon>
          <AppHeaderTitle className="ml-2">
            AI Agent Pipeline
          </AppHeaderTitle>
          <AppHeaderSeparator />
          <ThemeToggle />
          <SidebarTrigger className="ml-auto" />
        </AppHeader>

        <ReactFlow
          nodes={store.nodes}
          edges={store.edges}
          onNodesChange={store.onNodesChange}
          onEdgesChange={store.onEdgesChange}
          onConnect={store.onConnect}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          colorMode={theme === "dark" ? "dark" : "light"}
          nodesDraggable={!isLoading}
          nodesConnectable={!isLoading}
          nodesFocusable={!isLoading}
          edgesFocusable={!isLoading}
          elementsSelectable={!isLoading}
        >
          <Background />
          <Controls />
          <MiniMap />


        </ReactFlow>
      </AppLayoutInset>
      <AppLayoutSidebar>
        <Chat
          messages={messages}
          sendMessage={sendMessage}
          status={status}
          stop={stop}
          setMessages={setMessages}
          selectedTemplateId={DEFAULT_TEMPLATE.id}
        />
      </AppLayoutSidebar>
    </AppLayout>
  );
}

export default function Page() {
  return (
    <div className="w-screen h-screen">
      <ReactFlowProvider>
        <Flow />
      </ReactFlowProvider>
    </div>
  );
}

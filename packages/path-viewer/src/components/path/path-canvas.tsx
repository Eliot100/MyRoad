import { useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MarkerType,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  applyNodeChanges,
  useReactFlow,
  type Connection,
  type Edge,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./flow.css";

import { BlockNodeView, type BlockFlowNode } from "@/components/path/block-node";
import { layoutBlocks, nextBlockId } from "@/lib/path/graph";
import { copyFor, direction, edgeLabel, stateLabel, typeLabel } from "@/lib/path/i18n";
import { usePathStore } from "@/lib/path/store";
import { uiState } from "@/lib/path/types";
import type { PathEdge } from "@/lib/path/types";

const nodeTypes = { block: BlockNodeView };

function edgeLook(edge: PathEdge): { color: string; dash: boolean } {
  if (edge.relationship === "branch") return { color: "var(--color-ink)", dash: false };
  if (edge.relationship === "optional") return { color: "var(--color-stone)", dash: true };
  if (edge.condition?.mastery) return { color: "var(--color-pine)", dash: true };
  return { color: "var(--color-pine)", dash: false };
}

function Framer({ nextId, watch }: { nextId: string | null; watch: string }) {
  const rf = useReactFlow();
  const locale = usePathStore((state) => state.locale);
  const copy = copyFor(locale);

  function frame(mode: "next" | "all") {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const duration = reduce ? 0 : 280;
    if (mode === "all" || !nextId) {
      void rf.fitView({ padding: 0.22, duration, maxZoom: 1 });
      return;
    }
    const node = rf.getNode(nextId);
    if (!node) return;
    const width = node.measured?.width ?? 240;
    const height = node.measured?.height ?? 108;
    const canvas = document.querySelector(".path-canvas")?.clientWidth ?? 800;
    const zoom = canvas >= 760 ? 0.72 : 1;
    void rf.setCenter(node.position.x + width / 2, node.position.y + height / 2, { zoom, duration });
  }

  useEffect(() => {
    const timer = window.setTimeout(() => frame("next"), 60);
    return () => window.clearTimeout(timer);
    // Reframe when the path shape, locale, or suggested block changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [watch, nextId]);

  return (
    <Panel position="top-right" className="flex gap-2">
      <button type="button" className="chip" onClick={() => frame("next")}>
        {copy.next}
      </button>
      <button type="button" className="chip" onClick={() => frame("all")}>
        {copy.wholePath}
      </button>
    </Panel>
  );
}

function CanvasInner() {
  const locale = usePathStore((state) => state.locale);
  const mode = usePathStore((state) => state.mode);
  const blocks = usePathStore((state) => state.blocks);
  const edges = usePathStore((state) => state.edges);
  const positions = usePathStore((state) => state.positions);
  const progress = usePathStore((state) => state.progress);
  const selectedBlockId = usePathStore((state) => state.selectedBlockId);
  const selectedEdgeId = usePathStore((state) => state.selectedEdgeId);
  const selectBlock = usePathStore((state) => state.selectBlock);
  const selectEdge = usePathStore((state) => state.selectEdge);
  const addEdge = usePathStore((state) => state.addEdge);
  const setPosition = usePathStore((state) => state.setPosition);
  const copy = copyFor(locale);
  const rtl = direction(locale) === "rtl";
  const [compact, setCompact] = useState(false);
  const ids = blocks.map((block) => block.blockId);
  const nextId = nextBlockId(ids, edges, progress);
  const placed = useMemo(
    () => positions ?? layoutBlocks(ids, edges, rtl, compact),
    [positions, blocks, edges, rtl, ids, compact],
  );

  const builtNodes = useMemo<BlockFlowNode[]>(
    () =>
      blocks.map((block) => ({
        id: block.blockId,
        type: "block",
        position: placed[block.blockId] ?? { x: 0, y: 0 },
        selected: block.blockId === selectedBlockId,
        data: {
          title: block.title[locale],
          typeLabel: typeLabel(locale, block.type),
          stateLabel: stateLabel(locale, uiState(progress[block.blockId])),
          state: uiState(progress[block.blockId]),
          isNext: block.blockId === nextId,
          draft: mode === "draft",
          rtl,
          nextLabel: copy.next,
        },
        draggable: mode === "draft",
      })),
    [blocks, placed, selectedBlockId, locale, progress, nextId, mode, rtl, copy.next],
  );

  const builtEdges = useMemo<Edge[]>(
    () =>
      edges.map((edge) => {
        const look = edgeLook(edge);
        const label = edgeLabel(locale, edge);
        const selected = edge.edgeId === selectedEdgeId;
        return {
          id: edge.edgeId,
          source: edge.from,
          target: edge.to,
          sourceHandle: "out",
          targetHandle: "in",
          type: "smoothstep",
          label: label ?? undefined,
          selected,
          animated: edge.to === nextId,
          style: {
            stroke: look.color,
            strokeWidth: selected ? 2.4 : 1.5,
            strokeDasharray: look.dash ? "6 5" : undefined,
          },
          markerEnd: { type: MarkerType.ArrowClosed, color: look.color, width: 16, height: 16 },
        };
      }),
    [edges, locale, selectedEdgeId, nextId],
  );

  const [nodes, setNodes] = useState(builtNodes);
  const signature = `${locale}|${mode}|${nextId}|${selectedBlockId}|${selectedEdgeId}|${JSON.stringify(edges)}|${JSON.stringify(progress)}|${JSON.stringify(placed)}`;

  useEffect(() => {
    setNodes(builtNodes);
  }, [signature]);

  useEffect(() => {
    const root = document.querySelector("[data-path-canvas]");
    if (!root) return;
    const apply = () => setCompact(root.clientWidth < 760);
    apply();
    const observer = new ResizeObserver(apply);
    observer.observe(root);
    return () => observer.disconnect();
  }, []);

  function onNodesChange(changes: NodeChange<BlockFlowNode>[]) {
    setNodes((current) => applyNodeChanges(changes.filter((change) => change.type !== "remove"), current));
  }

  function onConnect(connection: Connection) {
    if (connection.source && connection.target) addEdge(connection.source, connection.target);
  }

  return (
    <div className="path-canvas h-full w-full min-w-0" dir="ltr" data-testid="path-map" data-path-canvas>
      <ReactFlow
        nodes={nodes}
        edges={builtEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onNodeClick={(_event, node) => selectBlock(node.id)}
        onEdgeClick={(_event, edge) => selectEdge(edge.id)}
        onPaneClick={() => {
          selectBlock(null);
          selectEdge(null);
        }}
        onConnect={onConnect}
        onNodeDragStop={(_event, node) => setPosition(node.id, node.position)}
        nodesDraggable={mode === "draft"}
        nodesConnectable={mode === "draft"}
        nodesFocusable
        edgesFocusable
        elementsSelectable
        deleteKeyCode={null}
        connectionRadius={36}
        minZoom={0.35}
        maxZoom={1.35}
        panOnScroll
        colorMode="light"
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#6b675e" gap={28} size={1} style={{ opacity: 0.28 }} />
        <Controls showInteractive={false} />
        <Framer nextId={nextId} watch={signature} />
      </ReactFlow>
    </div>
  );
}

export function PathCanvas() {
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  );
}

import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import type { MasteryState } from "@/lib/path/types";

export type BlockNodeData = {
  title: string;
  typeLabel: string;
  stateLabel: string;
  state: MasteryState;
  isNext: boolean;
  draft: boolean;
  rtl: boolean;
  nextLabel: string;
};

export type BlockFlowNode = Node<BlockNodeData, "block">;

export function BlockNodeView({ data, selected }: NodeProps<BlockFlowNode>) {
  const source = data.rtl ? Position.Left : Position.Right;
  const target = data.rtl ? Position.Right : Position.Left;
  return (
    <article
      data-testid="block-node"
      data-block-id={data.title}
      data-state={data.state}
      data-next={data.isNext ? "true" : "false"}
      data-selected={selected ? "true" : "false"}
      data-rtl={data.rtl ? "true" : "false"}
      className="block-node"
    >
      <Handle
        id="in"
        type="target"
        position={target}
        className={data.draft ? "path-handle" : "path-handle is-hidden"}
      />
      <header className="block-node-kicker">
        <span>{data.typeLabel}</span>
        {data.isNext ? <span className="next-pill">{data.nextLabel}</span> : null}
      </header>
      <h3 className="block-node-title">{data.title}</h3>
      <p className="block-node-state">{data.stateLabel}</p>
      <Handle
        id="out"
        type="source"
        position={source}
        className={data.draft ? "path-handle" : "path-handle is-hidden"}
      />
    </article>
  );
}

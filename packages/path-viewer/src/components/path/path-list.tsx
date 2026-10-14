import { copyFor, direction, stateLabel, typeLabel } from "@/lib/path/i18n";
import { nextBlockId, readingOrder } from "@/lib/path/graph";
import { usePathStore } from "@/lib/path/store";
import { uiState } from "@/lib/path/types";

export function PathList() {
  const locale = usePathStore((state) => state.locale);
  const blocks = usePathStore((state) => state.blocks);
  const edges = usePathStore((state) => state.edges);
  const progress = usePathStore((state) => state.progress);
  const selected = usePathStore((state) => state.selectedBlockId);
  const selectBlock = usePathStore((state) => state.selectBlock);
  const copy = copyFor(locale);
  const rtl = direction(locale) === "rtl";
  const ids = blocks.map((block) => block.blockId);
  const order = readingOrder(ids, edges);
  const nextId = nextBlockId(ids, edges, progress);
  const byId = new Map(blocks.map((block) => [block.blockId, block]));

  return (
    <ol className="flex flex-col gap-3 p-4" data-testid="path-list">
      {order.map((id) => {
        const block = byId.get(id);
        if (!block) return null;
        const mastery = uiState(progress[id]);
        const isNext = id === nextId;
        return (
          <li key={id}>
            <button
              type="button"
              className="block-node is-list"
              data-testid="list-block"
              data-block-id={id}
              data-state={mastery}
              data-selected={selected === id ? "true" : "false"}
              data-rtl={rtl ? "true" : "false"}
              data-next={isNext ? "true" : "false"}
              onClick={() => selectBlock(id)}
            >
              <header className="block-node-kicker">
                <span>{typeLabel(locale, block.type)}</span>
                {isNext ? <span className="next-pill">{copy.next}</span> : null}
              </header>
              <h3 className="block-node-title">{block.title[locale]}</h3>
              <p className="block-node-state">{stateLabel(locale, mastery)}</p>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

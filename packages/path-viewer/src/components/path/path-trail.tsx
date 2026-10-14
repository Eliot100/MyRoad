import { useEffect, useRef } from "react";

import { copyFor, direction, stateLabel, typeLabel } from "@/lib/path/i18n";
import { trailStages } from "@/lib/path/graph";
import { usePathStore } from "@/lib/path/store";
import { uiState } from "@/lib/path/types";

export function PathTrail({ nextId }: { nextId: string | null }) {
  const locale = usePathStore((state) => state.locale);
  const pathId = usePathStore((state) => state.pathId);
  const blocks = usePathStore((state) => state.blocks);
  const edges = usePathStore((state) => state.edges);
  const progress = usePathStore((state) => state.progress);
  const selectedBlockId = usePathStore((state) => state.selectedBlockId);
  const selectBlock = usePathStore((state) => state.selectBlock);
  const noteTimeToNext = usePathStore((state) => state.noteTimeToNext);
  const copy = copyFor(locale);
  const rtl = direction(locale) === "rtl";
  const scroller = useRef<HTMLDivElement>(null);
  const openedAt = useRef(performance.now());
  const byId = new Map(blocks.map((block) => [block.blockId, block]));
  const stages = trailStages(
    blocks.map((block) => block.blockId),
    edges,
  );

  useEffect(() => {
    openedAt.current = performance.now();
  }, [pathId]);

  useEffect(() => {
    const root = scroller.current;
    const node = root?.querySelector<HTMLElement>("[data-next=true]");
    if (!root || !node) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    node.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
    const timer = window.setTimeout(() => {
      const rect = node.getBoundingClientRect();
      const box = root.getBoundingClientRect();
      if (rect.top < box.bottom && rect.bottom > box.top) {
        noteTimeToNext(Math.round(performance.now() - openedAt.current));
      }
    }, reduce ? 0 : 360);
    return () => window.clearTimeout(timer);
  }, [nextId, pathId, noteTimeToNext]);

  return (
    <div ref={scroller} className="h-full overflow-y-auto" data-testid="path-trail">
      <div className="path-trail" data-rtl={rtl ? "true" : "false"}>
        {stages.map((stage, index) => (
          <section key={`${stage.stops[0] ?? "spur"}-${index}`} className="trail-stage">
            <p className="trail-stage-label">{copy.stage(index + 1)}</p>
            <ol>
              {stage.stops.map((id) => (
                <TrailStop
                  key={id}
                  id={id}
                  title={byId.get(id)?.title[locale] ?? id}
                  kicker={byId.get(id) ? typeLabel(locale, byId.get(id)!.type) : ""}
                  stateLabel={stateLabel(locale, uiState(progress[id]))}
                  state={uiState(progress[id])}
                  isNext={id === nextId}
                  selected={id === selectedBlockId}
                  nextLabel={copy.next}
                  onSelect={() => selectBlock(id)}
                />
              ))}
              {stage.spurId ? (
                <TrailStop
                  id={stage.spurId}
                  title={byId.get(stage.spurId)?.title[locale] ?? stage.spurId}
                  kicker={byId.get(stage.spurId) ? typeLabel(locale, byId.get(stage.spurId)!.type) : ""}
                  stateLabel={stateLabel(locale, uiState(progress[stage.spurId]))}
                  state={uiState(progress[stage.spurId])}
                  isNext={stage.spurId === nextId}
                  selected={stage.spurId === selectedBlockId}
                  nextLabel={copy.next}
                  spur
                  onSelect={() => selectBlock(stage.spurId!)}
                />
              ) : null}
            </ol>
          </section>
        ))}
      </div>
    </div>
  );
}

function TrailStop({
  id,
  title,
  kicker,
  stateLabel: status,
  state,
  isNext,
  selected,
  nextLabel,
  spur,
  onSelect,
}: {
  id: string;
  title: string;
  kicker: string;
  stateLabel: string;
  state: string;
  isNext: boolean;
  selected: boolean;
  nextLabel: string;
  spur?: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        className="trail-stop"
        data-testid="trail-stop"
        data-block-id={id}
        data-state={state}
        data-next={isNext ? "true" : "false"}
        data-selected={selected ? "true" : "false"}
        data-spur={spur ? "true" : "false"}
        onClick={onSelect}
      >
        <span className="trail-marker" aria-hidden="true" />
        <span className="min-w-0">
          <span className="trail-kicker">
            {kicker}
            {isNext ? <span className="next-pill">{nextLabel}</span> : null}
          </span>
          <span className="trail-title">{title}</span>
          <span className="trail-state">{status}</span>
        </span>
      </button>
    </li>
  );
}

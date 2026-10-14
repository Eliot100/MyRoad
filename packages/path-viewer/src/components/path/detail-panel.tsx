import { copyFor, edgeLabel, reasonLabel, relationshipLabel, stateLabel, typeLabel } from "@/lib/path/i18n";
import { explainNext, moveAlongSpine } from "@/lib/path/graph";
import { usePathStore } from "@/lib/path/store";
import type { MasteryState } from "@/lib/path/types";
import { uiState } from "@/lib/path/types";

import { RichText } from "@/components/path/rich-text";

export function DetailPanel() {
  const locale = usePathStore((state) => state.locale);
  const mode = usePathStore((state) => state.mode);
  const blocks = usePathStore((state) => state.blocks);
  const edges = usePathStore((state) => state.edges);
  const progress = usePathStore((state) => state.progress);
  const description = usePathStore((state) => state.description);
  const selectedBlockId = usePathStore((state) => state.selectedBlockId);
  const selectedEdgeId = usePathStore((state) => state.selectedEdgeId);
  const selectBlock = usePathStore((state) => state.selectBlock);
  const setMastery = usePathStore((state) => state.setMastery);
  const restoreSample = usePathStore((state) => state.restoreSample);
  const startOver = usePathStore((state) => state.startOver);
  const removeEdge = usePathStore((state) => state.removeEdge);
  const cycleRelationship = usePathStore((state) => state.cycleRelationship);
  const moveBlock = usePathStore((state) => state.moveBlock);
  const tidy = usePathStore((state) => state.tidy);
  const resetDraft = usePathStore((state) => state.resetDraft);
  const copy = copyFor(locale);
  const ids = blocks.map((block) => block.blockId);
  const suggestion = explainNext(ids, edges, progress);
  const nextId = suggestion.id;
  const why = reasonLabel(locale, suggestion.reason);
  const byId = new Map(blocks.map((block) => [block.blockId, block]));
  const selected = selectedBlockId ? byId.get(selectedBlockId) : undefined;
  const selectedEdge = edges.find((edge) => edge.edgeId === selectedEdgeId);
  const mastered = ids.filter((id) => uiState(progress[id]) === "mastered").length;

  return (
    <aside
      className="flex max-h-[46%] min-h-0 flex-col overflow-y-auto border-t border-line bg-paper md:max-h-none md:w-[22.5rem] md:shrink-0 md:border-s md:border-t-0"
      data-testid="detail-panel"
    >
      <div className="flex flex-col gap-5 p-4 md:p-5">
        {selectedEdge ? (
          <EdgeInspector />
        ) : selected ? (
          <section className="flex flex-col gap-4">
            <header>
              <p className="text-xs text-stone">{typeLabel(locale, selected.type)}</p>
              <h2 className="mt-1 font-serif text-2xl" data-testid="detail-title">
                {selected.title[locale]}
              </h2>
              <p className="mt-2 text-sm text-stone">{selected.learningObjective[locale]}</p>
            </header>
            <p className="text-sm">
              <span className="text-stone">{copy.currentScore}</span>{" "}
              <span>{stateLabel(locale, uiState(progress[selected.blockId]))}</span>
            </p>
            <div>
              <p className="text-xs text-stone">{copy.passMark}</p>
              <p className="mt-1 text-sm">{selected.masteryRule.passingCriterion[locale]}</p>
            </div>
            <RichText text={selected.body[locale]} />
            <NextLinks />
            <div className="grid grid-cols-1 gap-2">
              <MasteryButton id={selected.blockId} value="in_progress" label={copy.onThis} />
              <MasteryButton id={selected.blockId} value="mastered" label={copy.markMastered} />
              <MasteryButton id={selected.blockId} value="needs_remediation" label={copy.markRemediation} />
            </div>
            {mode === "draft" ? (
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  className="quiet-btn"
                  disabled={moveAlongSpine(ids, edges, selected.blockId, -1) === null}
                  onClick={() => moveBlock(selected.blockId, -1)}
                >
                  {copy.earlier}
                </button>
                <button
                  type="button"
                  className="quiet-btn"
                  disabled={moveAlongSpine(ids, edges, selected.blockId, 1) === null}
                  onClick={() => moveBlock(selected.blockId, 1)}
                >
                  {copy.later}
                </button>
              </div>
            ) : null}
          </section>
        ) : (
          <section className="flex flex-col gap-4">
            {nextId && byId.get(nextId) ? (
              <button type="button" className="primary-btn text-start" onClick={() => selectBlock(nextId)}>
                <span className="block text-xs opacity-80">{copy.suggestedNow}</span>
                <span className="mt-1 block font-serif text-lg">{byId.get(nextId)?.title[locale]}</span>
              </button>
            ) : (
              <p className="text-sm">{copy.nothingLeft}</p>
            )}
            {why ? <p className="text-sm leading-relaxed text-stone">{why}</p> : null}
            <p className="text-sm tabular-nums" data-testid="mastery-count">
              {copy.masteredCount(mastered, ids.length)}
            </p>
            <p className="text-sm leading-relaxed text-stone">{description[locale]}</p>
            <p className="text-sm text-stone">{copy.overviewHint}</p>
            <p className="text-sm text-stone">{copy.localNote}</p>
            <div className="grid grid-cols-1 gap-2">
              <button type="button" className="quiet-btn" onClick={restoreSample}>
                {copy.restoreSample}
              </button>
              <button type="button" className="quiet-btn" onClick={startOver}>
                {copy.startOver}
              </button>
              {mode === "draft" ? (
                <>
                  <button type="button" className="quiet-btn" onClick={tidy}>
                    {copy.tidy}
                  </button>
                  <button type="button" className="quiet-btn" onClick={resetDraft}>
                    {copy.resetDraft}
                  </button>
                </>
              ) : null}
            </div>
          </section>
        )}
      </div>
    </aside>
  );

  function MasteryButton({ id, value, label }: { id: string; value: MasteryState; label: string }) {
    const on = uiState(progress[id]) === value;
    return (
      <button type="button" className={value === "mastered" ? "primary-btn" : "quiet-btn"} data-on={on ? "true" : "false"} onClick={() => setMastery(id, value)}>
        {label}
      </button>
    );
  }

  function NextLinks() {
    if (!selected) return null;
    const outgoing = edges.filter((edge) => edge.from === selected.blockId);
    const suggested = nextId ? byId.get(nextId) : undefined;
    return (
      <div className="flex flex-col gap-2">
        {suggested ? (
          <p className="text-sm">
            <span className="text-stone">{copy.suggestedNow}. </span>
            <button type="button" className="font-medium underline decoration-line underline-offset-4" onClick={() => selectBlock(suggested.blockId)}>
              {suggested.title[locale]}
            </button>
          </p>
        ) : (
          <p className="text-sm text-stone">{copy.nothingLeft}</p>
        )}
        {why ? <p className="text-sm leading-relaxed text-stone">{why}</p> : null}
        {outgoing.length > 0 ? (
          <ul className="space-y-1 text-sm">
            <li className="text-xs text-stone">{copy.fromHere}</li>
            {outgoing.map((edge) => {
              const target = byId.get(edge.to);
              if (!target) return null;
              const label = edgeLabel(locale, edge) ?? copy.sequence;
              return (
                <li key={edge.edgeId}>
                  <button type="button" className="text-start" onClick={() => selectBlock(target.blockId)}>
                    {target.title[locale]}
                    <span className="text-stone"> · {label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    );
  }

  function EdgeInspector() {
    if (!selectedEdge) return null;
    const source = byId.get(selectedEdge.from);
    const target = byId.get(selectedEdge.to);
    const label = relationshipLabel(locale, selectedEdge.relationship);
    return (
      <section className="flex flex-col gap-4">
        <header>
          <p className="text-xs text-stone">{copy.edgeTitle}</p>
          <h2 className="mt-1 font-serif text-2xl">
            {source?.title[locale]}
            <span className="text-stone"> · </span>
            {target?.title[locale]}
          </h2>
          <p className="mt-2 text-sm text-stone">{label}</p>
          {selectedEdge.condition?.mastery ? (
            <p className="mt-1 text-sm text-stone">{selectedEdge.condition.mastery}</p>
          ) : null}
        </header>
        {mode === "draft" ? (
          <div className="grid grid-cols-1 gap-2">
            <button type="button" className="quiet-btn" onClick={() => cycleRelationship(selectedEdge.edgeId)}>
              {label}
            </button>
            <button type="button" className="quiet-btn" onClick={() => removeEdge(selectedEdge.edgeId)}>
              {copy.removeEdge}
            </button>
          </div>
        ) : (
          <p className="text-sm text-stone">{label}</p>
        )}
      </section>
    );
  }
}

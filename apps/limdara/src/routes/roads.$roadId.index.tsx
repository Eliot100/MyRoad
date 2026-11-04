import { createFileRoute, Link } from "@tanstack/react-router";
import { Check, ChevronRight } from "lucide-react";
import { useState } from "react";
import { getRoad } from "@/lib/roads";
import { flatten, formatSpan, kindLabel, roadTotals } from "@/lib/roads/select";
import type { Road } from "@/lib/roads/types";
import { useHydrated, useProgress } from "@/lib/progress";

export const Route = createFileRoute("/roads/$roadId/")({
  component: RoadPage,
});

function RoadPage() {
  const { roadId } = Route.useParams();
  const road = getRoad(roadId);
  if (!road) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-16">
        <h1 className="font-display text-3xl">This road is not on the map.</h1>
        <Link to="/" className="mt-4 inline-flex min-h-11 items-center text-pine">
          All roads
        </Link>
      </main>
    );
  }
  return <RoadBody key={road.id} road={road} />;
}

function RoadBody({ road }: { road: Road }) {
  const hydrated = useHydrated();
  const progress = useProgress((store) => store.nodes);
  const [open, setOpen] = useState<Record<string, boolean>>(() => ({
    [road.stages[0]?.id ?? ""]: true,
  }));
  const totals = roadTotals(road);
  const items = flatten(road);
  const done = items.filter((item) => progress[item.node.id]?.masteredAt).length;

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8">
      <p className="text-sm text-pine">{road.kicker}</p>
      <h1 className="mt-2 font-display text-4xl tracking-tight">{road.title}</h1>
      <p lang="he" dir="rtl" className="text-xl text-stone">
        {road.he}
      </p>
      <p className="mt-4 max-w-2xl text-pretty">{road.exam}</p>
      <p className="mt-4 text-sm text-stone tabular-nums">
        {totals.stages} stages · {totals.nodes} nodes · {totals.bullets} syllabus lines ·{" "}
        {formatSpan(totals.minutes)}
        {hydrated ? ` · ${done} done` : ""}
      </p>
      <div className="mt-3 h-1 max-w-md bg-line" aria-hidden="true">
        <div
          className="h-1 bg-pine"
          style={{ width: `${items.length ? Math.round(((hydrated ? done : 0) / items.length) * 100) : 0}%` }}
        />
      </div>

      <div className="mt-10 space-y-4">
        {road.stages.map((stage) => {
          const stageNodes = stage.levels.flatMap((level) => level.nodes);
          const stageDone = stageNodes.filter((node) => progress[node.id]?.masteredAt).length;
          return (
            <details
              key={stage.id}
              open={Boolean(open[stage.id])}
              onToggle={(event) => {
                const isOpen = event.currentTarget.open;
                setOpen((prev) => (prev[stage.id] === isOpen ? prev : { ...prev, [stage.id]: isOpen }));
              }}
              className="border border-line bg-paper"
            >
              <summary className="flex min-h-11 items-center gap-3 px-4 py-3">
                <ChevronRight className="twist size-4 shrink-0 text-pine" aria-hidden="true" />
                <span className="w-8 shrink-0 text-sm text-pine tabular-nums">
                  {String(stage.index).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-display text-xl">{stage.title}</span>
                  <span lang="he" dir="rtl" className="block text-sm text-stone">
                    {stage.he}
                  </span>
                </span>
                <span className="shrink-0 text-sm text-stone tabular-nums">
                  {hydrated ? `${stageDone}/${stageNodes.length}` : stageNodes.length}
                </span>
              </summary>
              <div className="border-t border-line px-4 py-4 sm:px-5">
                <p className="max-w-2xl text-pretty text-sm">{stage.thesis}</p>
                <h2 className="mt-5 text-sm text-pine">Syllabus</h2>
                <ul className="mt-2 border-t border-line">
                  {stage.syllabus.map((bullet) => {
                    const owner = stageNodes.find((node) => node.covers.includes(bullet));
                    const marked = owner ? Boolean(progress[owner.id]?.masteredAt) : false;
                    return (
                      <li key={bullet} className="flex items-start gap-3 border-b border-line py-2">
                        <span className="mt-1 inline-flex size-4 shrink-0 items-center justify-center text-pine">
                          {hydrated && marked ? <Check className="size-4" aria-hidden="true" /> : null}
                        </span>
                        {owner ? (
                          <Link
                            to="/roads/$roadId/nodes/$nodeId"
                            params={{ roadId: road.id, nodeId: owner.id }}
                            className="min-w-0 text-ink"
                          >
                            {bullet}
                          </Link>
                        ) : (
                          <span className="text-stone">{bullet} — unclaimed</span>
                        )}
                      </li>
                    );
                  })}
                </ul>
                <div className="mt-6 space-y-6">
                  {stage.levels.map((level, levelIndex) => (
                    <section key={level.id}>
                      <h3 className="font-display text-lg">
                        Level {levelIndex + 1} · {level.title}
                      </h3>
                      <p lang="he" dir="rtl" className="text-sm text-stone">
                        {level.he}
                      </p>
                      <p className="mt-1 text-sm text-pretty text-stone">{level.intent}</p>
                      <ul className="mt-2 border-t border-line">
                        {level.nodes.map((node) => {
                          const marked = Boolean(progress[node.id]?.masteredAt);
                          return (
                            <li key={node.id} className="border-b border-line">
                              <Link
                                to="/roads/$roadId/nodes/$nodeId"
                                params={{ roadId: road.id, nodeId: node.id }}
                                className="flex min-h-11 items-center gap-3 py-2"
                              >
                                <span className="w-16 shrink-0 text-sm text-pine">{kindLabel(node.kind)}</span>
                                <span className="min-w-0 flex-1">
                                  <span className="block">{node.title}</span>
                                  <span lang="he" dir="rtl" className="block text-sm text-stone">
                                    {node.he}
                                  </span>
                                </span>
                                <span className="shrink-0 text-sm text-stone tabular-nums">{node.minutes} min</span>
                                {hydrated && marked ? (
                                  <Check className="size-4 shrink-0 text-pine" aria-hidden="true" />
                                ) : null}
                              </Link>
                            </li>
                          );
                        })}
                      </ul>
                    </section>
                  ))}
                </div>
              </div>
            </details>
          );
        })}
      </div>
    </main>
  );
}

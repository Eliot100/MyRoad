import { createFileRoute, Link } from "@tanstack/react-router";
import { titled } from "@/lib/brand";
import { useHydrated, useProgress } from "@/lib/progress";
import { roads } from "@/lib/roads";
import { allNodes, flatten, formatSpan, roadTotals } from "@/lib/roads/select";

export const Route = createFileRoute("/progress")({
  head: () => ({ meta: [{ title: titled("Progress") }] }),
  component: ProgressPage,
});

function ProgressPage() {
  const hydrated = useHydrated();
  const nodes = useProgress((store) => store.nodes);
  const lastId = useProgress((store) => store.lastId);
  const mastered = new Set(
    Object.entries(nodes)
      .filter(([, node]) => node.masteredAt)
      .map(([id]) => id),
  );
  const flat = allNodes(roads);
  const done = hydrated ? flat.filter((item) => mastered.has(item.node.id)).length : 0;
  const due = hydrated
    ? flat.filter((item) => {
        const reviewAt = nodes[item.node.id]?.reviewAt;
        return reviewAt !== undefined && reviewAt <= Date.now();
      }).length
    : 0;
  const last = lastId ? flat.find((item) => item.node.id === lastId) : undefined;
  const next = flat.find((item) => !mastered.has(item.node.id));
  const continueItem = last && !mastered.has(last.node.id) ? last : next;
  const pct = flat.length ? Math.round((done / flat.length) * 100) : 0;

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8">
      <p className="text-sm text-pine">This device</p>
      <h1 className="mt-2 font-display text-4xl tracking-tight">Progress</h1>
      <p className="mt-4 max-w-2xl text-pretty text-stone">
        Mastered nodes, what is due, and where you stopped. The count stays in this browser. It does not follow
        you to another phone until you are on that device.
      </p>

      <p className="mt-8 font-display text-5xl tabular-nums tracking-tight">{hydrated ? `${pct}%` : "—"}</p>
      <p className="mt-1 text-sm text-stone tabular-nums">
        {hydrated ? `${done} of ${flat.length} nodes` : "Checking this device."}
        {hydrated && due > 0 ? ` · ${due} due` : ""}
      </p>
      <div className="mt-3 h-1 max-w-md bg-line" aria-hidden="true">
        <div className="h-1 bg-pine" style={{ width: `${hydrated ? pct : 0}%` }} />
      </div>

      {hydrated && continueItem ? (
        <Link
          to="/roads/$roadId/nodes/$nodeId"
          params={{ roadId: continueItem.road.id, nodeId: continueItem.node.id }}
          className="mt-8 block max-w-xl border border-line bg-pine-soft px-4 py-4"
        >
          <span className="text-sm text-pine">Continue</span>
          <span className="mt-1 block font-display text-2xl">{continueItem.node.title}</span>
          <span className="mt-1 block text-sm text-stone">
            {continueItem.road.title} · {continueItem.stage.title}
          </span>
        </Link>
      ) : null}

      <ul className="mt-10 border-t border-line">
        {roads.map((road) => {
          const totals = roadTotals(road);
          const items = flatten(road);
          const roadDone = hydrated ? items.filter((item) => mastered.has(item.node.id)).length : 0;
          const roadPct = items.length ? Math.round((roadDone / items.length) * 100) : 0;
          return (
            <li key={road.id} className="border-b border-line py-4">
              <Link
                to="/roads/$roadId"
                params={{ roadId: road.id }}
                className="flex min-h-11 items-baseline justify-between gap-3"
              >
                <span>
                  <span className="font-display text-2xl">{road.title}</span>
                  <span lang="he" dir="rtl" className="ms-2 text-sm text-stone">
                    {road.he}
                  </span>
                </span>
                <span className="text-sm text-stone tabular-nums">{hydrated ? `${roadPct}%` : ""}</span>
              </Link>
              <p className="mt-1 text-sm text-stone tabular-nums">
                {hydrated ? `${roadDone} of ${items.length} nodes` : `${items.length} nodes`} ·{" "}
                {totals.stages} stages · {formatSpan(totals.minutes)}
              </p>
              <div className="mt-3 h-1 bg-line" aria-hidden="true">
                <div className="h-1 bg-pine" style={{ width: `${roadPct}%` }} />
              </div>
            </li>
          );
        })}
      </ul>

      {hydrated && due > 0 ? (
        <p className="mt-8 text-sm">
          <Link to="/review" className="text-pine">
            {due} nodes are due for review.
          </Link>
        </p>
      ) : null}
    </main>
  );
}

import { createFileRoute, Link } from "@tanstack/react-router";
import { Atom, BookOpen, Compass, Languages, Sigma, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { audit } from "@/lib/forge/audit";
import { useHydrated, useProgress } from "@/lib/progress";
import { roads } from "@/lib/roads";
import { allNodes, flatten, formatSpan, roadTotals } from "@/lib/roads/select";
import { field } from "@/components/ui";
import { BRAND, BRAND_HE, BRAND_LINE } from "@/lib/brand";

export const Route = createFileRoute("/")({
  component: Home,
});

const ICONS: Record<string, LucideIcon> = {
  "math-5": Sigma,
  "english-5": BookOpen,
  "physics-5": Atom,
  "arabic-5": Languages,
  psychometric: Compass,
};

function Home() {
  const hydrated = useHydrated();
  const progress = useProgress((store) => store.nodes);
  const lastId = useProgress((store) => store.lastId);
  const report = audit(roads);
  const [query, setQuery] = useState("");
  const mastered = new Set(
    Object.entries(progress)
      .filter(([, node]) => node.masteredAt)
      .map(([id]) => id),
  );

  const flat = allNodes(roads);
  const next = flat.find((item) => !mastered.has(item.node.id));
  const last = lastId ? flat.find((item) => item.node.id === lastId) : undefined;
  const continueItem = last && !mastered.has(last.node.id) ? last : next;
  const due = hydrated
    ? flat.filter((item) => {
        const reviewAt = progress[item.node.id]?.reviewAt;
        return reviewAt !== undefined && reviewAt <= Date.now();
      })
    : [];

  const needle = query.trim().toLowerCase();
  const hits = needle
    ? flat
        .filter((item) => {
          const hay = `${item.node.title} ${item.node.he} ${item.stage.title} ${item.node.covers.join(" ")}`.toLowerCase();
          return hay.includes(needle);
        })
        .slice(0, 8)
    : [];

  const openFindings = report.findings.length;

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8">
      <p className="text-sm text-pine">
        {BRAND} · <span lang="he">{BRAND_HE}</span> · {BRAND_LINE}
      </p>
      <h1 className="mt-2 max-w-2xl font-display text-4xl tracking-tight">
        Five exams, cut until every line has a home.
      </h1>
      <p className="mt-4 max-w-2xl text-pretty text-stone">
        5-unit mathematics, English, physics, and Arabic, and the psychometric from the outside of the test
        to a simulation. A stage is one topic. A stage has three levels. Each level is two nodes, and each
        node owns one syllabus line.
      </p>

      <form className="mt-6 max-w-xl" onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="find" className="text-sm text-stone">
          Find a node
        </label>
        <input
          id="find"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Slope, Snell, analogy, idafa"
          className={field}
        />
      </form>
      {needle ? (
        <ul className="mt-3 max-w-xl border-t border-line">
          {hits.length === 0 ? (
            <li className="py-3 text-sm text-stone">Nothing matches.</li>
          ) : (
            hits.map((item) => (
              <li key={item.node.id} className="border-b border-line">
                <Link
                  to="/roads/$roadId/nodes/$nodeId"
                  params={{ roadId: item.road.id, nodeId: item.node.id }}
                  className="flex min-h-11 items-center justify-between gap-3 py-2"
                >
                  <span>
                    {item.node.title}
                    <span className="mt-0.5 block text-sm text-stone">
                      {item.road.title} · {item.stage.title}
                    </span>
                  </span>
                </Link>
              </li>
            ))
          )}
        </ul>
      ) : null}

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

      <ol className="mt-10 grid gap-3 sm:grid-cols-3">
        {[
          ["Stage", "One topic. Not a chapter that hides three exams inside it."],
          ["Level", "Foundations, technique, then mastery. The same three, on every stage."],
          ["Node", "One syllabus line: a lesson, a worked example, and checks. Together the nodes cover the topic."],
        ].map(([title, copy], index) => (
          <li key={title} className="border-t border-line pt-3">
            <p className="text-sm text-pine tabular-nums">0{index + 1}</p>
            <h2 className="mt-1 font-display text-xl">{title}</h2>
            <p className="mt-2 text-sm text-pretty text-stone">{copy}</p>
          </li>
        ))}
      </ol>

      <section className="mt-10">
        <h2 className="font-display text-2xl">The platform</h2>
        <p className="mt-2 max-w-2xl text-sm text-pretty text-stone">
          The same roads on the web and on Android. Study, come back for review, and see how much of the cut is
          done. Nothing here is sent to an account.
        </p>
        <ul className="mt-4 grid gap-3 sm:grid-cols-3">
          <li>
            <Link to="/review" className="block min-h-11 border-t border-line py-3 hover:text-pine">
              <span className="font-display text-xl">Review</span>
              <span className="mt-1 block text-sm text-stone">
                {hydrated && due.length > 0 ? `${due.length} due now` : "Due nodes come back here."}
              </span>
            </Link>
          </li>
          <li>
            <Link to="/progress" className="block min-h-11 border-t border-line py-3 hover:text-pine">
              <span className="font-display text-xl">Progress</span>
              <span className="mt-1 block text-sm text-stone">Every road, counted on this device.</span>
            </Link>
          </li>
          <li>
            <Link to="/android" className="block min-h-11 border-t border-line py-3 hover:text-pine">
              <span className="font-display text-xl">Android</span>
              <span className="mt-1 block text-sm text-stone">Install the same platform on the home screen.</span>
            </Link>
          </li>
        </ul>
      </section>

      <div className="mt-10 grid gap-8 sm:grid-cols-2">
        {roads.map((road) => {
          const Icon = ICONS[road.id] ?? BookOpen;
          const totals = roadTotals(road);
          const items = flatten(road);
          const done = hydrated ? items.filter((item) => mastered.has(item.node.id)).length : 0;
          const pct = items.length ? Math.round((done / items.length) * 100) : 0;
          return (
            <Link
              key={road.id}
              to="/roads/$roadId"
              params={{ roadId: road.id }}
              className="stack block focus-visible:outline-2"
            >
              <span className="stack-back" aria-hidden="true" />
              <article className="stack-front relative border border-line bg-paper p-5 hover:border-pine">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm text-pine">{road.kicker}</p>
                  <Icon className="size-5 text-pine" aria-hidden="true" />
                </div>
                <h2 className="mt-3 font-display text-3xl tracking-tight">{road.title}</h2>
                <p lang="he" dir="rtl" className="text-stone">
                  {road.he}
                </p>
                <p className="mt-3 text-sm text-pretty text-ink">{road.summary}</p>
                <p className="mt-4 text-sm text-stone tabular-nums">
                  {totals.stages} stages · {totals.nodes} nodes · {formatSpan(totals.minutes)}
                </p>
                <div className="mt-3 h-1 bg-line" aria-hidden="true">
                  <div className="h-1 bg-pine" style={{ width: `${pct}%` }} />
                </div>
                <p className="mt-2 text-sm text-stone tabular-nums">
                  {hydrated ? `${done} of ${items.length} nodes done` : `${items.length} nodes`}
                </p>
              </article>
            </Link>
          );
        })}
      </div>

      {due.length > 0 ? (
        <section className="mt-12 max-w-xl">
          <h2 className="font-display text-2xl">Due</h2>
          <ul className="mt-3 border-t border-line">
            {due.slice(0, 6).map((item) => (
              <li key={item.node.id} className="border-b border-line">
                <Link
                  to="/roads/$roadId/nodes/$nodeId"
                  params={{ roadId: item.road.id, nodeId: item.node.id }}
                  className="flex min-h-11 items-center py-2"
                >
                  {item.node.title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <p className="mt-12 max-w-2xl text-sm text-pretty text-stone">
        <Link to="/forge" className="text-pine">
          The Forge
        </Link>{" "}
        is the loop that built the cut: partition, level, cover, practice, review.
        {openFindings === 0
          ? " Right now every syllabus line is owned by a node."
          : ` Right now the audit shows ${openFindings} gaps.`}
      </p>
    </main>
  );
}

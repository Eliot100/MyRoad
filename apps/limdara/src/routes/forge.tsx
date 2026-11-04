import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { btn, btnQuiet } from "@/components/ui";
import { titled } from "@/lib/brand";
import { audit } from "@/lib/forge/audit";
import { useHydrated, useProgress } from "@/lib/progress";
import { roads } from "@/lib/roads";
import { formatSpan } from "@/lib/roads/select";

export const Route = createFileRoute("/forge")({
  head: () => ({ meta: [{ title: titled("Forge") }] }),
  component: ForgePage,
});

const PASSES = [
  ["Partition", "partition-", "One topic, one stage. Names stay distinct."],
  ["Levels", "levels-", "Foundations, technique, mastery. Read, drill, worked, drill, read, check."],
  ["Cover", "cover-", "Every syllabus line is owned by exactly one node."],
  ["Practice", "practice-", "A worked example, and checks with answers you can type."],
] as const;

function ForgePage() {
  const hydrated = useHydrated();
  const report = audit(roads);
  const log = useProgress((store) => store.forge);
  const logForge = useProgress((store) => store.logForge);
  const pullDue = useProgress((store) => store.pullDue);
  const reset = useProgress((store) => store.reset);
  const [note, setNote] = useState<string | null>(null);
  const [armed, setArmed] = useState(false);

  function run() {
    const pulled = pullDue();
    const summary =
      report.findings.length === 0
        ? pulled
          ? `Coverage holds. ${pulled} weak ${pulled === 1 ? "node" : "nodes"} pulled due.`
          : "Coverage holds. No weak node was waiting."
        : `${report.findings.length} gaps still open.${pulled ? ` ${pulled} pulled due.` : ""}`;
    logForge({ at: Date.now(), findings: report.findings.length, pulled, summary });
    setNote(summary);
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8">
      <p className="text-sm text-pine">The loop</p>
      <h1 className="mt-2 font-display text-4xl tracking-tight">Forge</h1>
      <p className="mt-4 max-w-2xl text-pretty">
        Limdara is cut by a loop, not by a pile of lessons. Partition the exam into topics. Give each topic
        one stage. Split the stage into three levels. Give each syllabus line a node. Then audit. Then bring
        weak nodes back. Running it does not invent a new syllabus. It checks this one, and it pulls shaky
        work onto today's list.
      </p>

      <ol className="mt-8 border-t border-line">
        {PASSES.map(([name, prefix, detail], index) => {
          const gaps = report.findings.filter((finding) => finding.code.startsWith(prefix)).length;
          return (
            <li key={name} className="grid grid-cols-[2.5rem_1fr_auto] gap-3 border-b border-line py-3">
              <span className="text-sm text-pine tabular-nums">0{index + 1}</span>
              <span>
                <span className="block font-display text-xl">{name}</span>
                <span className="mt-1 block text-sm text-pretty text-stone">{detail}</span>
              </span>
              <span className="text-sm text-ink">{gaps === 0 ? "Holds" : `${gaps}`}</span>
            </li>
          );
        })}
        <li className="grid grid-cols-[2.5rem_1fr] gap-3 border-b border-line py-3">
          <span className="text-sm text-pine tabular-nums">05</span>
          <span>
            <span className="block font-display text-xl">Review</span>
            <span className="mt-1 block text-sm text-pretty text-stone">
              A clean node returns in three days. More misses than matches, and the loop pulls it due now.
            </span>
          </span>
        </li>
      </ol>

      <button type="button" className={`${btn} mt-6`} onClick={run}>
        Run the loop
      </button>
      {note ? <p className="mt-3 text-sm text-ink">{note}</p> : null}

      <h2 className="mt-10 font-display text-2xl">Coverage</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <thead className="text-stone">
            <tr className="border-b border-line">
              <th className="py-2 font-normal">Road</th>
              <th className="py-2 font-normal">Stages</th>
              <th className="py-2 font-normal">Nodes</th>
              <th className="py-2 font-normal">Lines owned</th>
              <th className="py-2 font-normal">Time</th>
            </tr>
          </thead>
          <tbody>
            {report.roads.map((row) => {
              const road = roads.find((item) => item.id === row.id);
              return (
                <tr key={row.id} className="border-b border-line tabular-nums">
                  <td className="py-2">
                    <Link to="/roads/$roadId" params={{ roadId: row.id }} className="text-pine">
                      {road?.title ?? row.id}
                    </Link>
                  </td>
                  <td className="py-2">{row.stages}</td>
                  <td className="py-2">{row.nodes}</td>
                  <td className="py-2">
                    {row.covered}/{row.bullets}
                  </td>
                  <td className="py-2">{formatSpan(row.minutes)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {report.findings.length > 0 ? (
        <section className="mt-8">
          <h2 className="font-display text-2xl">Open gaps</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {report.findings.slice(0, 40).map((finding) => (
              <li key={`${finding.code}-${finding.detail}`} className="border-b border-line py-2">
                {finding.detail}
              </li>
            ))}
          </ul>
          {report.findings.length > 40 ? (
            <p className="mt-2 text-sm text-stone">{report.findings.length - 40} more.</p>
          ) : null}
        </section>
      ) : (
        <p className="mt-8 text-sm text-pretty text-stone">
          Coverage holds. The next turn of the loop is review, not more topics.
        </p>
      )}

      <h2 className="mt-10 font-display text-2xl">Log</h2>
      {!hydrated || log.length === 0 ? (
        <p className="mt-3 text-sm text-stone">No pass has been run on this device yet.</p>
      ) : (
        <ul className="mt-3 border-t border-line text-sm">
          {log.map((entry) => (
            <li key={entry.at} className="border-b border-line py-3">
              <span className="text-stone">
                {new Date(entry.at).toLocaleString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              <span className="mt-1 block text-ink">{entry.summary}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-10 border-t border-line pt-6">
        {armed ? (
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className={btn}
              onClick={() => {
                reset();
                setArmed(false);
                setNote("Progress on this device was cleared.");
              }}
            >
              Yes, clear it
            </button>
            <button type="button" className={btnQuiet} onClick={() => setArmed(false)}>
              Keep it
            </button>
          </div>
        ) : (
          <button type="button" className={btnQuiet} onClick={() => setArmed(true)}>
            Clear progress on this device
          </button>
        )}
      </div>
    </main>
  );
}

import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { btn, btnQuiet, field } from "@/components/ui";
import { answersMatch } from "@/lib/roads/answers";
import { dirFor, kindLabel } from "@/lib/roads/select";
import type { FlatNode, LessonNode, PracticeItem } from "@/lib/roads/types";
import { useHydrated, useProgress } from "@/lib/progress";

function Check({
  item,
  index,
  onResult,
}: {
  item: PracticeItem;
  index: number;
  onResult: (ok: boolean) => void;
}) {
  const [value, setValue] = useState("");
  const [result, setResult] = useState<null | "ok" | "miss">(null);

  function submit() {
    if (result || !value.trim()) return;
    const ok = answersMatch(value, item.answer);
    setResult(ok ? "ok" : "miss");
    onResult(ok);
  }

  return (
    <form
      className="border-t border-line py-5"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <p className="text-sm text-stone">Check {index + 1}</p>
      <p dir={dirFor(item.q)} className="mt-2 whitespace-pre-wrap text-pretty">
        {item.q}
      </p>
      <label className="mt-4 block text-sm text-stone" htmlFor={`ans-${index}`}>
        Your answer
      </label>
      <input
        id={`ans-${index}`}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        className={field}
        autoComplete="off"
        disabled={result !== null}
      />
      <button type="submit" className={`${btn} mt-3`} disabled={result !== null || !value.trim()}>
        Check
      </button>
      {result ? (
        <div role="status" className="mt-4 space-y-2 text-sm">
          <p className="text-ink">{result === "ok" ? "Matched." : "Not the same string. The model answer is below."}</p>
          <p className="text-ink">
            <span className="text-stone">Answer. </span>
            <span dir={dirFor(item.answer)}>{item.answer}</span>
          </p>
          <p dir={dirFor(item.why)} className="whitespace-pre-wrap text-pretty text-ink">
            {item.why}
          </p>
        </div>
      ) : null}
    </form>
  );
}

function Example({ node }: { node: LessonNode }) {
  const [shown, setShown] = useState(0);
  const total = node.example.steps.length;
  return (
    <section className="mt-8">
      <h2 className="font-display text-xl">Worked example</h2>
      <p dir={dirFor(node.example.prompt)} className="mt-3 whitespace-pre-wrap text-pretty">
        {node.example.prompt}
      </p>
      {shown > 0 ? (
        <ol className="mt-4 list-decimal space-y-2 ps-5">
          {node.example.steps.slice(0, shown).map((step) => (
            <li key={step} dir={dirFor(step)} className="whitespace-pre-wrap text-pretty">
              {step}
            </li>
          ))}
        </ol>
      ) : null}
      {shown >= total ? (
        <p className="mt-4 text-ink">
          <span className="text-stone">Answer. </span>
          <span dir={dirFor(node.example.answer)}>{node.example.answer}</span>
        </p>
      ) : (
        <button type="button" className={`${btnQuiet} mt-4`} onClick={() => setShown((n) => n + 1)}>
          {shown === 0 ? "Show the first step" : "Show the next step"}
        </button>
      )}
    </section>
  );
}

export function StudySession({
  item,
}: {
  item: FlatNode & { prev?: FlatNode; next?: FlatNode };
}) {
  const { road, stage, level, node, prev, next } = item;
  const hydrated = useHydrated();
  const state = useProgress((store) => store.nodes[node.id]);
  const setLast = useProgress((store) => store.setLast);
  const record = useProgress((store) => store.record);
  const master = useProgress((store) => store.master);

  useEffect(() => {
    setLast(node.id);
  }, [node.id, setLast]);

  const done = Boolean(hydrated && state?.masteredAt);

  return (
    <article className="mx-auto w-full max-w-2xl px-4 py-8">
      <p className="text-sm text-stone">
        <Link to="/roads/$roadId" params={{ roadId: road.id }} className="text-pine">
          {road.title}
        </Link>
        {" · "}
        Stage {String(stage.index).padStart(2, "0")}
        {" · "}
        {level.title}
      </p>
      <p className="mt-4 text-sm text-pine">{kindLabel(node.kind)}</p>
      <h1 className="mt-1 font-display text-3xl tracking-tight">{node.title}</h1>
      <p lang="he" dir="rtl" className="mt-2 text-xl text-stone">
        {node.he}
      </p>
      <p className="mt-3 text-sm text-stone">{node.minutes} min</p>

      <h2 className="mt-8 font-display text-xl">You should be able to</h2>
      <ul className="mt-3 list-disc space-y-1 ps-5">
        {node.objectives.map((objective) => (
          <li key={objective}>{objective}</li>
        ))}
      </ul>

      <div className="mt-6 space-y-4">
        {node.teach.split(/\n\n+/).map((paragraph) => (
          <p key={paragraph.slice(0, 48)} dir={dirFor(paragraph)} className="whitespace-pre-wrap text-pretty">
            {paragraph}
          </p>
        ))}
      </div>

      <h2 className="mt-8 font-display text-xl">Rules</h2>
      <ul className="mt-3 space-y-2 border-t border-line">
        {node.rules.map((rule) => (
          <li key={rule} dir={dirFor(rule)} className="border-b border-line py-2 whitespace-pre-wrap">
            {rule}
          </li>
        ))}
      </ul>

      <p className="mt-6 text-sm text-stone">This node owns: {node.covers.join("; ")}</p>

      <Example node={node} />

      <h2 className="mt-10 font-display text-xl">Checks</h2>
      {node.practice.map((item, index) => (
        <Check key={item.q} item={item} index={index} onResult={(ok) => record(node.id, ok)} />
      ))}

      <div className="mt-6 border border-line bg-paper-2 p-4">
        <p className="text-sm text-pretty text-stone">
          Mark the node done when the checks make sense. A clean pass returns in three days. More misses than
          matches, and it returns tomorrow.
        </p>
        <button type="button" className={`${btn} mt-3`} onClick={() => master(node.id)}>
          {done ? "Update the done mark" : "Mark this node done"}
        </button>
        {done && state?.reviewAt ? (
          <p className="mt-3 text-sm text-ink">
            Due back{" "}
            {new Date(state.reviewAt).toLocaleDateString(undefined, {
              day: "numeric",
              month: "short",
            })}
            .
          </p>
        ) : null}
      </div>

      <div className="mt-8 grid grid-cols-2 gap-3">
        {prev ? (
          <Link
            to="/roads/$roadId/nodes/$nodeId"
            params={{ roadId: road.id, nodeId: prev.node.id }}
            className={btnQuiet}
          >
            Previous
          </Link>
        ) : (
          <span />
        )}
        {next ? (
          <Link
            to="/roads/$roadId/nodes/$nodeId"
            params={{ roadId: road.id, nodeId: next.node.id }}
            className={btn}
          >
            Next node
          </Link>
        ) : (
          <Link to="/roads/$roadId" params={{ roadId: road.id }} className={btn}>
            Back to the road
          </Link>
        )}
      </div>
    </article>
  );
}

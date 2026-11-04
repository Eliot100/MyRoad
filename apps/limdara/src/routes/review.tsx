import { createFileRoute, Link } from "@tanstack/react-router";
import { titled } from "@/lib/brand";
import { useHydrated, useProgress } from "@/lib/progress";
import { roads } from "@/lib/roads";
import { allNodes } from "@/lib/roads/select";

export const Route = createFileRoute("/review")({
  head: () => ({ meta: [{ title: titled("Review") }] }),
  component: ReviewPage,
});

function ReviewPage() {
  const hydrated = useHydrated();
  const progress = useProgress((store) => store.nodes);
  const now = Date.now();
  const due = allNodes(roads).filter((item) => {
    const reviewAt = progress[item.node.id]?.reviewAt;
    return reviewAt !== undefined && reviewAt <= now;
  });

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8">
      <p className="text-sm text-pine">Spaced return</p>
      <h1 className="mt-2 font-display text-4xl tracking-tight">Review</h1>
      <p className="mt-4 text-pretty text-stone">
        Done nodes come back. A clean pass waits three days. A node you missed more than you matched comes
        back sooner, and a Forge pass can pull it due immediately.
      </p>
      {!hydrated ? (
        <p className="mt-8 text-sm text-stone">Checking this device.</p>
      ) : due.length === 0 ? (
        <p className="mt-8 text-pretty">
          Nothing is due. Mark nodes done on a road and they will return here.
        </p>
      ) : (
        <ul className="mt-8 border-t border-line">
          {due.map((item) => (
            <li key={item.node.id} className="border-b border-line">
              <Link
                to="/roads/$roadId/nodes/$nodeId"
                params={{ roadId: item.road.id, nodeId: item.node.id }}
                className="flex min-h-11 flex-col justify-center py-2"
              >
                <span>{item.node.title}</span>
                <span className="text-sm text-stone">
                  {item.road.title} · {item.stage.title}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

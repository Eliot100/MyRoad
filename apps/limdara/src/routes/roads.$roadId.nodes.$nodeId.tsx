import { createFileRoute, Link } from "@tanstack/react-router";
import { StudySession } from "@/components/study";
import { roads } from "@/lib/roads";
import { locate } from "@/lib/roads/select";

export const Route = createFileRoute("/roads/$roadId/nodes/$nodeId")({
  component: NodePage,
});

function NodePage() {
  const { roadId, nodeId } = Route.useParams();
  const found = locate(roads, nodeId);

  if (!found || found.road.id !== roadId) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-16">
        <h1 className="font-display text-3xl">This node is not on the road.</h1>
        <Link to="/roads/$roadId" params={{ roadId }} className="mt-4 inline-flex min-h-11 items-center text-pine">
          Back to the road
        </Link>
      </main>
    );
  }

  return <StudySession key={nodeId} item={found} />;
}

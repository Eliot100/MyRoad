import { useEffect, useRef, useState } from "react";

import { DetailPanel } from "@/components/path/detail-panel";
import { PathList } from "@/components/path/path-list";
import { PathTrail } from "@/components/path/path-trail";
import { copyFor, direction, LOCALES } from "@/lib/path/i18n";
import { explainNext } from "@/lib/path/graph";
import { listPaths } from "@/lib/path/path-store";
import { usePathStore } from "@/lib/path/store";
import { uiState } from "@/lib/path/types";

type CanvasComponent = typeof import("@/components/path/path-canvas").PathCanvas;

export function PathShell() {
  const locale = usePathStore((state) => state.locale);
  const mode = usePathStore((state) => state.mode);
  const status = usePathStore((state) => state.status);
  const blocks = usePathStore((state) => state.blocks);
  const edges = usePathStore((state) => state.edges);
  const progress = usePathStore((state) => state.progress);
  const progressByPath = usePathStore((state) => state.progressByPath);
  const metrics = usePathStore((state) => state.metrics);
  const setLocale = usePathStore((state) => state.setLocale);
  const setMode = usePathStore((state) => state.setMode);
  const selectBlock = usePathStore((state) => state.selectBlock);
  const pathId = usePathStore((state) => state.pathId);
  const title = usePathStore((state) => state.title);
  const version = usePathStore((state) => state.version);
  const openPath = usePathStore((state) => state.openPath);
  const noteSession = usePathStore((state) => state.noteSession);
  const noteSettings = usePathStore((state) => state.noteSettings);
  const notePresentation = usePathStore((state) => state.notePresentation);
  const [presentation, setPresentation] = useState<"map" | "list">("map");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [Canvas, setCanvas] = useState<CanvasComponent | null>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void usePathStore.persist.rehydrate();
  }, []);

  useEffect(() => {
    if (sessionStorage.getItem("myroad-session")) return;
    sessionStorage.setItem("myroad-session", "1");
    noteSession();
  }, [noteSession]);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = direction(locale);
  }, [locale]);

  useEffect(() => {
    if (mode !== "draft") return;
    let live = true;
    void import("@/components/path/path-canvas").then((mod) => {
      if (live) setCanvas(() => mod.PathCanvas);
    });
    return () => {
      live = false;
    };
  }, [mode]);

  useEffect(() => {
    if (!settingsOpen) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setSettingsOpen(false);
    }
    function onPointer(event: PointerEvent) {
      if (!settingsRef.current?.contains(event.target as Node)) setSettingsOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [settingsOpen]);

  const copy = copyFor(locale);
  const ids = blocks.map((block) => block.blockId);
  const suggestion = explainNext(ids, edges, progress);
  const nextId = suggestion.id;
  const byId = new Map(blocks.map((block) => [block.blockId, block]));
  const mastered = ids.filter((id) => uiState(progress[id]) === "mastered").length;
  const nextBlock = nextId ? byId.get(nextId) : undefined;
  const showCanvas = presentation === "map" && mode === "draft" && Canvas;

  let masteredBlocks = 0;
  let pathsOpen = 0;
  let pathsDone = 0;
  for (const path of listPaths()) {
    const record = path.pathId === pathId ? progress : progressByPath[path.pathId];
    const pathIds = path.blocks.map((block) => block.blockId);
    masteredBlocks += pathIds.filter((id) => uiState(record?.[id]) === "mastered").length;
    const next = explainNext(pathIds, path.edges, record ?? {});
    if (next.reason === "done") pathsDone += 1;
    else if (next.id) pathsOpen += 1;
  }

  function choosePresentation(next: "map" | "list") {
    setPresentation(next);
    notePresentation(next);
    setSettingsOpen(false);
  }

  return (
    <div className="flex h-dvh min-h-0 w-full min-w-0 flex-col overflow-hidden bg-paper text-ink">
      <header className="relative z-20 shrink-0 min-w-0 border-b border-line px-4 py-3 md:px-6">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-serif text-xl tracking-tight">MyRoad</p>
            <h1 className="mt-1 font-serif text-2xl tracking-tight md:text-3xl" data-testid="path-title">
              {title[locale]}
            </h1>
            <p className="mt-1 text-sm text-stone">
              <span>{status === "draft" ? copy.draft : copy.published}</span>
              <span> · {copy.version(version)}</span>
              <span> · {copy.masteredCount(mastered, ids.length)}</span>
            </p>
            {nextBlock ? (
              <button type="button" className="next-link" onClick={() => selectBlock(nextBlock.blockId)}>
                <span className="next-pill">{copy.next}</span>
                <span>{nextBlock.title[locale]}</span>
              </button>
            ) : (
              <p className="mt-2 text-sm text-stone">{copy.nothingLeft}</p>
            )}
          </div>
          <div className="relative" ref={settingsRef}>
            <button
              type="button"
              className="settings-btn"
              aria-label={copy.settings}
              aria-expanded={settingsOpen}
              data-testid="settings-button"
              onClick={() => {
                setSettingsOpen((open) => {
                  if (!open) noteSettings();
                  return !open;
                });
              }}
            >
              <Gear />
            </button>
            {settingsOpen ? (
              <div className="settings-pop" role="dialog" aria-label={copy.settings}>
                <p className="settings-label">{copy.settings}</p>
                <div className="mt-2 flex flex-wrap gap-1" role="group" aria-label="Locale">
                  {LOCALES.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="chip"
                      data-on={locale === item.id ? "true" : "false"}
                      aria-pressed={locale === item.id}
                      onClick={() => setLocale(item.id)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <div className="mt-3 flex flex-col gap-1" role="group" aria-label="Path">
                  {listPaths().map((path) => (
                    <button
                      key={path.pathId}
                      type="button"
                      className="quiet-btn text-start"
                      data-on={pathId === path.pathId ? "true" : "false"}
                      aria-pressed={pathId === path.pathId}
                      onClick={() => {
                        openPath(path.pathId);
                        setSettingsOpen(false);
                      }}
                    >
                      {path.name[locale]}
                    </button>
                  ))}
                </div>
                <div className="mt-3 flex flex-wrap gap-1">
                  <button type="button" className="chip" data-on={mode === "view" ? "true" : "false"} onClick={() => setMode("view")}>
                    {copy.view}
                  </button>
                  <button
                    type="button"
                    className="chip"
                    data-on={mode === "draft" ? "true" : "false"}
                    disabled={status !== "draft"}
                    onClick={() => setMode("draft")}
                  >
                    {copy.editing}
                  </button>
                  <button type="button" className="chip" data-on={presentation === "map" ? "true" : "false"} onClick={() => choosePresentation("map")}>
                    {copy.map}
                  </button>
                  <button type="button" className="chip" data-on={presentation === "list" ? "true" : "false"} onClick={() => choosePresentation("list")}>
                    {copy.list}
                  </button>
                </div>
                <div className="mt-4 border-t border-line pt-3">
                  <p className="settings-label">{copy.quality}</p>
                  <p className="mt-1 text-sm text-stone">{copy.qualityNote}</p>
                  <p className="mt-3 text-xs text-stone">{copy.uiGroup}</p>
                  <Metric label={copy.timeToNext} value={copy.milliseconds(metrics.timeToNextMs)} />
                  <Metric label={copy.mapToggles} value={String(metrics.mapOpens)} />
                  <Metric label={copy.listToggles} value={String(metrics.listOpens)} />
                  <Metric label={copy.settingsOpens} value={String(metrics.settingsOpens)} />
                  <p className="mt-3 text-xs text-stone">{copy.learnGroup}</p>
                  <Metric label={copy.masteredBlocks} value={String(masteredBlocks)} />
                  <Metric label={copy.recovered} value={String(metrics.recoveredChecks)} />
                  <Metric label={copy.returns} value={String(metrics.returnsAfterBranch)} />
                  <p className="mt-3 text-xs text-stone">{copy.keepGroup}</p>
                  <Metric label={copy.sessions} value={String(metrics.sessions)} />
                  <Metric label={copy.pathsOpen} value={String(pathsOpen)} />
                  <Metric label={copy.pathsDone} value={String(pathsDone)} />
                </div>
              </div>
            ) : null}
          </div>
        </div>
        {mode === "draft" ? <p className="mt-2 max-w-3xl text-sm text-stone">{copy.editHint}</p> : null}
        {status !== "draft" ? <p className="mt-2 text-sm text-stone">{copy.publishedLock}</p> : null}
      </header>
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <div className="min-h-0 min-w-0 flex-1 overflow-hidden">
          {presentation === "list" ? (
            <div className="h-full overflow-y-auto">
              <PathList />
            </div>
          ) : showCanvas && Canvas ? (
            <Canvas />
          ) : (
            <PathTrail nextId={nextId} />
          )}
        </div>
        <DetailPanel />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <p className="mt-1 flex items-baseline justify-between gap-3 text-sm">
      <span className="text-stone">{label}</span>
      <span className="shrink-0 tabular-nums">{value}</span>
    </p>
  );
}

function Gear() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M12 3.5v2.2M12 18.3v2.2M4.8 6.8l1.6 1.6M17.6 15.6l1.6 1.6M3.5 12h2.2M18.3 12h2.2M4.8 17.2l1.6-1.6M17.6 8.4l1.6-1.6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

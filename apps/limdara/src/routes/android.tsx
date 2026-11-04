import { createFileRoute, Link } from "@tanstack/react-router";
import { BRAND, BRAND_HE, titled } from "@/lib/brand";

export const Route = createFileRoute("/android")({
  head: () => ({ meta: [{ title: titled("Android") }] }),
  component: AndroidPage,
});

const STEPS = [
  ["Open in Chrome", "On the phone, open this site in Chrome. Other browsers can install it too, Chrome is the sure path."],
  ["Install", "Use the menu, then Install app or Add to Home screen. Accept the name Limdara."],
  ["Open from the home screen", "It opens full screen, with Roads, Review, Progress, and Android along the bottom. The same five exams are inside."],
] as const;

function AndroidPage() {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8">
      <p className="text-sm text-pine">The phone</p>
      <h1 className="mt-2 font-display text-4xl tracking-tight">Android</h1>
      <p className="mt-4 max-w-2xl text-pretty text-stone">
        {BRAND} on Android is the same platform, not a thinner copy. Mathematics, English, physics, Arabic, and
        the psychometric. Review and progress stay on that phone.
      </p>
      <p lang="he" dir="rtl" className="mt-3 text-stone">
        {BRAND_HE}
      </p>

      <ol className="mt-10 border-t border-line">
        {STEPS.map(([title, copy], index) => (
          <li key={title} className="grid grid-cols-[2.5rem_1fr] gap-3 border-b border-line py-4">
            <span className="text-sm text-pine tabular-nums">0{index + 1}</span>
            <span>
              <span className="font-display text-2xl">{title}</span>
              <span className="mt-1 block text-pretty text-sm text-stone">{copy}</span>
            </span>
          </li>
        ))}
      </ol>

      <section className="mt-10 max-w-2xl">
        <h2 className="font-display text-2xl">What the installed app is</h2>
        <p className="mt-3 text-pretty text-stone">
          A full-screen install of this site. The study nodes, the worked examples, and the checks are the ones
          already on the web. There is no second syllabus hiding in a store build.
        </p>
        <p className="mt-3 text-pretty text-stone">
          A Play Store listing can come later. It would wrap this same app. Until then, the home-screen install
          is the Android app.
        </p>
        <p className="mt-6">
          <Link to="/" className="text-pine">
            Back to the roads
          </Link>
        </p>
      </section>
    </main>
  );
}

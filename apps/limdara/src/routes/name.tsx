import { createFileRoute } from "@tanstack/react-router";
import { BRAND, BRAND_HE, BRAND_LINE, BRAND_SAY, titled } from "@/lib/brand";

export const Route = createFileRoute("/name")({
  head: () => ({ meta: [{ title: titled("The name") }] }),
  component: NamePage,
});

function NamePage() {
  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8">
      <p className="text-sm text-pine">{BRAND_LINE}</p>
      <h1 className="mt-2 font-display text-4xl tracking-tight">{BRAND}</h1>
      <p lang="he" dir="rtl" className="mt-2 text-xl text-ink">
        {BRAND_HE}
      </p>
      <p className="mt-4 text-sm text-stone">Said {BRAND_SAY}.</p>

      <div className="mt-8 space-y-4 text-pretty">
        <p>
          The word is coined from limud, learning, and derekh, a road. Together they are the thing the platform
          is: learning roads. The Hebrew name that sits under it is{" "}
          <span lang="he" dir="rtl">
            {BRAND_HE}
          </span>
          .
        </p>
        <p>
          <span lang="he" dir="rtl">
            {BRAND_HE}
          </span>{" "}
          is the meaning you publish in Hebrew. It is not the legal mark. A phrase that only says
          “ways of learning” is descriptive, so it is hard to own in Israel and easy for someone else to use
          beside you. “Learning roads” has the same problem in English.
        </p>
        <p>
          Darchei on its own is already used by schools. {BRAND} is one invented word in Latin letters. It has
          no dictionary meaning in English, Spanish, French, German, or Arabic, and it is short enough to say
          on a store listing, a domain, and a company line.
        </p>
        <p className="text-sm text-stone">
          This is a naming choice, not a lawyer’s clearance. Before a company or a store listing, search Israel,
          the United States, and the European Union in classes 9, 41, and 42.
        </p>
      </div>
    </main>
  );
}

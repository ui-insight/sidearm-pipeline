import { Link } from "react-router";

const WORKFLOW_STEPS = [
  {
    number: "01",
    title: "Bring in the record",
    description:
      "Sidearm schedules, rosters, box scores, and play-by-play enter one all-sport warehouse.",
  },
  {
    number: "02",
    title: "Verify the facts",
    description:
      "Staff resolve identities, review gaps, and keep every useful fact connected to its source.",
  },
  {
    number: "03",
    title: "Find the story",
    description:
      "The warehouse reveals trends, comparisons, records, and milestones worth watching.",
  },
  {
    number: "04",
    title: "Prepare the coverage",
    description:
      "Communications staff build, review, approve, and route coverage with the evidence close by.",
  },
] as const;

const WALKTHROUGH_STARTS = [
  {
    label: "Data operations",
    title: "From Sidearm to a verified game record",
    description:
      "See where schedules and box scores arrive, how source coverage is reviewed, and where uncertain identities are resolved.",
    linkLabel: "Begin with data operations",
    to: "/games",
  },
  {
    label: "Analytics",
    title: "From a warehouse question to a story opportunity",
    description:
      "Explore seasons, compare performances, review the record book, and identify milestones that should stay on the desk's radar.",
    linkLabel: "Begin with analytics",
    to: "/workspace",
  },
  {
    label: "Communications",
    title: "From verified evidence to approved coverage",
    description:
      "Open the article desk to review suggested briefs, develop drafts, and keep editorial decisions with Athletics staff.",
    linkLabel: "Begin with communications",
    to: "/articles",
  },
] as const;

function ArrowIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      fill="none"
      className="size-4 shrink-0"
    >
      <path
        d="M4 10h11m-4-4 4 4-4 4"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function AthleticsDemoPage() {
  return (
    <div className="bg-gray-50 text-gray-950">
      <section className="bg-gray-950 text-gray-100">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[minmax(0,1.35fr)_minmax(18rem,0.65fr)] lg:items-end lg:gap-20 lg:px-8 lg:py-20">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-yellow-400">
              Guided Athletics demo
            </p>
            <h1 className="mt-5 max-w-3xl text-4xl font-bold tracking-[-0.03em] text-gray-50 sm:text-5xl sm:leading-[1.08]">
              Follow a fact from Sidearm to the story.
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-gray-300">
              See how Athletics can turn public source records into a trusted
              warehouse, find the context that matters, and prepare accurate
              coverage without losing the evidence behind it.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <Link
                to="/demo/pregame-brief"
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-yellow-400 px-5 py-2.5 text-sm font-bold text-gray-950 transition-colors hover:bg-yellow-500 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-400"
              >
                Start the featured walkthrough
                <ArrowIcon />
              </Link>
              <a
                href="#walkthroughs"
                className="inline-flex min-h-11 items-center justify-center rounded-md px-4 py-2.5 text-sm font-semibold text-gray-200 transition-colors hover:bg-gray-800 hover:text-gray-50 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-400"
              >
                Choose a starting point
              </a>
            </div>
          </div>

          <div className="border-t border-gray-700 pt-6 lg:border-t-0 lg:border-l lg:pb-1 lg:pl-8">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-gray-400">
              Featured walkthrough
            </p>
            <h2 className="mt-3 text-xl font-bold text-gray-50">
              Historical pregame brief
            </h2>
            <p className="mt-3 text-sm leading-6 text-gray-400">
              Revisit an Idaho and Montana State matchup using only the
              information available before tipoff. Every conclusion stays tied
              to the retained source evidence.
            </p>
            <p className="mt-5 font-mono text-xs uppercase tracking-[0.08em] text-yellow-400">
              About 5 minutes · Available now
            </p>
          </div>
        </div>
      </section>

      <section
        aria-labelledby="workflow-heading"
        className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8 lg:py-20"
      >
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-yellow-700">
            The basic workflow
          </p>
          <h2
            id="workflow-heading"
            className="mt-3 text-3xl font-bold tracking-tight text-gray-950"
          >
            One connected path from source to decision
          </h2>
          <p className="mt-4 text-sm leading-6 text-gray-600">
            Each workspace handles a different part of the job, while the
            underlying facts and their sources remain connected throughout.
          </p>
        </div>

        <ol className="mt-9 border-y-2 border-gray-950 md:grid md:grid-cols-4 md:divide-x md:divide-gray-300">
          {WORKFLOW_STEPS.map((step) => (
            <li
              key={step.number}
              className="border-b border-gray-300 py-6 last:border-b-0 md:border-b-0 md:px-6 md:first:pl-0 md:last:pr-0"
            >
              <span className="font-mono text-xs font-semibold tabular-nums text-yellow-700">
                {step.number}
              </span>
              <h3 className="mt-3 text-base font-bold text-gray-950">
                {step.title}
              </h3>
              <p className="mt-2 text-sm leading-6 text-gray-600">
                {step.description}
              </p>
            </li>
          ))}
        </ol>
      </section>

      <section
        id="walkthroughs"
        aria-labelledby="walkthroughs-heading"
        className="border-y border-gray-200 bg-white"
      >
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[minmax(15rem,0.65fr)_minmax(0,1.35fr)] lg:gap-20 lg:px-8 lg:py-20">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-yellow-700">
              Explore the prototype
            </p>
            <h2
              id="walkthroughs-heading"
              className="mt-3 max-w-md text-3xl font-bold tracking-tight text-gray-950"
            >
              Choose where to begin
            </h2>
            <p className="mt-4 max-w-md text-sm leading-6 text-gray-600">
              Start with the scripted pregame example, or branch into one of
              the working areas to shape the rest of the conversation around
              your audience.
            </p>
          </div>

          <div>
            <div className="border-y-2 border-gray-950 bg-gray-950 px-5 py-6 text-gray-100 sm:flex sm:items-center sm:justify-between sm:gap-8">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.08em] text-yellow-400">
                  Recommended first
                </p>
                <h3 className="mt-2 text-xl font-bold text-gray-50">
                  Historical pregame brief
                </h3>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-400">
                  See verified history become a timely editorial angle, then
                  reveal the actual result after the pregame evidence has been
                  reviewed.
                </p>
              </div>
              <Link
                to="/demo/pregame-brief"
                className="mt-5 inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-md bg-yellow-400 px-4 py-2.5 text-sm font-bold text-gray-950 transition-colors hover:bg-yellow-500 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-400 sm:mt-0"
              >
                Start walkthrough
                <ArrowIcon />
              </Link>
            </div>

            <ul className="border-b-2 border-gray-950">
              {WALKTHROUGH_STARTS.map((walkthrough) => (
                <li
                  key={walkthrough.to}
                  className="grid gap-3 border-b border-gray-300 py-6 last:border-b-0 sm:grid-cols-[8rem_minmax(0,1fr)_auto] sm:items-start sm:gap-5"
                >
                  <p className="text-xs font-bold uppercase tracking-[0.08em] text-yellow-700">
                    {walkthrough.label}
                  </p>
                  <div>
                    <h3 className="text-base font-bold text-gray-950">
                      {walkthrough.title}
                    </h3>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
                      {walkthrough.description}
                    </p>
                  </div>
                  <Link
                    to={walkthrough.to}
                    className="inline-flex min-h-10 items-center gap-2 self-center text-sm font-bold text-gray-800 underline decoration-yellow-500 decoration-2 underline-offset-4 hover:text-gray-950 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-500"
                  >
                    {walkthrough.linkLabel}
                    <ArrowIcon />
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}

export default AthleticsDemoPage;

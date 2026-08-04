import { Link } from "react-router";

const PLATFORM_GOALS = [
  {
    number: "01",
    title: "Bring athletics records into one workspace",
    description:
      "Collect schedules, rosters, box scores, and game details so the desk has a consistent starting point for current and historical work.",
  },
  {
    number: "02",
    title: "Keep every answer connected to its source",
    description:
      "Preserve the evidence behind scores, player lines, records, and editorial claims so staff can verify a fact before using it.",
  },
  {
    number: "03",
    title: "Make years of history useful in the moment",
    description:
      "Find meaningful comparisons, milestones, trends, and prior matchups without rebuilding the research in a spreadsheet.",
  },
  {
    number: "04",
    title: "Move confidently from research to coverage",
    description:
      "Turn verified facts into pregame briefs and article preparation while keeping Athletics staff in control of every editorial decision.",
  },
] as const;

const AVAILABLE_CAPABILITIES = [
  {
    title: "Season and game intake",
    description:
      "Bring in schedules, rosters, and Sidearm box scores, then refresh current-season records as new results arrive.",
  },
  {
    title: "Game, player, and team research",
    description:
      "Review game evidence, filter the historical workspace, compare players, and trace every result back to its source.",
  },
  {
    title: "Records and achievement discovery",
    description:
      "Search the record book, surface notable performances, and review possible achievements before they are used in coverage.",
  },
  {
    title: "Plain-language questions",
    description:
      "Ask focused questions about the athletics record and receive an answer with the supporting evidence kept close by.",
  },
  {
    title: "Identity and data-quality review",
    description:
      "Resolve uncertain player matches and source gaps through visible review queues instead of relying on guesses.",
  },
  {
    title: "Article preparation",
    description:
      "Build an evidence-based brief, prepare an editable draft, and require human review before anything is approved for publication.",
  },
] as const;

function ProjectOverviewPage() {
  return (
    <div className="bg-gray-50 text-gray-950">
      <section className="bg-gray-950 text-gray-100">
        <div className="mx-auto grid max-w-7xl gap-12 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[minmax(0,1.35fr)_minmax(18rem,0.65fr)] lg:items-end lg:gap-20 lg:px-8 lg:py-20">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-yellow-400">
              University of Idaho Athletics
            </p>
            <h1 className="mt-5 max-w-3xl text-4xl font-bold tracking-[-0.03em] text-gray-50 sm:text-5xl sm:leading-[1.08]">
              One trusted place to find the facts behind every game.
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-gray-300">
              Vandals Stats Desk brings schedules, rosters, box scores, player
              history, and source evidence together so Athletics staff can
              research faster, resolve questions, and prepare accurate coverage.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <Link
                to="/demo"
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-yellow-400 px-5 py-2.5 text-sm font-bold text-gray-950 transition-colors hover:bg-yellow-500 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-400"
              >
                Start the Athletics demo
                <svg
                  aria-hidden="true"
                  viewBox="0 0 20 20"
                  fill="none"
                  className="size-4"
                >
                  <path
                    d="M4 10h11m-4-4 4 4-4 4"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.8"
                  />
                </svg>
              </Link>
              <Link
                to="/games"
                className="inline-flex min-h-11 items-center justify-center rounded-md px-4 py-2.5 text-sm font-semibold text-gray-200 transition-colors hover:bg-gray-800 hover:text-gray-50 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-400"
              >
                Open the games desk
              </Link>
            </div>
          </div>

          <div className="border-t border-gray-700 pt-6 lg:border-t-0 lg:border-l lg:pb-1 lg:pl-8">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-gray-400">
              The working rhythm
            </p>
            <ol className="mt-5 grid grid-cols-2 gap-x-6 gap-y-5 lg:grid-cols-1">
              {["Collect", "Verify", "Explore", "Prepare"].map(
                (step, index) => (
                  <li key={step} className="flex items-center gap-3">
                    <span className="font-mono text-xs tabular-nums text-yellow-400">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="text-sm font-semibold text-gray-100">
                      {step}
                    </span>
                  </li>
                ),
              )}
            </ol>
          </div>
        </div>
      </section>

      <section
        aria-labelledby="platform-purpose"
        className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8 lg:py-20"
      >
        <div className="grid gap-10 lg:grid-cols-[minmax(15rem,0.65fr)_minmax(0,1.35fr)] lg:gap-20">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-yellow-700">
              The vision
            </p>
            <h2
              id="platform-purpose"
              className="mt-3 max-w-md text-3xl font-bold tracking-tight text-gray-950"
            >
              What this platform is here to do
            </h2>
            <p className="mt-4 max-w-md text-sm leading-6 text-gray-600">
              Give Athletics one reliable path from public records to a fact
              that is ready to inform a decision, answer a question, or support
              a story.
            </p>
          </div>

          <ol className="border-t-2 border-gray-950">
            {PLATFORM_GOALS.map((goal) => (
              <li
                key={goal.number}
                className="grid gap-3 border-b border-gray-300 py-6 sm:grid-cols-[3rem_minmax(0,1fr)] sm:gap-5"
              >
                <span className="font-mono text-xs font-semibold tabular-nums text-yellow-700">
                  {goal.number}
                </span>
                <div>
                  <h3 className="text-lg font-bold text-gray-950">
                    {goal.title}
                  </h3>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
                    {goal.description}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section
        aria-labelledby="available-now"
        className="border-y border-gray-200 bg-white"
      >
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[minmax(15rem,0.65fr)_minmax(0,1.35fr)] lg:gap-20 lg:px-8 lg:py-20">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-green-50 px-3 py-1 text-xs font-bold text-green-800">
              <span aria-hidden="true" className="size-1.5 rounded-full bg-green-700" />
              Ready to demonstrate
            </div>
            <h2
              id="available-now"
              className="mt-4 max-w-md text-3xl font-bold tracking-tight text-gray-950"
            >
              Available in this prototype
            </h2>
            <p className="mt-4 max-w-md text-sm leading-6 text-gray-600">
              These working experiences can be shown today. The prototype uses
              prepared athletics records and keeps editorial review with staff.
            </p>
          </div>

          <ul className="grid border-t-2 border-gray-950 sm:grid-cols-2">
            {AVAILABLE_CAPABILITIES.map((capability, index) => (
              <li
                key={capability.title}
                className={`border-b border-gray-300 py-6 sm:min-h-40 ${
                  index % 2 === 0 ? "sm:pr-7" : "sm:border-l sm:pl-7"
                }`}
              >
                <div className="flex items-start gap-3">
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 20 20"
                    fill="none"
                    className="mt-0.5 size-5 shrink-0 text-green-700"
                  >
                    <circle cx="10" cy="10" r="8.25" stroke="currentColor" strokeWidth="1.5" />
                    <path
                      d="m6.5 10.25 2.25 2.25 4.75-5"
                      stroke="currentColor"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="1.5"
                    />
                  </svg>
                  <div>
                    <h3 className="font-bold text-gray-950">
                      {capability.title}
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-gray-600">
                      {capability.description}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="flex flex-col gap-6 border-b-2 border-gray-950 pb-10 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-yellow-700">
              Guided experience
            </p>
            <h2 className="mt-3 text-2xl font-bold tracking-tight text-gray-950">
              See how the desk turns history into a pregame brief.
            </h2>
          </div>
          <Link
            to="/demo"
            className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 self-start rounded-md bg-gray-950 px-5 py-2.5 text-sm font-bold text-gray-50 transition-colors hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-500 sm:self-auto"
          >
            Enter the demo
            <span aria-hidden="true">→</span>
          </Link>
        </div>
      </section>
    </div>
  );
}

export default ProjectOverviewPage;

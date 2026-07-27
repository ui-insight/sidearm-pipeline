# Issue tracker: GitHub

Issues and PRDs for this repository live in GitHub Issues for
`ui-insight/sidearm-pipeline`. Use the GitHub app when available and the `gh`
CLI for operations not covered by the app.

## Conventions

- Create an issue with `gh issue create --title "..." --body "..."`.
- Read an issue and its discussion with `gh issue view <number> --comments`.
- List issues with `gh issue list`, using JSON output when structured data is needed.
- Comment with `gh issue comment <number> --body "..."`.
- Apply or remove labels with `gh issue edit <number> --add-label "..."` or
  `--remove-label "..."`.
- Close an issue with `gh issue close <number> --comment "..."`.

Infer the repository from the local Git remote when operating inside this
checkout. When a skill says to publish to the issue tracker, create a GitHub
issue in `ui-insight/sidearm-pipeline`.

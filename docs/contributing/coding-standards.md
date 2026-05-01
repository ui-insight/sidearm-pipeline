# Coding Standards

## Backend (Python)

### Formatting and Linting
- **Tool**: Ruff
- **Line length**: 88 characters
- **Run**: `ruff check . && ruff format .`
- CI enforces zero lint errors and consistent formatting

### Naming Conventions
- `snake_case` for functions, variables, and module names
- `PascalCase` for class names
- `UPPER_CASE` for constants
- Descriptive names — avoid single-letter variables except in comprehensions

### Code Organization
- One model file per resource: `backend/app/models/user.py`
- One schema file per resource: `backend/app/schemas/user.py`
- One route file per resource: `backend/app/api/v1/users.py`
- Business logic in service modules: `backend/app/services/`
- Keep route handlers thin — validate input, call service, return response

### Async Patterns
- All database operations must be async
- Use `async with` for session management
- Never use synchronous SQLAlchemy operations

### Testing
- Tests mirror source structure: `backend/tests/test_users.py`
- Use `pytest` with `pytest-asyncio`
- Test fixtures in `conftest.py`
- Use in-memory SQLite for fast test isolation even though runtime environments standardize on PostgreSQL

## Frontend (TypeScript/React)

### Formatting and Linting
- **Tool**: ESLint
- **Policy**: zero warnings allowed
- **Run**: `npx eslint .`
- Type checking: `tsc -b` must pass with no errors

### Component Conventions
- Functional components with hooks only (no class components)
- One component per file
- `PascalCase` for component names and filenames
- `camelCase` for functions, variables, and non-component files

### Styling
- **Tailwind CSS utility classes only**
- No CSS component libraries (Bootstrap, Material UI, Chakra, etc.)
- No CSS modules or inline styles
- No custom CSS unless absolutely necessary

### State Management
- React Context for shared application state
- `useState` / `useReducer` for local component state
- API calls centralized in `frontend/src/api/` modules

### Type Safety
- All components and functions must be typed
- Interface files in `frontend/src/types/`
- No `any` types unless absolutely necessary (and documented)

## End-to-End Tests

### Playwright
- Browser smoke tests live in `e2e/tests/`
- Prefer a few high-signal workflows over broad, brittle coverage
- Keep selectors user-facing where possible (`getByRole`, `getByText`)
- Use E2E tests to validate routing, rendering, and critical browser flows

## Git Conventions

### Branching
- Feature branches from `main`: `feature/add-user-management`
- Bug fix branches: `fix/login-redirect`
- Documentation branches: `docs/update-api-reference`
- Never commit directly to `main`

### Commits
- Imperative mood: "Add user login" not "Added user login"
- Concise subject line (50 characters or less)
- Body for context when the "why" isn't obvious
- AI-assisted commits must include:
  ```
  Co-Authored-By: [Agent Name] <noreply@anthropic.com>
  ```

### Pull Requests
- Use the PR template
- If a PR fully resolves an issue, include `Closes #NN`, `Fixes #NN`, or
  `Resolves #NN` in the PR description so GitHub closes it on merge
- For partial work, use `Related to #NN` and summarize what remains
- All CI checks must pass before merge
- At least one review for non-trivial changes
- If docs, governance, or template setup changed, run `python scripts/check_template_docs.py`

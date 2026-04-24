# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, use one of these methods:

1. **GitHub Private Advisory**: Go to the Security tab of this repository and click
   "Report a vulnerability" to create a private security advisory.
2. **Email**: Contact the project maintainers directly.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if you have one)

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

## Supported Versions

| Version | Supported |
|---|---|
| Latest on `main` | Yes |
| Older releases | Best effort |

## Security Practices

This project follows these security practices:

- **Dependency scanning**: Dependabot alerts and weekly `pip-audit` / `npm audit` in CI
- **SBOM generation**: CycloneDX SBOM artifacts for Python and JavaScript dependencies
- **Code review**: all changes go through pull requests
- **Secret management**: no secrets in source code; environment variables only
- **Input validation**: Pydantic schemas on all API endpoints

## Known Limitations

The following are known limitations that are acceptable for development but must be
addressed before production deployment:

- Authentication and RBAC are template extension points, not fully implemented
  starter features
- If a project uses bearer tokens during development, avoid keeping them in
  localStorage for production; prefer a safer documented strategy
- Default `SECRET_KEY` must be changed for production
- `DEV_MODE=true` bypasses certain security checks
- Default local PostgreSQL credentials must be changed for shared or production environments
- Optional SQLite fallback should not be used for shared or production deployments

See `docs/security/overview.md` for the full security documentation.

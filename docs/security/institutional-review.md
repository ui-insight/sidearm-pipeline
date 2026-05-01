# Institutional Security Review Checklist

This checklist helps IT security teams evaluate this application for deployment.

## 1. System Classification

- [ ] Data classification level determined (Public / Internal / Confidential / Restricted)
- [ ] Applicable regulations identified (FERPA, HIPAA, PCI-DSS, etc.)
- [ ] System owner and data steward designated

## 2. Authentication and Access Control

- [ ] Authentication requirements determined (public app, SSO, JWT, session, etc.)
- [ ] Authentication method reviewed and documented if access is restricted
- [ ] Password policy requirements verified
- [ ] Role-based or equivalent authorization model verified if used
- [ ] Session or token management reviewed if authentication is used
- [ ] Account lockout or rate limiting configured
  See [Rate Limiting Guidance](rate-limiting.md).

## 3. Data Protection

- [ ] Encryption at rest evaluated
- [ ] Encryption in transit (TLS) verified
- [ ] PII inventory reviewed
- [ ] Data retention policy defined
- [ ] Backup and recovery procedures documented

## 4. Network Architecture

- [ ] Network diagram reviewed
- [ ] Firewall rules appropriate
- [ ] API endpoints not directly exposed to internet (behind reverse proxy)
- [ ] Database not accessible from public network

## 5. Application Security

- [ ] Input validation on all endpoints (Pydantic schemas)
- [ ] Output encoding to prevent XSS
- [ ] CORS configuration reviewed
- [ ] File upload restrictions verified
- [ ] Error handling does not leak sensitive information

## 6. Dependency Management

- [ ] Dependency scanning enabled (pip-audit, npm audit)
- [ ] Automated vulnerability alerts configured (Dependabot)
- [ ] SBOM generation available
- [ ] No known critical vulnerabilities

## 7. Deployment Security

- [ ] Docker images use minimal base images
- [ ] No secrets in Docker images or source code
- [ ] Environment variables properly managed
- [ ] Production configuration reviewed (no debug mode)

## 8. Monitoring and Incident Response

- [ ] Application logging enabled
- [ ] Security event logging configured
- [ ] Incident response plan in place
- [ ] Contact information for security issues published (SECURITY.md)

## 9. Compliance

- [ ] FERPA compliance verified (if handling student data)
- [ ] HIPAA compliance verified (if handling health data)
- [ ] Section 508 / WCAG accessibility compliance planned
- [ ] State data privacy requirements reviewed

## 10. Source Code Review

- [ ] CLAUDE.md reviewed for AI agent constraints
- [ ] No hardcoded credentials in source
- [ ] Security-sensitive code paths reviewed
- [ ] Third-party library licenses compatible

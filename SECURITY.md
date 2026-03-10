# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in AURIX, please report it responsibly.

### How to Report

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Email the maintainers directly with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes

### What to Expect

- Acknowledgment within 48 hours
- Regular updates on the fix progress
- Credit in the security advisory (if desired)

### Scope

Security issues in:
- AURIX core code
- GitHub Actions integration
- Configuration handling
- AI prompt injection vulnerabilities

### Out of Scope

- Issues in dependencies (report to upstream)
- Issues requiring physical access
- Social engineering attacks

## Best Practices for Users

1. **API Keys**: Never commit API keys. Use GitHub Secrets.
2. **Permissions**: Use minimal GitHub token permissions
3. **Updates**: Keep AURIX updated to the latest version
4. **Configuration**: Review auto-approval settings carefully

Thank you for helping keep AURIX secure!

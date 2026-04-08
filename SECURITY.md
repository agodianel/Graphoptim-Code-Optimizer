# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in GraphOptim, please report it responsibly.

### How to Report

1. **Do NOT open a public issue** for security vulnerabilities
2. **Email**: Send a detailed report to the maintainers via the repository's private security advisory feature on GitHub
3. **GitHub Security Advisory**: Use the [Report a vulnerability](../../security/advisories/new) button on this repository

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Assessment**: Within 7 days
- **Fix/Release**: Within 30 days for confirmed vulnerabilities

### Security Considerations

GraphOptim processes and transforms Python source code. Key security areas:

- **Code execution**: GraphOptim uses `ast.parse()` and `ast.unparse()` — it does NOT execute arbitrary code. It only performs static analysis and AST transformations.
- **File system access**: `optimize_file(inplace=True)` modifies files on disk. Always creates `.bak` backups before modifying.
- **API keys**: Benchmark mode uses API keys loaded from environment variables. Keys are never logged, stored in files, or transmitted anywhere except to their respective API endpoints.
- **Dependencies**: We monitor dependencies for known vulnerabilities via GitHub Dependabot.

### Scope

The following are considered in-scope for security reports:

- Code injection via crafted Python input that causes unintended execution
- Path traversal in file operations (`analyze_file`, `optimize_file`)
- API key leakage through logs, error messages, or output
- Dependency vulnerabilities affecting GraphOptim users

The following are out-of-scope:

- Denial of service via extremely large input files (resource exhaustion)
- Issues in third-party dependencies that don't affect GraphOptim
- Social engineering attacks

## Disclosure Policy

We follow [coordinated disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure). Once a fix is released, we will:

1. Publish a GitHub Security Advisory
2. Release a patched version on PyPI
3. Credit the reporter (unless they prefer anonymity)

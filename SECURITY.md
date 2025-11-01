# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: **security@vllm-batch-server.dev** (or create a private security advisory on GitHub)

### What to Include

Please include the following information:

- **Type of vulnerability** (e.g., SQL injection, XSS, authentication bypass)
- **Full paths** of source file(s) related to the vulnerability
- **Location** of the affected source code (tag/branch/commit or direct URL)
- **Step-by-step instructions** to reproduce the issue
- **Proof-of-concept or exploit code** (if possible)
- **Impact** of the vulnerability
- **Suggested fix** (if you have one)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity
  - **Critical**: 1-7 days
  - **High**: 7-30 days
  - **Medium**: 30-90 days
  - **Low**: Best effort

### Disclosure Policy

- Security issues will be disclosed after a fix is available
- We will credit reporters in the security advisory (unless you prefer to remain anonymous)
- We follow coordinated disclosure practices

## Security Best Practices

### For Users

1. **Keep Updated**: Always use the latest version
2. **Secure Credentials**: Never commit `.env` files or API keys
3. **Network Security**: Run behind a firewall, use HTTPS in production
4. **Access Control**: Limit who can access the API server
5. **Monitor Logs**: Watch for suspicious activity

### For Developers

1. **Input Validation**: Validate all user inputs
2. **SQL Injection**: Use parameterized queries (SQLAlchemy ORM)
3. **Authentication**: Implement API key authentication for production
4. **Rate Limiting**: Prevent abuse with rate limits
5. **Dependency Updates**: Keep dependencies up to date

## Known Security Considerations

### 1. No Built-in Authentication

**Issue**: The default configuration has no authentication.

**Mitigation**:
- Set `API_KEY` in `.env` for production
- Use reverse proxy (nginx) with authentication
- Run behind VPN or firewall

### 2. File Upload Vulnerabilities

**Issue**: Users can upload arbitrary JSONL files.

**Mitigation**:
- File size limits enforced (100MB default)
- JSONL format validation
- Sandboxed file storage
- No code execution from uploaded files

### 3. Model Loading

**Issue**: Loading untrusted models could execute malicious code.

**Mitigation**:
- Only load models from trusted sources (HuggingFace)
- Use model registry to whitelist models
- Run worker in isolated environment

### 4. Database Access

**Issue**: Direct database access could leak sensitive data.

**Mitigation**:
- Use strong PostgreSQL passwords
- Limit database network access
- Use read-only credentials where possible
- Regular backups

### 5. GPU Resource Exhaustion

**Issue**: Malicious users could submit large batches to exhaust GPU.

**Mitigation**:
- Implement rate limiting
- Set maximum batch size
- Monitor GPU usage
- Implement job quotas

## Security Features

### Current

- ✅ **Input Validation**: Pydantic models validate all inputs
- ✅ **SQL Injection Protection**: SQLAlchemy ORM prevents SQL injection
- ✅ **File Size Limits**: Prevents DoS via large uploads
- ✅ **CORS Configuration**: Configurable CORS headers
- ✅ **Error Handling**: No sensitive data in error messages

### Planned

- [ ] **API Key Authentication**: Built-in API key support
- [ ] **Rate Limiting**: Per-IP and per-user rate limits
- [ ] **Audit Logging**: Track all API calls
- [ ] **Encryption**: Encrypt sensitive data at rest
- [ ] **HTTPS**: Built-in TLS support

## Vulnerability Disclosure

We will publish security advisories for:

- **Critical**: Remote code execution, authentication bypass
- **High**: SQL injection, XSS, privilege escalation
- **Medium**: Information disclosure, DoS
- **Low**: Minor issues with limited impact

## Security Updates

Subscribe to security updates:

- **GitHub Watch**: Watch this repository for security advisories
- **Release Notes**: Check release notes for security fixes
- **Mailing List**: (Coming soon)

## Compliance

This project aims to follow:

- **OWASP Top 10**: Web application security risks
- **CWE Top 25**: Most dangerous software weaknesses
- **NIST Guidelines**: Security best practices

## Contact

For security concerns, contact:

- **Email**: security@vllm-batch-server.dev
- **GitHub**: Create a private security advisory
- **PGP Key**: (Coming soon)

---

Thank you for helping keep vLLM Batch Server secure! 🔒


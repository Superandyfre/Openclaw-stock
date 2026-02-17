# Security Policy

## Supported Versions

We actively maintain and provide security updates for the latest version of OpenClaw.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Security Measures

### Dependency Security

All dependencies are regularly updated to patch known vulnerabilities:

- **aiohttp >= 3.13.3**: Patched zip bomb, DoS, and directory traversal vulnerabilities
- **torch >= 2.6.0**: Patched heap buffer overflow, use-after-free, and RCE vulnerabilities  
- **transformers >= 4.48.0**: Patched deserialization of untrusted data vulnerabilities
- **requests >= 2.32.3**: Latest security patches applied

### API Security

- **Rate Limiting**: All API clients implement rate limiting to prevent abuse
- **Input Validation**: All user inputs and API responses are validated
- **Secure Defaults**: Dry-run mode enabled by default (no real trading)

### Data Security

- **Environment Variables**: Sensitive data stored in `.env` (never committed)
- **No Hardcoded Secrets**: All API keys loaded from environment variables
- **In-Memory Cache**: Default caching doesn't persist sensitive data to disk

### Trading Security

- **Dry Run Mode**: Default mode simulates trading without real execution
- **Position Limits**: Multiple layers of risk management
- **Stop Loss**: Automatic stop-loss mechanisms
- **Daily Loss Limits**: Maximum daily loss protection

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please report it responsibly:

### How to Report

1. **DO NOT** open a public GitHub issue for security vulnerabilities
2. Email security concerns to: [Create a security email or use GitHub Security Advisories]
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 5 business days
- **Status Updates**: Every 7 days until resolved
- **Fix Timeline**: Critical issues within 7 days, others within 30 days

### Disclosure Policy

- We request 90 days before public disclosure
- We will credit you in release notes (unless you prefer anonymity)
- We may request your help in testing the fix

## Security Best Practices

### For Users

1. **Keep Dependencies Updated**
   ```bash
   pip install -r requirements.txt --upgrade
   pip install -r requirements-ai.txt --upgrade
   ```

2. **Secure Your Environment**
   ```bash
   chmod 600 .env  # Restrict .env file permissions
   ```

3. **Use Dry Run Mode**
   - Never enable real trading until thoroughly tested
   - Keep `DRY_RUN=true` in production until confident

4. **Monitor API Keys**
   - Rotate API keys regularly
   - Use read-only API keys when possible
   - Never commit API keys to version control

5. **Review Logs**
   ```bash
   tail -f logs/openclaw.log  # Monitor for suspicious activity
   ```

### For Developers

1. **Code Review**
   - All PRs require review before merging
   - Security-sensitive changes require two reviews

2. **Dependency Scanning**
   ```bash
   pip-audit  # Scan for known vulnerabilities
   ```

3. **Static Analysis**
   ```bash
   bandit -r openclaw/  # Security linter for Python
   ```

4. **Input Validation**
   - Validate all external inputs
   - Sanitize data before processing
   - Use type hints and validate types

5. **Error Handling**
   - Never expose sensitive data in error messages
   - Log security events appropriately
   - Use generic error messages for users

## Known Security Considerations

### AI Model Security

- **Model Loading**: Only load models from trusted sources (HuggingFace official)
- **Deserialization**: Be cautious with `torch.load()` - use `weights_only=True` when possible
- **Model Files**: Store model files securely, scan for tampering

### API Integration

- **Yahoo Finance**: Free tier, no authentication required (limited data exposure)
- **Upbit WebSocket**: Read-only access (no API keys for market data)
- **News APIs**: API keys required but only for read access

### Database Security

- **Redis**: In-memory only by default (no persistence)
- **PostgreSQL**: Not used by default (configure with caution)
- **Data Retention**: Clear sensitive data regularly

## Vulnerability History

### Patched Vulnerabilities

**2026-02-17**: Updated all dependencies to patch critical vulnerabilities
- aiohttp: 3.9.1 → 3.13.3 (CVE: zip bomb, DoS, directory traversal)
- torch: 2.1.2 → 2.6.0 (CVE: buffer overflow, UAF, RCE)
- transformers: 4.36.2 → 4.48.0 (CVE: deserialization attacks)

## Security Checklist

Before deploying OpenClaw:

- [ ] All dependencies updated to latest secure versions
- [ ] `.env` file secured with proper permissions (600)
- [ ] API keys rotated and validated
- [ ] Dry run mode tested extensively
- [ ] Risk limits configured appropriately
- [ ] Logs monitored for anomalies
- [ ] Backup and recovery procedures tested
- [ ] Network access restricted (firewall configured)
- [ ] Running with least privilege user account
- [ ] SSL/TLS enabled for all external connections

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python.readthedocs.io/en/latest/library/security_warnings.html)
- [GitHub Security Advisories](https://github.com/advisories)
- [CVE Database](https://cve.mitre.org/)

## Contact

For security concerns: Use GitHub Security Advisories or contact repository maintainers

---

**Note**: This is an educational project. Never use in production without thorough security review and testing.

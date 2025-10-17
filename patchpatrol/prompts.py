"""
Prompt templates for AI-powered commit review.

This module defines the core prompt templates that control how the AI model
interprets commit review tasks and ensures structured JSON outputs.
"""

# System prompt defining the AI reviewer persona and output format
SYSTEM_REVIEWER = """You are an automated code reviewer specialized in analyzing Git commits for quality, coherence, and best practices.

Your job is to assess both code changes and commit messages objectively and concisely.

You MUST return a single JSON object with this exact structure:

```json
{"score": float, "verdict": string, "comments": [string, ...]}
```

Where:
- `score`: A float between 0.0 and 1.0 reflecting overall quality (1.0 = excellent, 0.0 = needs major work)
- `verdict`: Either "approve" (if commit meets standards) or "revise" (if changes needed)
- `comments`: Array of actionable feedback and suggestions (provide only relevant insights based on what you observe)

Evaluation criteria:
- Code quality: structure, naming, safety, performance implications
- Test coverage: presence of tests for new functionality
- Documentation: inline comments, docstrings, README updates where needed
- Breaking changes: compatibility and migration considerations
- Commit message: clarity, conventional format, alignment with changes
- Security: potential vulnerabilities or sensitive data exposure

Guidelines for comments:
- Simple changes: 1-2 comments if there are only minor observations
- Complex changes: More comments if multiple areas need attention
- Perfect code: Empty array if no improvements needed
- Focus quality over quantity - only mention what's actually relevant

Only return the JSON object, with no additional text or explanations."""

# Template for reviewing staged code changes
USER_TEMPLATE_CHANGES = """Review the following staged Git diff for quality and coherence.

Files changed: {files}
Total lines modified: {loc}
Minimum quality threshold: {threshold}

<DIFF>
{diff}
</DIFF>

Analyze the changes for:
1. Code structure and organization
2. Naming conventions and clarity
3. Error handling and edge cases
4. Test coverage for new functionality
5. Documentation updates if needed
6. Breaking changes or API modifications
7. Security implications
8. Performance considerations

Return only the JSON response as specified in the system prompt."""

# Template for reviewing commit messages
USER_TEMPLATE_MESSAGE = """Review the following commit message for quality and adherence to conventions.

<MESSAGE>
{message}
</MESSAGE>

Evaluation criteria:
1. Clear, imperative mood ("Add feature" not "Added feature")
2. Conventional commit format (type: description)
3. Appropriate scope and breaking change indicators
4. Descriptive summary (50 chars or less for first line)
5. Detailed explanation if needed (wrapped at 72 chars)
6. Issue/ticket references where applicable
7. Clarity of intent and "why" behind the change

Minimum quality threshold: {threshold}

Return only the JSON response as specified in the system prompt."""

# Template for reviewing both changes and message together
USER_TEMPLATE_COMPLETE = """Review the following Git commit comprehensively, analyzing both the code changes and commit message.

Commit Message:
<MESSAGE>
{message}
</MESSAGE>

Files changed: {files}
Total lines modified: {loc}
Minimum quality threshold: {threshold}

Code Changes:
<DIFF>
{diff}
</DIFF>

Perform a holistic review considering:
1. Alignment between commit message and actual changes
2. Code quality and structure
3. Test coverage and documentation
4. Commit message clarity and conventions
5. Breaking changes properly documented
6. Security and performance implications

Return only the JSON response as specified in the system prompt."""

# Template for reviewing a historical commit by SHA
USER_TEMPLATE_COMMIT = """Review the following historical Git commit comprehensively, analyzing both the code changes and commit message.

Commit Information:
- SHA: {commit_sha}
- Author: {author_name} <{author_email}>
- Date: {author_date}
- Subject: {subject}

Commit Message:
<MESSAGE>
{message}
</MESSAGE>

Files changed: {files}
Total lines modified: {loc}
Minimum quality threshold: {threshold}

Code Changes:
<DIFF>
{diff}
</DIFF>

Perform a retrospective review considering:
1. Historical context and alignment between commit message and changes
2. Code quality standards that should have been applied
3. Potential issues or improvements that could have been made
4. Documentation and test coverage considerations
5. Breaking changes and their communication
6. Security implications and best practices
7. Overall impact on the codebase

Note: This is a historical analysis for learning and quality assessment purposes.

Return only the JSON response as specified in the system prompt."""

# Security-focused system prompt defining the AI security expert persona
SYSTEM_SECURITY_REVIEWER = """You are an expert cybersecurity code reviewer specialized in identifying security vulnerabilities, weaknesses, and risky patterns in code changes.

Your job is to perform comprehensive security analysis of Git commits with deep expertise in OWASP Top 10, Common Weakness Enumeration (CWE), and industry security standards.

You MUST return a single JSON object with this exact structure:

```json
{
  "score": float,
  "verdict": string,
  "severity": string,
  "comments": [string, ...],
  "security_issues": [
    {
      "category": string,
      "severity": string,
      "cwe": string,
      "description": string,
      "file": string,
      "line": integer,
      "remediation": string
    }
  ],
  "owasp_categories": [string, ...],
  "compliance_impact": [string, ...]
}
```

Where:
- `score`: Security risk score between 0.0 (secure) and 1.0 (critical vulnerabilities)
- `verdict`: "approve" (secure), "revise" (security concerns), or "security_risk" (vulnerabilities found)
- `severity`: Overall severity level: "CRITICAL", "HIGH", "MEDIUM", or "LOW"
- `comments`: Array of security-focused observations and recommendations
- `security_issues`: Array of specific security vulnerabilities found
- `owasp_categories`: OWASP Top 10 categories affected (e.g., "A03:2021-Injection", "A07:2021-Identification and Authentication Failures")
- `compliance_impact`: Compliance frameworks affected (e.g., "SOC2", "PCI-DSS", "GDPR", "HIPAA")

Security Categories to analyze:
1. **Secrets & Credentials** - API keys, passwords, tokens, certificates hardcoded
2. **Injection Vulnerabilities** - SQL injection, command injection, XSS, LDAP injection
3. **Authentication & Authorization** - Broken authentication, authorization bypasses, session management
4. **Cryptography** - Weak encryption, broken crypto, insecure randomness, key management
5. **Input Validation** - Unvalidated input, buffer overflows, deserialization attacks
6. **Data Exposure** - Sensitive data in logs, error messages, debug output
7. **Dependencies** - Known vulnerable dependencies, supply chain risks
8. **Infrastructure as Code** - Docker, Kubernetes, cloud misconfigurations
9. **Race Conditions** - TOCTOU, concurrent access issues
10. **Business Logic** - Privilege escalation, workflow bypasses

Severity Guidelines:
- **CRITICAL**: Remote code execution, authentication bypass, data breach potential
- **HIGH**: Privilege escalation, sensitive data exposure, significant security impact
- **MEDIUM**: Information disclosure, denial of service, moderate security impact
- **LOW**: Security hardening opportunities, best practice violations

Focus on actionable findings with clear remediation steps. Consider the full attack surface and potential exploitation scenarios.

Only return the JSON object, with no additional text or explanations."""

# Template for security review of staged code changes
USER_TEMPLATE_SECURITY_CHANGES = """Perform a comprehensive security analysis of the following staged Git diff.

Files changed: {files}
Total lines modified: {loc}
Security risk threshold: {threshold}

<DIFF>
{diff}
</DIFF>

Analyze the changes for security vulnerabilities and risks:

**Critical Security Areas:**
1. **Secrets Detection**: Hardcoded API keys, passwords, tokens, certificates, private keys
2. **Injection Vulnerabilities**: SQL injection, command injection, XSS, template injection, LDAP injection
3. **Authentication & Authorization**: Broken authentication logic, authorization bypasses, session security
4. **Cryptography Issues**: Weak algorithms, insecure randomness, key management, encryption flaws
5. **Input Validation**: Unvalidated user input, buffer overflows, deserialization vulnerabilities
6. **Data Protection**: Sensitive data exposure, inadequate sanitization, privacy violations
7. **Dependencies**: Vulnerable third-party libraries, supply chain security risks
8. **Infrastructure Security**: Container misconfigurations, cloud security, deployment vulnerabilities
9. **Business Logic Flaws**: Privilege escalation paths, workflow security gaps
10. **Error Handling**: Information disclosure through error messages, debug output

**OWASP Top 10 2021 Mapping:**
- A01:2021 – Broken Access Control
- A02:2021 – Cryptographic Failures
- A03:2021 – Injection
- A04:2021 – Insecure Design
- A05:2021 – Security Misconfiguration
- A06:2021 – Vulnerable and Outdated Components
- A07:2021 – Identification and Authentication Failures
- A08:2021 – Software and Data Integrity Failures
- A09:2021 – Security Logging and Monitoring Failures
- A10:2021 – Server-Side Request Forgery (SSRF)

**Compliance Considerations:**
Assess impact on SOC2, PCI-DSS, GDPR, HIPAA, ISO 27001, and other security frameworks.

Return only the JSON response as specified in the system prompt."""

# Template for security review of commit messages
USER_TEMPLATE_SECURITY_MESSAGE = """Analyze the following commit message for security-relevant information and potential security disclosure risks.

<MESSAGE>
{message}
</MESSAGE>

Security risk threshold: {threshold}

Evaluate the commit message for:

**Security Disclosure Risks:**
1. **Sensitive Information Exposure**: Passwords, API keys, internal URLs, system details
2. **Vulnerability Details**: Explicit security flaw descriptions that could aid attackers
3. **Infrastructure Disclosure**: Internal system architecture, network topology, technology stack details
4. **Security Bypass Information**: Methods to circumvent security controls
5. **Attack Vector Documentation**: Detailed exploitation techniques or vulnerability research

**Security Best Practices:**
1. **Responsible Disclosure**: Appropriate level of detail for security fixes
2. **Vague Security References**: Using general terms instead of specific vulnerability details
3. **Security Attribution**: Proper credit for security researchers without exposing details
4. **Compliance Documentation**: Appropriate documentation for audit trails

**Red Flags:**
- Hardcoded credentials or secrets in commit messages
- Detailed vulnerability descriptions
- Internal system information that could aid reconnaissance
- Security bypass techniques or exploitation methods
- Unredacted security test data or penetration testing results

Return only the JSON response as specified in the system prompt."""

# Template for comprehensive security review (changes + message)
USER_TEMPLATE_SECURITY_COMPLETE = """Perform a comprehensive security analysis of the following Git commit, analyzing both the code changes and commit message together.

Commit Message:
<MESSAGE>
{message}
</MESSAGE>

Files changed: {files}
Total lines modified: {loc}
Security risk threshold: {threshold}

Code Changes:
<DIFF>
{diff}
</DIFF>

Perform a holistic security assessment considering:

**Code Security Analysis:**
1. **Vulnerability Detection**: All OWASP Top 10 categories and CWE patterns
2. **Secrets & Credentials**: Hardcoded sensitive data detection
3. **Injection Attacks**: SQL, command, XSS, template, LDAP injection vulnerabilities
4. **Authentication Security**: Login mechanisms, session management, password handling
5. **Authorization Logic**: Access controls, privilege escalation, permission bypasses
6. **Cryptographic Security**: Encryption implementation, key management, randomness
7. **Input Validation**: Data sanitization, validation routines, boundary checks
8. **Output Encoding**: XSS prevention, data sanitization for different contexts
9. **Error Handling**: Information disclosure through error messages
10. **Dependencies**: Third-party library vulnerabilities and supply chain risks

**Message Security Review:**
1. **Information Disclosure**: Sensitive data exposure in commit messages
2. **Vulnerability Documentation**: Appropriate level of security fix documentation
3. **Compliance Requirements**: Audit trail and documentation standards

**Integration Analysis:**
1. **Consistency**: Alignment between security changes and their documentation
2. **Completeness**: Whether security fixes are comprehensive
3. **Communication**: Appropriate security communication practices
4. **Impact Assessment**: Full security impact of the combined changes

**Compliance Frameworks:**
Evaluate impact on SOC2, PCI-DSS, GDPR, HIPAA, ISO 27001, NIST Cybersecurity Framework, and other relevant security standards.

Return only the JSON response as specified in the system prompt."""

# Template for security review of historical commits
USER_TEMPLATE_SECURITY_COMMIT = """Perform a comprehensive security analysis of the following historical Git commit.

Commit Information:
- SHA: {commit_sha}
- Author: {author_name} <{author_email}>
- Date: {author_date}
- Subject: {subject}

Commit Message:
<MESSAGE>
{message}
</MESSAGE>

Files changed: {files}
Total lines modified: {loc}
Security risk threshold: {threshold}

Code Changes:
<DIFF>
{diff}
</DIFF>

Perform a retrospective security assessment considering:

**Historical Security Analysis:**
1. **Vulnerability Timeline**: Security issues that existed at commit time vs. current knowledge
2. **Attack Surface Evolution**: How this commit affected the overall attack surface
3. **Security Debt**: Technical security debt introduced or resolved
4. **Compliance History**: Historical compliance implications

**Modern Security Standards:**
Evaluate against current security standards and practices:
1. **OWASP Top 10 2021**: Current vulnerability categories
2. **CWE Top 25**: Most dangerous software weaknesses
3. **NIST Secure Development**: Current secure coding guidelines
4. **Zero Trust Principles**: Modern security architecture patterns

**Retrospective Risk Assessment:**
1. **Exploitability**: Historical and current exploitation potential
2. **Impact Analysis**: Business and technical impact of any security issues
3. **Detection Timeline**: How long security issues may have existed
4. **Remediation History**: Whether issues were subsequently addressed

**Learning Opportunities:**
1. **Security Patterns**: Good security practices demonstrated
2. **Anti-patterns**: Security mistakes to avoid in future development
3. **Process Improvements**: Security review process enhancements
4. **Training Needs**: Developer security education opportunities

Note: This is a retrospective security analysis for learning and improvement purposes.

Return only the JSON response as specified in the system prompt."""

# Configuration for prompt behavior
PROMPT_CONFIG = {
    "max_diff_length": 200000,  # Truncate diffs longer than this
    "max_message_length": 2000,  # Truncate messages longer than this
    "default_temperature": 0.2,  # Low temperature for consistency
    "default_max_tokens": 512,  # Sufficient for JSON response
}


def truncate_diff(
    diff_content: str, max_length: int = int(PROMPT_CONFIG["max_diff_length"])
) -> str:
    """
    Truncate diff content if it exceeds max_length to avoid token overflow.

    Args:
        diff_content: The git diff content
        max_length: Maximum allowed length

    Returns:
        Truncated diff with indication if truncation occurred
    """
    if len(diff_content) <= max_length:
        return diff_content

    truncated = diff_content[:max_length]
    # Try to cut at a line boundary
    last_newline = truncated.rfind("\n")
    if last_newline > max_length * 0.8:  # If we can find a reasonable cutoff
        truncated = truncated[:last_newline]

    return truncated + "\n\n[... DIFF TRUNCATED DUE TO LENGTH ...]"


def truncate_message(
    message: str, max_length: int = int(PROMPT_CONFIG["max_message_length"])
) -> str:
    """
    Truncate commit message if it exceeds max_length.

    Args:
        message: The commit message
        max_length: Maximum allowed length

    Returns:
        Truncated message with indication if truncation occurred
    """
    if len(message) <= max_length:
        return message

    return message[:max_length] + "\n\n[... MESSAGE TRUNCATED DUE TO LENGTH ...]"

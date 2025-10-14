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

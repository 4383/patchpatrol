"""
Parsing utilities for AI model outputs.

This module provides functions to extract, validate, and normalize
JSON responses from AI models for commit review.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SecurityIssue:
    """
    Structured representation of a security issue.

    Attributes:
        category: Security category (secrets, injection, authentication, etc.)
        severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
        cwe: Common Weakness Enumeration ID (e.g., CWE-798)
        description: Human-readable description of the issue
        file: File where the issue was found (optional)
        line: Line number where the issue was found (optional)
        remediation: Suggested fix or remediation steps
    """

    category: str
    severity: str
    description: str
    remediation: str
    cwe: str | None = None
    file: str | None = None
    line: int | None = None


@dataclass
class ReviewResult:
    """
    Structured representation of a commit review result.

    Attributes:
        score: Quality score between 0.0 and 1.0
        verdict: Either "approve", "revise", or "security_risk"
        comments: List of review comments
        raw_response: Original AI response
        parsing_errors: Any errors that occurred during parsing
        security_issues: List of security issues (for security mode)
        severity: Overall severity level (for security mode)
        owasp_categories: List of OWASP Top 10 categories affected
        compliance_impact: List of compliance frameworks affected
    """

    score: float
    verdict: str
    comments: list[str]
    raw_response: str
    parsing_errors: list[str] | None = None
    security_issues: list[SecurityIssue] | None = None
    severity: str | None = None
    owasp_categories: list[str] | None = None
    compliance_impact: list[str] | None = None

    def is_approved(self, threshold: float = 0.7) -> bool:
        """Check if the review meets the approval threshold."""
        return self.verdict == "approve" and self.score >= threshold

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "score": self.score,
            "verdict": self.verdict,
            "comments": self.comments,
            "raw_response": self.raw_response,
            "parsing_errors": self.parsing_errors,
        }

        # Add security-specific fields if present
        if self.security_issues is not None:
            result["security_issues"] = [
                {
                    "category": issue.category,
                    "severity": issue.severity,
                    "description": issue.description,
                    "remediation": issue.remediation,
                    "cwe": issue.cwe,
                    "file": issue.file,
                    "line": issue.line,
                }
                for issue in self.security_issues
            ]
        if self.severity is not None:
            result["severity"] = self.severity
        if self.owasp_categories is not None:
            result["owasp_categories"] = self.owasp_categories
        if self.compliance_impact is not None:
            result["compliance_impact"] = self.compliance_impact

        return result


class ParseError(Exception):
    """Exception raised when parsing AI responses fails."""

    pass


def extract_json_from_text(text: str) -> dict[str, Any] | None:
    """
    Extract JSON object from AI model response text.

    Handles cases where the model includes extra text around the JSON
    or uses markdown code blocks.

    Args:
        text: Raw text response from AI model

    Returns:
        Parsed JSON object or None if extraction fails
    """
    if not text or not text.strip():
        return None

    # Clean the text
    text = text.strip()

    # Pattern 1: Try to find JSON in code blocks
    code_block_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(code_block_pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1))  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    # Pattern 2: Try to find JSON object directly
    # Look for balanced braces
    json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
    matches = re.findall(json_pattern, text, re.DOTALL)

    for match in matches:
        try:
            return json.loads(match)  # type: ignore[no-any-return, arg-type]
        except json.JSONDecodeError:
            continue

    # Pattern 3: Try to extract from the beginning of the text
    if text.strip().startswith("{"):
        # Find the end of the JSON object
        brace_count = 0
        json_end = 0
        for i, char in enumerate(text):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    json_end = i + 1
                    break

        if json_end > 0:
            try:
                return json.loads(text[:json_end])  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass

    # Pattern 4: Try parsing the entire text
    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        pass

    return None


def validate_review_json(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate that JSON contains required review fields.

    Args:
        data: Parsed JSON data

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check required fields
    required_fields = ["score", "verdict", "comments"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        return False, errors

    # Validate score
    score = data["score"]
    if not isinstance(score, int | float):
        errors.append(f"Score must be a number, got {type(score).__name__}")
    elif not 0.0 <= score <= 1.0:
        errors.append(f"Score must be between 0.0 and 1.0, got {score}")

    # Validate verdict
    verdict = data["verdict"]
    if not isinstance(verdict, str):
        errors.append(f"Verdict must be a string, got {type(verdict).__name__}")
    elif verdict.lower() not in ["approve", "revise", "security_risk"]:
        errors.append(f"Verdict must be 'approve', 'revise', or 'security_risk', got '{verdict}'")

    # Validate comments
    comments = data["comments"]
    if not isinstance(comments, list):
        errors.append(f"Comments must be a list, got {type(comments).__name__}")
    else:
        for i, comment in enumerate(comments):
            if not isinstance(comment, str):
                errors.append(f"Comment {i} must be a string, got {type(comment).__name__}")

    # Validate security-specific fields if present
    if "security_issues" in data:
        security_issues = data["security_issues"]
        if not isinstance(security_issues, list):
            errors.append(f"Security issues must be a list, got {type(security_issues).__name__}")
        else:
            for i, issue in enumerate(security_issues):
                if not isinstance(issue, dict):
                    errors.append(f"Security issue {i} must be a dict, got {type(issue).__name__}")
                    continue

                # Check required security issue fields
                required_issue_fields = ["category", "severity", "description", "remediation"]
                for field in required_issue_fields:
                    if field not in issue:
                        errors.append(f"Security issue {i} missing required field: {field}")

    if "severity" in data:
        severity = data["severity"]
        if not isinstance(severity, str):
            errors.append(f"Severity must be a string, got {type(severity).__name__}")
        elif severity.upper() not in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            errors.append(f"Severity must be CRITICAL, HIGH, MEDIUM, or LOW, got '{severity}'")

    if "owasp_categories" in data:
        owasp_categories = data["owasp_categories"]
        if not isinstance(owasp_categories, list):
            errors.append(f"OWASP categories must be a list, got {type(owasp_categories).__name__}")

    if "compliance_impact" in data:
        compliance_impact = data["compliance_impact"]
        if not isinstance(compliance_impact, list):
            errors.append(
                f"Compliance impact must be a list, got {type(compliance_impact).__name__}"
            )

    return len(errors) == 0, errors


def normalize_review_json(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize and clean review JSON data.

    Args:
        data: Raw JSON data

    Returns:
        Normalized JSON data
    """
    normalized: dict[str, Any] = {}

    # Normalize score
    score = data.get("score", 0.0)
    if isinstance(score, str):
        try:
            score = float(score)
        except ValueError:
            score = 0.0
    normalized["score"] = max(0.0, min(1.0, float(score)))

    # Normalize verdict
    verdict = data.get("verdict", "revise").lower().strip()
    if verdict in ["approve", "approved", "accept", "pass"]:
        normalized["verdict"] = "approve"
    elif verdict in ["security_risk", "security-risk", "vulnerable", "insecure"]:
        normalized["verdict"] = "security_risk"
    else:
        normalized["verdict"] = "revise"

    # Normalize comments
    comments = data.get("comments", [])
    if isinstance(comments, str):
        # If comments is a string, split it or wrap it
        if comments.strip():
            normalized["comments"] = [comments.strip()]
        else:
            normalized["comments"] = []
    elif isinstance(comments, list):
        normalized["comments"] = [
            str(comment).strip() for comment in comments if str(comment).strip()
        ]
    else:
        normalized["comments"] = []

    # Limit number of comments
    if len(normalized["comments"]) > 10:
        normalized["comments"] = normalized["comments"][:10]

    # Normalize security-specific fields if present
    if "security_issues" in data:
        security_issues = data.get("security_issues", [])
        if isinstance(security_issues, list):
            normalized_issues = []
            for issue in security_issues:
                if isinstance(issue, dict):
                    normalized_issue = {
                        "category": str(issue.get("category", "unknown")).strip(),
                        "severity": str(issue.get("severity", "MEDIUM")).upper().strip(),
                        "description": str(issue.get("description", "")).strip(),
                        "remediation": str(issue.get("remediation", "")).strip(),
                        "cwe": str(issue.get("cwe", "")).strip() if issue.get("cwe") else None,
                        "file": str(issue.get("file", "")).strip() if issue.get("file") else None,
                        "line": issue.get("line") if isinstance(issue.get("line"), int) else None,
                    }
                    # Validate severity
                    if normalized_issue["severity"] not in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
                        normalized_issue["severity"] = "MEDIUM"
                    normalized_issues.append(normalized_issue)
            normalized["security_issues"] = normalized_issues[:20]  # Limit to 20 issues

    if "severity" in data:
        severity = str(data.get("severity", "MEDIUM")).upper().strip()
        if severity not in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            severity = "MEDIUM"
        normalized["severity"] = severity

    if "owasp_categories" in data:
        owasp_categories = data.get("owasp_categories", [])
        if isinstance(owasp_categories, list):
            normalized["owasp_categories"] = [
                str(cat).strip() for cat in owasp_categories if str(cat).strip()
            ][:10]

    if "compliance_impact" in data:
        compliance_impact = data.get("compliance_impact", [])
        if isinstance(compliance_impact, list):
            normalized["compliance_impact"] = [
                str(impact).strip() for impact in compliance_impact if str(impact).strip()
            ][:10]

    return normalized


def parse_json_response(response: str) -> ReviewResult:
    """
    Parse AI model response into a structured ReviewResult.

    Args:
        response: Raw response from AI model

    Returns:
        ReviewResult object with parsed data

    Raises:
        ParseError: If parsing fails completely
    """
    parsing_errors = []

    # Extract JSON from response
    json_data = extract_json_from_text(response)
    if json_data is None:
        parsing_errors.append("Could not extract JSON from response")
        # Return a default "revise" result
        return ReviewResult(
            score=0.0,
            verdict="revise",
            comments=["Failed to parse AI response - please review manually"],
            raw_response=response,
            parsing_errors=parsing_errors,
        )

    # Validate JSON structure
    is_valid, validation_errors = validate_review_json(json_data)
    if not is_valid:
        parsing_errors.extend(validation_errors)

    # Normalize the data
    try:
        normalized_data = normalize_review_json(json_data)
    except Exception as e:
        parsing_errors.append(f"Failed to normalize JSON: {e}")
        # Return a default "revise" result
        return ReviewResult(
            score=0.0,
            verdict="revise",
            comments=["Failed to process AI response - please review manually"],
            raw_response=response,
            parsing_errors=parsing_errors,
        )

    # Parse security issues if present
    security_issues = None
    if "security_issues" in normalized_data:
        security_issues = []
        for issue_data in normalized_data["security_issues"]:
            security_issues.append(
                SecurityIssue(
                    category=issue_data["category"],
                    severity=issue_data["severity"],
                    description=issue_data["description"],
                    remediation=issue_data["remediation"],
                    cwe=issue_data["cwe"],
                    file=issue_data["file"],
                    line=issue_data["line"],
                )
            )

    return ReviewResult(
        score=normalized_data["score"],
        verdict=normalized_data["verdict"],
        comments=normalized_data["comments"],
        raw_response=response,
        parsing_errors=parsing_errors if parsing_errors else None,
        security_issues=security_issues,
        severity=normalized_data.get("severity"),
        owasp_categories=normalized_data.get("owasp_categories"),
        compliance_impact=normalized_data.get("compliance_impact"),
    )


def validate_review_output(result: ReviewResult, threshold: float = 0.7) -> bool:
    """
    Validate that a review result meets quality standards.

    Args:
        result: ReviewResult to validate
        threshold: Minimum score threshold

    Returns:
        True if the review is valid and meets standards
    """
    # Check for complete parsing failures (JSON extraction failed)
    if result.parsing_errors and any(
        "Could not extract JSON" in error for error in result.parsing_errors
    ):
        logger.warning(f"Review has parsing errors: {result.parsing_errors}")
        return False

    # Log other parsing errors as warnings but don't automatically fail
    # These are validation errors that normalization might have fixed
    if result.parsing_errors:
        logger.warning(f"Review has parsing errors: {result.parsing_errors}")

    # Check score range
    if not 0.0 <= result.score <= 1.0:
        logger.error(f"Invalid score: {result.score}")
        return False

    # Check verdict
    if result.verdict not in ["approve", "revise", "security_risk"]:
        logger.error(f"Invalid verdict: {result.verdict}")
        return False

    # Check if comments are meaningful
    if not result.comments or all(len(comment.strip()) < 5 for comment in result.comments):
        logger.warning("Review comments are too short or missing")
        # Not a hard failure, but worth noting

    return True


def format_review_output(result: ReviewResult, use_colors: bool = True) -> str:
    """
    Format review result for human-readable output using Rich markup.

    Args:
        result: ReviewResult to format
        use_colors: Whether to use Rich color markup

    Returns:
        Formatted string with Rich markup
    """
    if not use_colors:
        # Plain text version
        status_icon = (
            "✓"
            if result.verdict == "approve"
            else ("🔒" if result.verdict == "security_risk" else "✗")
        )
        status_line = f"{status_icon} {result.verdict.upper().replace('_', ' ')}"
        score_line = f"Score: {result.score:.2f}"

        # Add severity for security reviews
        if result.severity:
            score_line += f" | Severity: {result.severity}"

        comments_section = ""
        if result.comments:
            comments_section = "\nComments:\n"
            for i, comment in enumerate(result.comments, 1):
                comments_section += f"  {i}. {comment}\n"

        # Security issues section
        security_section = ""
        if result.security_issues:
            security_section = "\nSecurity Issues:\n"
            for i, issue in enumerate(result.security_issues, 1):
                security_section += (
                    f"  {i}. [{issue.severity}] {issue.category}: {issue.description}\n"
                )
                if issue.cwe:
                    security_section += f"     CWE: {issue.cwe}\n"
                security_section += f"     Remediation: {issue.remediation}\n"

        # OWASP categories
        owasp_section = ""
        if result.owasp_categories:
            owasp_section = f"\nOWASP Categories: {', '.join(result.owasp_categories)}\n"

        # Compliance impact
        compliance_section = ""
        if result.compliance_impact:
            compliance_section = f"Compliance Impact: {', '.join(result.compliance_impact)}\n"

        errors_section = ""
        if result.parsing_errors:
            errors_section = "\nParsing Issues:\n"
            for error in result.parsing_errors:
                errors_section += f"  ⚠ {error}\n"

        return f"{status_line} | {score_line}{comments_section}{security_section}{owasp_section}{compliance_section}{errors_section}".rstrip()

    # Rich markup version
    if result.verdict == "approve":
        status_color = "green"
        status_icon = "✓"
    elif result.verdict == "security_risk":
        status_color = "red"
        status_icon = "🔒"
    else:
        status_color = "red"
        status_icon = "✗"

    status_line = f"[bold {status_color}]{status_icon} {result.verdict.upper().replace('_', ' ')}[/bold {status_color}]"

    # Score line with color based on score
    if result.score >= 0.8:
        score_color = "green"
    elif result.score >= 0.5:
        score_color = "yellow"
    else:
        score_color = "red"
    score_line = f"[bold]Score:[/bold] [{score_color}]{result.score:.2f}[/{score_color}]"

    # Add severity for security reviews
    if result.severity:
        severity_colors = {"CRITICAL": "red", "HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}
        severity_color = severity_colors.get(result.severity, "white")
        score_line += (
            f" | [bold]Severity:[/bold] [{severity_color}]{result.severity}[/{severity_color}]"
        )

    # Comments
    comments_section = ""
    if result.comments:
        comments_section = "\n[bold]Comments:[/bold]\n"
        for i, comment in enumerate(result.comments, 1):
            comments_section += f"  [blue]{i}.[/blue] {comment}\n"

    # Security issues section
    security_section = ""
    if result.security_issues:
        security_section = "\n[bold red]Security Issues:[/bold red]\n"
        for i, issue in enumerate(result.security_issues, 1):
            severity_colors = {"CRITICAL": "red", "HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}
            severity_color = severity_colors.get(issue.severity, "white")

            security_section += f"  [cyan]{i}.[/cyan] [[{severity_color}]{issue.severity}[/{severity_color}]] [bold]{issue.category}[/bold]: {issue.description}\n"
            if issue.cwe:
                security_section += f"     [dim]CWE: {issue.cwe}[/dim]\n"
            if issue.file:
                file_info = issue.file
                if issue.line:
                    file_info += f":{issue.line}"
                security_section += f"     [dim]Location: {file_info}[/dim]\n"
            security_section += f"     [green]Remediation:[/green] {issue.remediation}\n"

    # OWASP categories
    owasp_section = ""
    if result.owasp_categories:
        owasp_section = f"\n[bold]OWASP Categories:[/bold] [yellow]{', '.join(result.owasp_categories)}[/yellow]\n"

    # Compliance impact
    compliance_section = ""
    if result.compliance_impact:
        compliance_section = f"[bold]Compliance Impact:[/bold] [magenta]{', '.join(result.compliance_impact)}[/magenta]\n"

    # Parsing errors
    errors_section = ""
    if result.parsing_errors:
        errors_section = "\n[bold yellow]Parsing Issues:[/bold yellow]\n"
        for error in result.parsing_errors:
            errors_section += f"  [yellow]⚠[/yellow] {error}\n"

    return f"{status_line} | {score_line}{comments_section}{security_section}{owasp_section}{compliance_section}{errors_section}".rstrip()


# Helper function for common use case
def parse_and_validate(response: str, threshold: float = 0.7) -> tuple[ReviewResult, bool]:
    """
    Parse and validate AI response in one step.

    Args:
        response: Raw AI response
        threshold: Score threshold for approval

    Returns:
        Tuple of (ReviewResult, is_valid)
    """
    result = parse_json_response(response)
    is_valid = validate_review_output(result, threshold)
    return result, is_valid

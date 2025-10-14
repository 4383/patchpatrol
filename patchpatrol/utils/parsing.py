"""
Parsing utilities for AI model outputs.

This module provides functions to extract, validate, and normalize
JSON responses from AI models for commit review.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """
    Structured representation of a commit review result.

    Attributes:
        score: Quality score between 0.0 and 1.0
        verdict: Either "approve" or "revise"
        comments: List of review comments
        raw_response: Original AI response
        parsing_errors: Any errors that occurred during parsing
    """

    score: float
    verdict: str
    comments: list[str]
    raw_response: str
    parsing_errors: Optional[list[str]] = None

    def is_approved(self, threshold: float = 0.7) -> bool:
        """Check if the review meets the approval threshold."""
        return self.verdict == "approve" and self.score >= threshold

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "score": self.score,
            "verdict": self.verdict,
            "comments": self.comments,
            "raw_response": self.raw_response,
            "parsing_errors": self.parsing_errors,
        }


class ParseError(Exception):
    """Exception raised when parsing AI responses fails."""

    pass


def extract_json_from_text(text: str) -> Optional[dict[str, Any]]:
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
    if not isinstance(score, (int, float)):
        errors.append(f"Score must be a number, got {type(score).__name__}")
    elif not 0.0 <= score <= 1.0:
        errors.append(f"Score must be between 0.0 and 1.0, got {score}")

    # Validate verdict
    verdict = data["verdict"]
    if not isinstance(verdict, str):
        errors.append(f"Verdict must be a string, got {type(verdict).__name__}")
    elif verdict.lower() not in ["approve", "revise"]:
        errors.append(f"Verdict must be 'approve' or 'revise', got '{verdict}'")

    # Validate comments
    comments = data["comments"]
    if not isinstance(comments, list):
        errors.append(f"Comments must be a list, got {type(comments).__name__}")
    else:
        for i, comment in enumerate(comments):
            if not isinstance(comment, str):
                errors.append(f"Comment {i} must be a string, got {type(comment).__name__}")

    return len(errors) == 0, errors


def normalize_review_json(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize and clean review JSON data.

    Args:
        data: Raw JSON data

    Returns:
        Normalized JSON data
    """
    normalized = {}

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
        normalized["verdict"] = "approve"  # type: ignore[assignment]
    else:
        normalized["verdict"] = "revise"  # type: ignore[assignment]

    # Normalize comments
    comments = data.get("comments", [])
    if isinstance(comments, str):
        # If comments is a string, split it or wrap it
        if comments.strip():
            normalized["comments"] = [comments.strip()]  # type: ignore[assignment]
        else:
            normalized["comments"] = []  # type: ignore[assignment]
    elif isinstance(comments, list):
        normalized["comments"] = [  # type: ignore[assignment]
            str(comment).strip() for comment in comments if str(comment).strip()
        ]
    else:
        normalized["comments"] = []  # type: ignore[assignment]

    # Limit number of comments
    if len(normalized["comments"]) > 10:  # type: ignore[arg-type]
        normalized["comments"] = normalized["comments"][:10]  # type: ignore[index]

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

    return ReviewResult(
        score=normalized_data["score"],
        verdict=normalized_data["verdict"],
        comments=normalized_data["comments"],
        raw_response=response,
        parsing_errors=parsing_errors if parsing_errors else None,
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
    # Check for parsing errors
    if result.parsing_errors:
        logger.warning(f"Review has parsing errors: {result.parsing_errors}")
        return False

    # Check score range
    if not 0.0 <= result.score <= 1.0:
        logger.error(f"Invalid score: {result.score}")
        return False

    # Check verdict
    if result.verdict not in ["approve", "revise"]:
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
        status_line = f"{'✓' if result.verdict == 'approve' else '✗'} {result.verdict.upper()}"
        score_line = f"Score: {result.score:.2f}"

        comments_section = ""
        if result.comments:
            comments_section = "\nComments:\n"
            for i, comment in enumerate(result.comments, 1):
                comments_section += f"  {i}. {comment}\n"

        errors_section = ""
        if result.parsing_errors:
            errors_section = "\nParsing Issues:\n"
            for error in result.parsing_errors:
                errors_section += f"  ⚠ {error}\n"

        return f"{status_line} | {score_line}{comments_section}{errors_section}".rstrip()

    # Rich markup version
    status_color = "green" if result.verdict == "approve" else "red"
    status_line = f"[bold {status_color}]{'✓' if result.verdict == 'approve' else '✗'} {result.verdict.upper()}[/bold {status_color}]"

    # Score line with color based on score
    if result.score >= 0.8:
        score_color = "green"
    elif result.score >= 0.5:
        score_color = "yellow"
    else:
        score_color = "red"
    score_line = f"[bold]Score:[/bold] [{score_color}]{result.score:.2f}[/{score_color}]"

    # Comments
    comments_section = ""
    if result.comments:
        comments_section = "\n[bold]Comments:[/bold]\n"
        for i, comment in enumerate(result.comments, 1):
            comments_section += f"  [blue]{i}.[/blue] {comment}\n"

    # Parsing errors
    errors_section = ""
    if result.parsing_errors:
        errors_section = "\n[bold yellow]Parsing Issues:[/bold yellow]\n"
        for error in result.parsing_errors:
            errors_section += f"  [yellow]⚠[/yellow] {error}\n"

    return f"{status_line} | {score_line}{comments_section}{errors_section}".rstrip()


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

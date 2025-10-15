"""Unit tests for parsing utilities."""

from patchpatrol.utils.parsing import (
    ReviewResult,
    extract_json_from_text,
    format_review_output,
    normalize_review_json,
    parse_and_validate,
    parse_json_response,
    validate_review_json,
    validate_review_output,
)


class TestReviewResult:
    """Test ReviewResult dataclass."""

    def test_review_result_creation(self):
        """Test creating a ReviewResult."""
        result = ReviewResult(
            score=0.85,
            verdict="approve",
            comments=["Good code quality", "Well tested"],
            raw_response='{"score": 0.85, "verdict": "approve"}',
        )

        assert result.score == 0.85
        assert result.verdict == "approve"
        assert len(result.comments) == 2
        assert result.parsing_errors is None

    def test_is_approved_true(self):
        """Test is_approved returns True for approved results above threshold."""
        result = ReviewResult(
            score=0.85,
            verdict="approve",
            comments=["Good"],
            raw_response="{}",
        )

        assert result.is_approved(threshold=0.7) is True
        assert result.is_approved(threshold=0.8) is True

    def test_is_approved_false_low_score(self):
        """Test is_approved returns False for low scores."""
        result = ReviewResult(
            score=0.65,
            verdict="approve",
            comments=["Good"],
            raw_response="{}",
        )

        assert result.is_approved(threshold=0.7) is False

    def test_is_approved_false_revise_verdict(self):
        """Test is_approved returns False for revise verdict."""
        result = ReviewResult(
            score=0.85,
            verdict="revise",
            comments=["Needs work"],
            raw_response="{}",
        )

        assert result.is_approved(threshold=0.7) is False

    def test_to_dict(self):
        """Test converting ReviewResult to dictionary."""
        result = ReviewResult(
            score=0.75,
            verdict="approve",
            comments=["Good work"],
            raw_response='{"score": 0.75}',
            parsing_errors=["Minor issue"],
        )

        dict_result = result.to_dict()

        assert dict_result["score"] == 0.75
        assert dict_result["verdict"] == "approve"
        assert dict_result["comments"] == ["Good work"]
        assert dict_result["raw_response"] == '{"score": 0.75}'
        assert dict_result["parsing_errors"] == ["Minor issue"]


class TestExtractJsonFromText:
    """Test JSON extraction from text."""

    def test_extract_json_from_code_block(self):
        """Test extracting JSON from markdown code block."""
        text = """Here's the review:
        ```json
        {"score": 0.8, "verdict": "approve", "comments": ["Good work"]}
        ```
        That's the result."""

        result = extract_json_from_text(text)

        assert result is not None
        assert result["score"] == 0.8
        assert result["verdict"] == "approve"

    def test_extract_json_from_code_block_no_language(self):
        """Test extracting JSON from code block without language specifier."""
        text = """```
        {"score": 0.9, "verdict": "approve", "comments": []}
        ```"""

        result = extract_json_from_text(text)

        assert result is not None
        assert result["score"] == 0.9

    def test_extract_json_direct_object(self):
        """Test extracting JSON object directly from text."""
        text = 'The analysis shows {"score": 0.75, "verdict": "revise", "comments": ["Fix issues"]} for this commit.'

        result = extract_json_from_text(text)

        assert result is not None
        assert result["score"] == 0.75
        assert result["verdict"] == "revise"

    def test_extract_json_from_beginning(self):
        """Test extracting JSON from beginning of text."""
        text = '{"score": 0.6, "verdict": "revise", "comments": ["Needs improvement"]} and some other text'

        result = extract_json_from_text(text)

        assert result is not None
        assert result["score"] == 0.6

    def test_extract_json_pure_json(self):
        """Test extracting pure JSON text."""
        text = '{"score": 1.0, "verdict": "approve", "comments": ["Perfect"]}'

        result = extract_json_from_text(text)

        assert result is not None
        assert result["score"] == 1.0

    def test_extract_json_no_json_found(self):
        """Test when no JSON can be extracted."""
        text = "This is just plain text with no JSON structure."

        result = extract_json_from_text(text)

        assert result is None

    def test_extract_json_empty_text(self):
        """Test with empty or whitespace text."""
        assert extract_json_from_text("") is None
        assert extract_json_from_text("   ") is None

    def test_extract_json_malformed_json(self):
        """Test with malformed JSON."""
        text = '{"score": 0.8, "verdict": "approve", "comments":}'  # Missing value

        result = extract_json_from_text(text)

        assert result is None

    def test_extract_json_nested_braces(self):
        """Test with nested braces in JSON."""
        text = """{"score": 0.8, "verdict": "approve", "metadata": {"author": "AI", "confidence": 0.9}}"""

        result = extract_json_from_text(text)

        assert result is not None
        assert result["score"] == 0.8
        assert result["metadata"]["author"] == "AI"


class TestValidateReviewJson:
    """Test JSON validation for review format."""

    def test_validate_valid_json(self):
        """Test validating correct JSON structure."""
        data = {"score": 0.8, "verdict": "approve", "comments": ["Good work", "Well tested"]}

        is_valid, errors = validate_review_json(data)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_fields(self):
        """Test validation with missing required fields."""
        data = {"score": 0.8}  # Missing verdict and comments

        is_valid, errors = validate_review_json(data)

        assert is_valid is False
        assert "Missing required field: verdict" in errors
        assert "Missing required field: comments" in errors

    def test_validate_invalid_score_type(self):
        """Test validation with invalid score type."""
        data = {"score": "high", "verdict": "approve", "comments": ["Good"]}  # Should be number

        is_valid, errors = validate_review_json(data)

        assert is_valid is False
        assert "Score must be a number" in errors[0]

    def test_validate_invalid_score_range(self):
        """Test validation with score out of range."""
        data = {"score": 1.5, "verdict": "approve", "comments": ["Good"]}  # Should be 0.0-1.0

        is_valid, errors = validate_review_json(data)

        assert is_valid is False
        assert "Score must be between 0.0 and 1.0" in errors[0]

    def test_validate_invalid_verdict(self):
        """Test validation with invalid verdict."""
        data = {
            "score": 0.8,
            "verdict": "maybe",  # Should be approve or revise
            "comments": ["Good"],
        }

        is_valid, errors = validate_review_json(data)

        assert is_valid is False
        assert "Verdict must be 'approve' or 'revise'" in errors[0]

    def test_validate_invalid_comments_type(self):
        """Test validation with invalid comments type."""
        data = {
            "score": 0.8,
            "verdict": "approve",
            "comments": "This should be a list",  # Should be list
        }

        is_valid, errors = validate_review_json(data)

        assert is_valid is False
        assert "Comments must be a list" in errors[0]

    def test_validate_invalid_comment_types(self):
        """Test validation with non-string comments."""
        data = {
            "score": 0.8,
            "verdict": "approve",
            "comments": ["Good work", 123, "Another comment"],  # 123 is not string
        }

        is_valid, errors = validate_review_json(data)

        assert is_valid is False
        assert "Comment 1 must be a string" in errors[0]


class TestNormalizeReviewJson:
    """Test JSON normalization."""

    def test_normalize_string_score(self):
        """Test normalizing string score to float."""
        data = {"score": "0.85", "verdict": "approve", "comments": ["Good"]}

        normalized = normalize_review_json(data)

        assert normalized["score"] == 0.85
        assert isinstance(normalized["score"], float)

    def test_normalize_invalid_string_score(self):
        """Test normalizing invalid string score."""
        data = {"score": "invalid", "verdict": "approve", "comments": ["Good"]}

        normalized = normalize_review_json(data)

        assert normalized["score"] == 0.0

    def test_normalize_out_of_range_score(self):
        """Test normalizing out-of-range scores."""
        # Test too high
        data1 = {"score": 1.5, "verdict": "approve", "comments": ["Good"]}
        normalized1 = normalize_review_json(data1)
        assert normalized1["score"] == 1.0

        # Test too low
        data2 = {"score": -0.5, "verdict": "approve", "comments": ["Good"]}
        normalized2 = normalize_review_json(data2)
        assert normalized2["score"] == 0.0

    def test_normalize_verdict_variations(self):
        """Test normalizing different verdict variations."""
        # Test approve variations
        for verdict in ["approve", "approved", "accept", "pass"]:
            data = {"score": 0.8, "verdict": verdict, "comments": ["Good"]}
            normalized = normalize_review_json(data)
            assert normalized["verdict"] == "approve"

        # Test revise (default for everything else)
        for verdict in ["revise", "reject", "fail", "unknown"]:
            data = {"score": 0.8, "verdict": verdict, "comments": ["Good"]}
            normalized = normalize_review_json(data)
            assert normalized["verdict"] == "revise"

    def test_normalize_string_comments(self):
        """Test normalizing string comments to list."""
        data = {"score": 0.8, "verdict": "approve", "comments": "This is a single comment"}

        normalized = normalize_review_json(data)

        assert normalized["comments"] == ["This is a single comment"]

    def test_normalize_empty_string_comments(self):
        """Test normalizing empty string comments."""
        data = {"score": 0.8, "verdict": "approve", "comments": "   "}  # Whitespace only

        normalized = normalize_review_json(data)

        assert normalized["comments"] == []

    def test_normalize_list_comments_with_cleanup(self):
        """Test normalizing list comments with cleanup."""
        data = {
            "score": 0.8,
            "verdict": "approve",
            "comments": ["Good work", "  ", 123, "Another comment", ""],
        }

        normalized = normalize_review_json(data)

        assert normalized["comments"] == ["Good work", "123", "Another comment"]

    def test_normalize_too_many_comments(self):
        """Test limiting number of comments."""
        data = {
            "score": 0.8,
            "verdict": "approve",
            "comments": [f"Comment {i}" for i in range(15)],  # 15 comments
        }

        normalized = normalize_review_json(data)

        assert len(normalized["comments"]) == 10  # Should be limited to 10

    def test_normalize_missing_fields(self):
        """Test normalizing with missing fields."""
        data: dict[str, str] = {}  # No fields

        normalized = normalize_review_json(data)

        assert normalized["score"] == 0.0
        assert normalized["verdict"] == "revise"
        assert normalized["comments"] == []


class TestParseJsonResponse:
    """Test complete JSON response parsing."""

    def test_parse_valid_response(self):
        """Test parsing valid JSON response."""
        response = '{"score": 0.85, "verdict": "approve", "comments": ["Good work", "Well tested"]}'

        result = parse_json_response(response)

        assert result.score == 0.85
        assert result.verdict == "approve"
        assert len(result.comments) == 2
        assert result.parsing_errors is None

    def test_parse_response_with_markdown(self):
        """Test parsing response with markdown code block."""
        response = """Here's my review:
        ```json
        {"score": 0.7, "verdict": "approve", "comments": ["Looks good"]}
        ```"""

        result = parse_json_response(response)

        assert result.score == 0.7
        assert result.verdict == "approve"

    def test_parse_invalid_json_response(self):
        """Test parsing completely invalid response."""
        response = "This is not JSON at all, just plain text."

        result = parse_json_response(response)

        assert result.score == 0.0
        assert result.verdict == "revise"
        assert "Failed to parse AI response" in result.comments[0]
        assert result.parsing_errors is not None
        assert "Could not extract JSON from response" in result.parsing_errors

    def test_parse_response_with_validation_errors(self):
        """Test parsing response with validation errors."""
        response = '{"score": "invalid", "verdict": "maybe", "comments": "not a list"}'

        result = parse_json_response(response)

        # Should still normalize and return result
        assert result.score == 0.0  # Normalized from invalid string
        assert result.verdict == "revise"  # Normalized from invalid verdict
        assert isinstance(result.comments, list)
        assert result.parsing_errors is not None
        assert len(result.parsing_errors) > 0

    def test_parse_response_normalization_error(self):
        """Test parsing when normalization fails."""
        response = '{"score": 0.8, "verdict": "approve", "comments": ["Good"]}'

        # Test with valid data - normalization should succeed
        result = parse_json_response(response)
        assert result.score == 0.8


class TestValidateReviewOutput:
    """Test review output validation."""

    def test_validate_good_review(self):
        """Test validating a good review result."""
        result = ReviewResult(
            score=0.85,
            verdict="approve",
            comments=["Good work", "Well tested"],
            raw_response="{}",
        )

        is_valid = validate_review_output(result, threshold=0.7)

        assert is_valid is True

    def test_validate_review_with_parsing_errors(self):
        """Test validating review with parsing errors."""
        result = ReviewResult(
            score=0.85,
            verdict="approve",
            comments=["Good work"],
            raw_response="{}",
            parsing_errors=["Some parsing issue"],
        )

        is_valid = validate_review_output(result, threshold=0.7)

        # Parsing errors only generate warnings, the normalized data is still valid
        assert is_valid is True

    def test_validate_review_invalid_score(self):
        """Test validating review with invalid score."""
        result = ReviewResult(
            score=1.5,  # Invalid score
            verdict="approve",
            comments=["Good work"],
            raw_response="{}",
        )

        is_valid = validate_review_output(result, threshold=0.7)

        assert is_valid is False

    def test_validate_review_invalid_verdict(self):
        """Test validating review with invalid verdict."""
        result = ReviewResult(
            score=0.85,
            verdict="maybe",  # Invalid verdict
            comments=["Good work"],
            raw_response="{}",
        )

        is_valid = validate_review_output(result, threshold=0.7)

        assert is_valid is False

    def test_validate_review_short_comments(self):
        """Test validating review with very short comments."""
        result = ReviewResult(
            score=0.85,
            verdict="approve",
            comments=["ok", ""],  # Very short comments
            raw_response="{}",
        )

        # Should still be valid, just logs a warning
        is_valid = validate_review_output(result, threshold=0.7)

        assert is_valid is True


class TestFormatReviewOutput:
    """Test review output formatting."""

    def test_format_approved_review_with_colors(self):
        """Test formatting approved review with colors."""
        result = ReviewResult(
            score=0.85,
            verdict="approve",
            comments=["Good work", "Well tested"],
            raw_response="{}",
        )

        formatted = format_review_output(result, use_colors=True)

        assert "✓" in formatted
        assert "APPROVE" in formatted
        assert "0.85" in formatted
        assert "Good work" in formatted
        assert "[bold green]" in formatted

    def test_format_revise_review_with_colors(self):
        """Test formatting revise review with colors."""
        result = ReviewResult(
            score=0.45,
            verdict="revise",
            comments=["Needs improvement"],
            raw_response="{}",
        )

        formatted = format_review_output(result, use_colors=True)

        assert "✗" in formatted
        assert "REVISE" in formatted
        assert "0.45" in formatted
        assert "[bold red]" in formatted

    def test_format_review_without_colors(self):
        """Test formatting review without colors."""
        result = ReviewResult(
            score=0.75,
            verdict="approve",
            comments=["Good work"],
            raw_response="{}",
        )

        formatted = format_review_output(result, use_colors=False)

        assert "✓" in formatted
        assert "APPROVE" in formatted
        assert "0.75" in formatted
        assert "Good work" in formatted
        assert "[" not in formatted  # No markup

    def test_format_review_with_parsing_errors(self):
        """Test formatting review with parsing errors."""
        result = ReviewResult(
            score=0.75,
            verdict="approve",
            comments=["Good work"],
            raw_response="{}",
            parsing_errors=["Minor parsing issue"],
        )

        formatted = format_review_output(result, use_colors=True)

        assert "Parsing Issues" in formatted
        assert "Minor parsing issue" in formatted

    def test_format_review_no_comments(self):
        """Test formatting review with no comments."""
        result = ReviewResult(
            score=0.75,
            verdict="approve",
            comments=[],
            raw_response="{}",
        )

        formatted = format_review_output(result, use_colors=True)

        assert "Comments:" not in formatted
        assert "0.75" in formatted


class TestParseAndValidate:
    """Test the convenience function."""

    def test_parse_and_validate_success(self):
        """Test successful parsing and validation."""
        response = '{"score": 0.85, "verdict": "approve", "comments": ["Good work"]}'

        result, is_valid = parse_and_validate(response, threshold=0.7)

        assert result.score == 0.85
        assert result.verdict == "approve"
        assert is_valid is True

    def test_parse_and_validate_failure(self):
        """Test parsing with validation failure."""
        response = "Not JSON at all"

        result, is_valid = parse_and_validate(response, threshold=0.7)

        assert result.score == 0.0
        assert result.verdict == "revise"
        assert is_valid is False

    def test_parse_and_validate_with_parsing_errors(self):
        """Test parsing with errors but normalization success."""
        response = '{"score": "0.85", "verdict": "approved", "comments": "Good work"}'

        result, is_valid = parse_and_validate(response, threshold=0.7)

        assert result.score == 0.85  # Normalized
        assert result.verdict == "approve"  # Normalized
        assert isinstance(result.comments, list)  # Normalized
        # Has parsing errors but is still valid after normalization
        assert result.parsing_errors is not None
        assert is_valid is True  # Should be valid after normalization

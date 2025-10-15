# 🧠 Technical Specification

## Project: *AI Commit Review Hook System (Local & Offline)*

### 🎯 Purpose

Develop a **local, offline AI-powered commit review system**, named patchpatrol, integrated into the **Git pre-commit workflow**, distributed as a Python package compatible with the **pre-commit** framework.
The tool must analyze both:

* the **staged diff** (code quality, relevance, consistency),
* and the **commit message** (clarity, conventions, alignment with changes).

It must support **two interchangeable local inference backends**:

* **ONNX Runtime** for HF/Optimum-exported models,
* **llama.cpp** for quantized GGUF models.

The system must be **100% offline**, **configurable**, **extensible**, and **ready for distribution** via GitHub and PyPI.

---

## 🧱 1. System Architecture

### 1.1 High-Level Components

| Component                                                          | Responsibility                                               |
| ------------------------------------------------------------------ | ------------------------------------------------------------ |
| **CLI layer** (`cli.py`)                                           | Provides user interface (subcommands, options, exit codes).  |
| **Prompt layer** (`prompts.py`)                                    | Defines system and user prompt templates used for AI review. |
| **Backend layer** (`backends/`)                                    | Abstracts inference engines (ONNX / llama.cpp).              |
| **Git utilities** (`utils/git_utils.py`)                           | Extracts diffs, staged files, and commit messages.           |
| **Parsing layer** (`utils/parsing.py`)                             | Validates and normalizes AI outputs (JSON structure).        |
| **Config & metadata** (`.pre-commit-hooks.yaml`, `pyproject.toml`) | Integration with the pre-commit ecosystem.                   |

### 1.2 Directory Layout

```
ai-commit-review/
├─ ai_commit_review/
│  ├─ cli.py
│  ├─ prompts.py
│  ├─ backends/
│  │  ├─ onnx_backend.py
│  │  └─ llama_backend.py
│  ├─ utils/
│  │  ├─ git_utils.py
│  │  └─ parsing.py
│  └─ __init__.py
├─ pyproject.toml
├─ .pre-commit-hooks.yaml
├─ README.md
└─ LICENSE
```

---

## ⚙️ 2. Core Functionalities

### 2.1 Command-Line Interface

**Main commands:**

* `ai-commit-review review-changes`
  → Analyze the staged diff before committing.
* `ai-commit-review review-message`
  → Analyze the commit message on the `commit-msg` stage.

**Common global options:**

| Option                                         | Description                                               |                                  |
| ---------------------------------------------- | --------------------------------------------------------- | -------------------------------- |
| \`--backend \[onnx                             | llama]\`                                                  | Selects the inference engine.    |
| `--model <path>`                               | Path to the local model (ONNX folder or GGUF file).       |                                  |
| \`--device \<cpu                               | cuda>\`                                                   | Compute device for ONNX backend. |
| `--threshold <float>`                          | Minimal acceptance score (0–1).                           |                                  |
| `--max-new-tokens`, `--temperature`, `--top-p` | Generation parameters.                                    |                                  |
| `--soft/--hard`                                | Whether failure blocks the commit or only warns the user. |                                  |

Each hook in `.pre-commit-config.yaml` must be able to specify its own arguments.

---

## 🧩 3. Prompt Template Design (Critical Component)

### 3.1 Overview

Prompt templates are the **core control interface** between the commit context (diff/message) and the local language model.
They define *how the model interprets the task* and ensure **structured, reproducible JSON outputs**.

Each inference cycle uses:

1. A **System Prompt** — defines the reviewer persona and JSON output format.
2. A **User Prompt** — provides the diff or message context and quality criteria.

Both are defined as plain strings in `prompts.py` and must be easy to customize by advanced users.

---

### 3.2 System Prompt Specification

**File:** `prompts.py`
**Variable:** `SYSTEM_REVIEWER`

**Purpose:**
Establish a strict instruction set for the AI, defining its role, tone, and expected output schema.

**Requirements:**

* Must define the assistant as an *objective, concise reviewer*.
* Must constrain the output to a **single JSON object**.
* Must avoid reasoning outside of JSON.

**Reference content (conceptual, not code):**

> You are an automated code reviewer.
> Your job is to assess the quality and clarity of commits.
> You must return a **single JSON object** with the following structure:
>
> ```json
> {"score": float (0–1), "verdict": "approve|revise", "comments": [string, ...]}
> ```
>
> The `score` reflects overall quality.
> The `verdict` is `"approve"` if the commit meets standards, `"revise"` otherwise.
> The `comments` list contains brief, actionable suggestions.
>
> Review both:
>
> * Clarity and relevance of the commit message.
> * Coherence and quality of the diff (structure, tests, docs, naming, safety).
>
> Only return the JSON, with no additional text.

---

### 3.3 User Prompt — Diff Review (`USER_TEMPLATE_CHANGES`)

**Purpose:**
Provide the staged diff context to the model for technical analysis.

**Input fields:**

| Placeholder   | Description                                              |
| ------------- | -------------------------------------------------------- |
| `{diff}`      | Output of `git diff --cached`. (Truncated if necessary.) |
| `{files}`     | List of filenames affected.                              |
| `{loc}`       | Estimated lines of change (added/removed).               |
| `{threshold}` | Minimum acceptance threshold.                            |

**Expected behavior:**

* Model should evaluate the *coherence, quality, and potential risks* in the code changes.
* Output should prioritize: code safety, tests, documentation, breaking changes, naming conventions, and clarity.

**Conceptual content:**

> Review the following staged Git diff for quality and coherence.
> Files changed: `{files}`
> Total lines modified: `{loc}`
> Minimum quality threshold: `{threshold}`
>
> `<DIFF>`
> {diff}
> `</DIFF>`
>
> Analyze risks, test coverage, and documentation consistency.
> Return only the JSON described in the system prompt.

---

### 3.4 User Prompt — Message Review (`USER_TEMPLATE_MESSAGE`)

**Purpose:**
Evaluate the commit message for clarity, conventions, and intent.

**Input fields:**

| Placeholder   | Description               |
| ------------- | ------------------------- |
| `{message}`   | The raw commit message.   |
| `{threshold}` | Target quality threshold. |

**Expected behavior:**

* The model must check message structure (e.g., Conventional Commits).
* Ensure imperative mood, clear “why/what”, and references if applicable.

**Conceptual content:**

> Review the following commit message for quality and adherence to conventions:
>
> `<MESSAGE>`
> {message}
> `</MESSAGE>`
>
> Criteria: clarity, intent, conventional structure, relevance to the code diff, presence of issue references.
> Minimum quality threshold: `{threshold}`.
>
> Return only the JSON described in the system prompt.

---

### 3.5 Prompt Behavior Rules

* **Truncation:** Diff content must be truncated above 200,000 characters to avoid overflow.
* **Determinism:** Temperature default should be low (`0.2`) to ensure repeatability.
* **JSON focus:** The agent must always ensure that parsing errors (extra text) are handled gracefully.
* **Multi-backend consistency:** The same prompt templates must work identically with ONNX and llama.cpp backends.
* **Customizability:** Advanced users should be able to override the templates via environment variables or config.

---

## 🧠 4. Backend Architecture

### 4.1 Common Interface

Each backend must implement:

```
generate_json(system_prompt: str, user_prompt: str) -> str
```

* Input: textual prompts.
* Output: raw model response (string containing JSON).
* The CLI layer handles JSON extraction and validation.

### 4.2 ONNX Runtime Backend

* Loads models exported using **Optimum + Transformers**.
* Providers: `CPUExecutionProvider` or `CUDAExecutionProvider`.
* Dependencies: `optimum[onnxruntime]`, `transformers`.
* Supports configurable parameters: `temperature`, `top_p`, `max_new_tokens`.

### 4.3 llama.cpp Backend

* Loads quantized `.gguf` models locally (no server, no internet).
* Uses `create_chat_completion()` interface.
* Dependencies: `llama-cpp-python`.
* Parameters: `n_ctx`, `temperature`, `top_p`, `max_tokens`.

### 4.4 Extensibility

The backend interface should allow future extensions:

* `ollama` (via HTTP or local socket)
* `mlc-llm` or `vLLM`
* Potential model auto-detection by file type (`.gguf`, `.onnx`, `.bin`).

---

## 🧰 5. Git Integration & Workflow

### 5.1 Hooks

Two hooks are declared in `.pre-commit-hooks.yaml`:

| Hook                | Stage        | Function                     |
| ------------------- | ------------ | ---------------------------- |
| `ai-review-changes` | `pre-commit` | Analyze staged diffs.        |
| `ai-review-message` | `commit-msg` | Analyze commit message text. |

### 5.2 User Integration Example

```yaml
repos:
- repo: https://github.com/example/ai-commit-review
  rev: v0.1.0
  hooks:
    - id: ai-review-changes
      args: [--backend=llama, --model=./models/granite.gguf, --soft]
    - id: ai-review-message
      args: [--backend=onnx, --model=./models/gpt-oss-onnx, --threshold=0.75]
```

### 5.3 Exit Behavior

| Mode     | Behavior                                                   |
| -------- | ---------------------------------------------------------- |
| **Soft** | Displays warnings, does not block commit.                  |
| **Hard** | Fails the hook if score < threshold or verdict = "revise". |

---

## 📦 6. Packaging & Distribution

### 6.1 Packaging Requirements

* Python ≥ 3.10
* Dependencies:

  * Core: `click`, `rich`, `gitpython`
  * Optional extras:

    * `[onnx]` → `optimum[onnxruntime] transformers`
    * `[llama]` → `llama-cpp-python`
* Distributed via:

  * PyPI (`pip install ai-commit-review[llama]`)
  * GitHub releases (referenced in pre-commit YAML)

### 6.2 Configuration

* Include version in `pyproject.toml`.
* Use semantic versioning (`MAJOR.MINOR.PATCH`).
* Ensure `rev` tag consistency with GitHub release.

---

## 🔒 7. Technical Constraints

| Requirement           | Description                                                                             |
| --------------------- | --------------------------------------------------------------------------------------- |
| **Offline operation** | No network calls; all inference is local.                                               |
| **Security**          | Must never send diffs, messages, or data externally.                                    |
| **Performance**       | Inference must complete within \~5 seconds for medium diffs (<500 LOC).                 |
| **Compatibility**     | Linux, macOS, Windows.                                                                  |
| **Extensibility**     | New backends must be addable via the same interface.                                    |
| **Failure safety**    | Fallbacks and graceful degradation when model is missing, misconfigured, or JSON fails. |

---

## 🧪 8. Validation Criteria

1. ✅ Both ONNX and llama.cpp backends work interchangeably.
2. ✅ The CLI executes automatically during `git commit` operations.
3. ✅ 100% offline operation — no API calls.
4. ✅ Output is structured, colored, and human-readable.
5. ✅ Soft/hard modes behave correctly.
6. ✅ The package integrates seamlessly with pre-commit.
7. ✅ All prompt templates produce valid JSON consistently.
8. ✅ Documentation and usage examples are provided in README.

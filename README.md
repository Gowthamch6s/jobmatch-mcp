# JobMatch MCP

An [MCP](https://modelcontextprotocol.io) server that exposes an active job search as agent-callable tools: search live postings, score a resume against a specific posting, and track applications through their pipeline. Point Claude Desktop, Cursor, or any other MCP host at it and it can search jobs, judge fit, and log outcomes for you, without a dedicated frontend.

Built as a companion to [AI Career Copilot](#) (an agentic RAG job-matching system) and [AgentFlow Studio](#) (a self-correcting LangGraph agent) — this project's job is specifically to prove out **MCP server authorship**: schema-driven tool design, server-side auth, structured error handling, and observability, as a distinct engineering skill from agent orchestration or RAG.

## Why this exists

Job search tools live inside someone else's chat window or someone else's webapp. This puts job search, resume-fit scoring, and application tracking behind three narrow tools any MCP-compatible agent can call directly — including inside your own coding assistant, where you're already spending your day.

## Tools

| Tool | Purpose | Key inputs |
|---|---|---|
| `search_jobs` | Live job postings by title/keyword + location | `query` (required), `location`, `max_results` (1-20) |
| `score_resume_match` | 0-100 fit score of a resume against a posting | `resume_text`, `job_description` (both required) |
| `track_application` | Create or update a tracked application | `job_title`, `company`, `status` enum, optional `application_id` to update |
| `list_applications` | List tracked applications, optionally by status | `status` (optional filter) |

Every tool's full input/output contract — including every field, type, and default — lives in its docstring in [`src/jobmatch_mcp/server.py`](src/jobmatch_mcp/server.py), which is also what the MCP host shows the calling model. Nothing here is undocumented.

## Design choices (and why they're the point of this project)

**Schema-driven tools, not one mega-tool.** Each tool has one responsibility, a `Literal` enum for `status` rather than a free-text string, explicit required/optional fields, and worked examples in its docstring. This is what a JSON-Schema-first tool-use hiring bar is actually checking for — see the docstrings, not just the type hints.

**Auth never touches the model.** `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` are read once, server-side, in [`config.py`](src/jobmatch_mcp/config.py). They never appear in a tool's input schema, output, or log line (see `redact_params` in [`logging_utils.py`](src/jobmatch_mcp/logging_utils.py)). A calling model can request a search; it can never see, forward, or leak a credential.

**Structured errors, not stack traces.** Every *expected* failure mode is a documented [`JobMatchError`](src/jobmatch_mcp/errors.py) subclass returned as `{"ok": false, "error": {"code", "message", "retryable"}}` instead of a raw exception — see the error catalog below. A calling agent can branch on `code` and `retryable` without burning tokens parsing a traceback. Genuinely unexpected exceptions are left to propagate to FastMCP's own error handling, because those are bugs, not domain outcomes.

**Runs with zero credentials.** If `ADZUNA_APP_ID`/`ADZUNA_APP_KEY` aren't set, `search_jobs` automatically falls back to a deterministic mock dataset (`source: "mock"` on every listing) instead of failing. The server, its test suite, and its eval harness are all fully runnable — including in CI, with no secrets configured.

**Read-before-write.** `track_application` only ever inserts a brand-new row or updates a row the caller identified by `application_id`. There's no bulk/implicit mutation path.

**Observable by default.** Every tool call emits one structured JSON log line — tool name, latency in ms, outcome, redacted params — via [`log_tool_call`](src/jobmatch_mcp/logging_utils.py). No log line ever contains a credential or full resume text.

### Error catalog

| Code | Retryable | Meaning |
|---|---|---|
| `INVALID_QUERY` | No | Caller-side input failed validation (empty string, out-of-range value, bad enum) |
| `NO_RESULTS_FOUND` | No | Search/lookup succeeded but matched nothing |
| `RATE_LIMITED` | Yes | Upstream (Adzuna) rejected the request for rate limiting |
| `UPSTREAM_UNAVAILABLE` | Yes | Upstream unreachable or returned a 5xx |
| `APPLICATION_NOT_FOUND` | No | `track_application` referenced an `application_id` that doesn't exist |

## Architecture

```
MCP host (Claude Desktop / Cursor / etc.)
        │  stdio (JSON-RPC)
        ▼
  server.py  ── registers 4 tools on a FastMCP instance
        │
        ├─ adzuna_client.py  ── live Adzuna call, or deterministic mock fallback
        ├─ matching.py        ── dependency-light TF-IDF-style resume/job scorer
        ├─ storage.py          ── SQLite-backed application tracker (read-before-write)
        ├─ errors.py            ── JobMatchError catalog → structured {ok, error} shape
        └─ logging_utils.py      ── one structured JSON log line per call, with redaction
```

## Setup

```bash
git clone <this repo>
cd jobmatch-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env   # optional -- server runs fine with these blank (mock mode)
```

Run it directly over stdio:

```bash
jobmatch-mcp
```

Run the test suite and eval harness:

```bash
pytest -v
python evals/run_evals.py
```

Build and run in Docker:

```bash
docker build -t jobmatch-mcp .
docker run -i --rm -e ADZUNA_APP_ID=... -e ADZUNA_APP_KEY=... -v jobmatch-data:/data jobmatch-mcp
```

### Connecting to Claude Desktop / Cursor

Add to your MCP client's config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "jobmatch": {
      "command": "jobmatch-mcp",
      "env": {
        "ADZUNA_APP_ID": "your-app-id",
        "ADZUNA_APP_KEY": "your-app-key",
        "JOBMATCH_DB_PATH": "/absolute/path/to/jobmatch.db"
      }
    }
  }
}
```

Omit the `ADZUNA_*` keys entirely to run in mock mode.

## Testing

21 tests across four modules (`tests/`), covering every tool's happy path and every documented error code — including the mock-mode fallback, invalid input, not-found, and status-round-trip cases. All tests use an isolated throwaway SQLite file per test and run fully offline.

```
21 passed in ~1s
```

## Evals

`evals/run_evals.py` scores a fixed set of resume/job-description pairs against expected score bounds and expected relative rankings (e.g. a resume listing the exact stack in the posting must outscore an unrelated resume) — the same reproducible-eval pattern used in AI Career Copilot, applied here to the matching function specifically.

```
6/6 passed (100.0%)
```

## Roadmap / what a v2 would add

- Streamable HTTP transport alongside stdio, for multi-host use beyond a single local MCP client
- Swap `matching.py`'s TF-IDF scorer for an embedding-based one behind the same `score_match(resume_text, job_description)` signature
- Cover letter drafting tool, grounded in a tracked application's `notes` + the matched job description

## License

MIT

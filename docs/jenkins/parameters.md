# Jenkins parameters — consolidation and recommendations

This document recommends a consolidated set of Jenkins job parameters and environment variables to expose for the ingenialink-python CI pipeline. The aim is to make runs configurable (timeouts, retries, artifact retention), keep behavior reproducible, and integrate cleanly with `TEST_SESSIONS.setAttributeInCascade`.

## Goals

- Keep common knobs on the job parameters so maintainers can tune runs without editing the Jenkinsfile.
- Provide sane defaults for day-to-day runs while allowing long-running/CI runs to increase timeouts and retries.
- Make it easy to map parameters into `TestSession` attributes and environment variables.

## Recommended parameters

- `PYTHON_VERSIONS` (choice) — default: `MIN`
  - Options: `MIN`, `MAX`, `MIN_MAX`, `All`
  - Controls `TEST_SESSIONS.runPythonVersions` as currently implemented.

- `TEST_STAGE_PATTERN` (string) — default: `.*`
  - Regex to select which test stages/substages to run (existing `run_test_stages`).

- `WIRESHARK_LOGGING` (boolean) — default: `false`
  - Maps to `TEST_SESSIONS.useWiresharkLogging`.

- `WIRESHARK_SCOPE` (choice) — default: `session`
  - Values: `function`, `module`, `session` → maps to `TEST_SESSIONS.wiresharkScope`.

- `START_WIRESHARK_TIMEOUT_S` (string/number) — default: `10`
  - Maps to `TEST_SESSIONS.startWiresharkTimeoutS`.

- `TEST_TIMEOUT_MINUTES` (number) — default: `60`
  - Pipeline timeout for a test session (use to configure `pipeline.timeout` wrappers).

- `RETRY_BUILD_COUNT` (number) — default: `0`
  - Re-run build steps on transient failures. Should be used with care; add upper cap in Jenkinsfile.

- `TEST_RETRY_COUNT` (number) — default: `0`
  - Number of times to re-run failing pytest runs for flakiness handling. Implement by wrapping `pytest` invocation with a retry loop.

- `ARTIFACT_RETENTION_DAYS` (number) — default: `14`
  - How long artifacts (wheels, docs, coverage XML) should be kept by the publisher step (if supported by storage plugin).

- `CLEAN_WORKSPACE_BEFORE` (boolean) — default: `false`
  - When true, run a workspace clean before build/test stages to ensure reproducibility.

- `VENV_WORKING_FOLDER` (string) — default: (kept per-node in Jenkinsfile)
  - Allow override of working folder for running in different agents.

- `FORCE_PARALLEL_PYTHONS` (boolean) — default: `false`
  - When true, expand per-python builds/tests into parallel child stages.

## How to wire into `TestSession` / Jenkinsfile

- Use `params` mapping in the `Set env` stage to call

```groovy
TEST_SESSIONS.setAttributeInCascade(
  runPythonVersions: computeFromParam(params.PYTHON_VERSIONS),
  useWiresharkLogging: params.WIRESHARK_LOGGING,
  wiresharkScope: params.WIRESHARK_SCOPE,
  startWiresharkTimeoutS: params.START_WIRESHARK_TIMEOUT_S,
  jobName: "${env.JOB_NAME}-#${env.BUILD_NUMBER}"
)
```

- Use `TEST_TIMEOUT_MINUTES` to configure `pipeline.timeout(time: params.TEST_TIMEOUT_MINUTES, unit: 'MINUTES')` around `runTestSession`.
- Use `TEST_RETRY_COUNT` to implement a simple retry wrapper around the pytest invocation inside `PyTestManager`.

## Jenkins parameter snippets

Example `parameters` block to add to the Jenkinsfile:

```groovy
parameters {
  choice(name: 'PYTHON_VERSIONS', choices: ['MIN','MAX','MIN_MAX','All'], default: 'MIN')
  string(name: 'TEST_STAGE_PATTERN', defaultValue: '.*', description: 'Regex for test stages to run')
  booleanParam(name: 'WIRESHARK_LOGGING', defaultValue: false)
  choice(name: 'WIRESHARK_SCOPE', choices: ['function','module','session'], defaultValue: 'session')
  string(name: 'START_WIRESHARK_TIMEOUT_S', defaultValue: '10')
  string(name: 'VENV_WORKING_FOLDER', defaultValue: '', description: 'Optional override for working folder')
  booleanParam(name: 'CLEAN_WORKSPACE_BEFORE', defaultValue: false)
  string(name: 'TEST_TIMEOUT_MINUTES', defaultValue: '60')
  string(name: 'TEST_RETRY_COUNT', defaultValue: '0')
  string(name: 'RETRY_BUILD_COUNT', defaultValue: '0')
  string(name: 'ARTIFACT_RETENTION_DAYS', defaultValue: '14')
}
```

## Implementation notes

- Validation: convert numeric params to ints and validate ranges (e.g. timeouts > 0, retry counts within safe limits) before applying to `TestSession`.
- Migration: keep current param names (`run_test_stages`, `PYTHON_VERSIONS`) for backward compatibility; add new params as optional.
- Safe defaults: avoid aggressive retries by default (set to 0); increase in scheduled nightly pipelines only.
- Parallel expansion: if `FORCE_PARALLEL_PYTHONS` is enabled, dynamically generate parallel stages per Python version instead of iterating serially with `venvManager.forPythons`.

## Example: converting `PYTHON_VERSIONS` to `runPythonVersions`

Provide a small helper in the Jenkinsfile:

```groovy
String[] pythonChoicesToSet(String choice) {
  switch(choice) {
    case 'MIN': return [PYTHON_VERSION_MIN]
    case 'MAX': return [PYTHON_VERSION_MAX]
    case 'MIN_MAX': return [PYTHON_VERSION_MIN, PYTHON_VERSION_MAX]
    case 'All': return ALL_PYTHON_VERSIONS as String[]
    default: return [PYTHON_VERSION_MIN]
  }
}

TEST_SESSIONS.setAttributeInCascade(runPythonVersions: pythonChoicesToSet(params.PYTHON_VERSIONS) as Set)
```

## Checklist for adoption

- [ ] Add parameters to `parameters` block and update `Set env` stage to map them to `TEST_SESSIONS`.
- [ ] Add validation and safe-range clamping for numeric params.
- [ ] Add small documentation in README or job description explaining new knobs.
- [ ] Consider a follow-up to expose `ARTIFACT_RETENTION_DAYS` to the artifact storage/publisher step.

---

If you'd like, I can:

- Implement the parameter block and mapping in `Jenkinsfile` now, or
- Add a small helper to generate parallel per-python stages when `FORCE_PARALLEL_PYTHONS` is true.

## Consolidated proposals (all areas)

Below is a consolidated list of the proposals discussed during the review. They are grouped by ownership (TestSession, PyTestManager, VEnvManager, Jenkinsfile/CI, and cross-cutting). Use this as a short roadmap when adopting the parameter consolidation.

Priority: High / Medium / Low shown for quick triage.

- Cross-platform venv creation (High) — make `VEnvManager.createVirtualEnvironment` platform-aware: use `py -3.x` on Windows, `python3.x` or `python${version}` on Unix; ensure pip is available (remove `--without-pip` or bootstrap via `ensurepip`). (Owner: `VEnvManager`)
- Idempotent setup & workspace isolation (High) — ensure venv creation, copying, and installs are idempotent and safe for repeated runs; prefer `VENV_WORKING_FOLDER` for isolated operations. (Owner: `VEnvManager` / Jenkinsfile)
- Error handling & retry strategy (High) — wire `TEST_RETRY_COUNT`/`RETRY_BUILD_COUNT` into `PyTestManager` and build stages; fail fast for deterministic failures, retry flaky steps. (Owner: `PyTestManager` / Jenkinsfile)
- Reduce duplication (Medium) — extract repeated `unstash`/`stash` loops and other patterns into small helpers or `cicd-lib` library functions. (Owner: Jenkinsfile / cicd-lib)
- Coverage merging robustness (Medium) — make `stashCoverageFile` more defensive: handle missing `.coverage`, avoid renaming conflicts, validate `coverage_files` before passing to combine. (Owner: `PyTestManager`)
- Logging & diagnostics (Medium) — replace prints with structured `echo`/`logging`, add `pytest_sessionfinish` summary and `caplog`-friendly hooks; integrate `recordIssues` / `recordTestResults` where appropriate. (Owner: Jenkinsfile / PyTestManager)
- Parallelization (Medium) — optionally expand per-Python runs into parallel stages when `FORCE_PARALLEL_PYTHONS` is enabled to reduce wall time. (Owner: Jenkinsfile)
- Stash/unstash strategy & artifact retention (Medium) — consider compressing artifacts before stashing, or publish to an artifact store (ACR/S3) for large files; honor `ARTIFACT_RETENTION_DAYS`. (Owner: Jenkinsfile / publisher)
- Move heavy logic to shared library (Low) — migrate `VEnvManager`, `PyTestManager`, and `TestSession` into `cicd-lib` for reusability and to keep `Jenkinsfile` concise. (Owner: cicd-lib)
- Windows tooling checks (Low) — validate existence of external tools (7z, npcap) in images and fail early with actionable messages. (Owner: Jenkinsfile / images)
- Type hints & docs (Low) — keep inline docs (done) and optionally provide a small JSON schema or README for config usage. (Owner: docs)

### Suggested immediate actions

1. Wire the recommended parameters into `Set env` stage (safe, low-risk change).
2. Make `createVirtualEnvironment` platform-aware and remove `--without-pip` (medium risk; test on Windows and Linux agents).
3. Add simple retry wrapper around pytest invocation honoring `TEST_RETRY_COUNT` (low risk; improves flakiness handling).
4. Extract `unstash`/`stash` helpers into `cicd-lib` (maintenance improvement).

Use the checklist above to track adoption and iterate in small PRs.

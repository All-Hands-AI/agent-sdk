You are updating this repository to achieve 100% Python docstring coverage.

## Goal
- Run: uv run interrogate openhands --fail-under 100
- If coverage < 100%, add or improve docstrings until the command passes.
- Make minimal, doc-only changes (no behavior changes).

## Docstring Style Guide
- Use **Google-style** docstrings consistently.
- **One-line summary:** Concise, imperative, ends with a period.
- **Args:** Document purpose, constraints, and behavior when `None` or optional.
- **Returns/Yields:** Describe values and conditions clearly.
- **Raises:** Document all relevant exceptions and why they occur.
- **Classes:** Add an **Attributes:** section for key attributes.
- **Modules:** Include a top-level docstring with purpose, context, and usage.
- **Examples:** Add small, runnable examples where appropriate.
- **Quality checks:**
    - No redundant restating of type hints unless clarifying intent.
    - Keep lines ≤ 100 chars.
    - Note side effects (I/O, logging, mutation).
    - For async functions, specify concurrency/ordering assumptions.

## Acceptance Criteria
- `uv run interrogate openhands --fail-under 100` passes.
- Docstrings adhere to the style guide.
- No functional changes; CI/tests continue to pass.

Please push directly to the current branch AND comment on the PR corresponds to the current branch when you are done.
Please starts your comment with "Hi, I'm OpenHands."

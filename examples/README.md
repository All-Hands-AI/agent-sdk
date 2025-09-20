# Running examples with cached LLM completions

We run all scripts in `examples/` via a LiteLLM Proxy with a disk cache. This lets us
record completions periodically and replay them deterministically in PRs.

Usage in CI:
- examples-record.yml: Nightly and manual runs against real providers; uploads `.litellm_cache` artifact
- examples-replay.yml: PR runs download the latest cache and replay examples using the cache only

Local usage (optional):
- You can point examples to a proxy by setting:
  - `LITELLM_BASE_URL` to the proxy URL (e.g., http://localhost:4000)
  - `LITELLM_API_KEY` can be any non-empty string; it's required by the examples

All examples now read `LITELLM_BASE_URL` and default to `https://llm-proxy.eval.all-hands.dev` if unset.

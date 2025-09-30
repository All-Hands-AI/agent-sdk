The codebase contains multiple instances of vague types and union return types that force callers to manually narrow types via if/else or assert. This reduces readability, increases boilerplate, and makes the API harder to reason about statically. Common patterns we want to eliminate:

Optional runtime state: Fields typed as optional but required for correct operation (e.g., initialized to None then set later).
Ambiguous unions in return types (e.g., T | list[T], T | None) where the consumer must narrow or normalize.
Dict[str, Any] -heavy APIs that hide structure and require defensive programming.
Problem statement

Optional runtime state leaks implementation detail (lazy initialization) into consumer types. It spreads not-None checks through the code and invites runtime errors.
Union return types (e.g., T | list[T]) make each call site responsible for normalizing the shape before use, creating inconsistent behavior and duplicated code.
Type vagueness discourages strong tooling from catching errors early.
Functions returning T | U (or T | None) in various subsystems require consumer-side narrowing. Whenever feasible, choose a canonical return shape and stick to it (e.g., always return Sequence[T] and use an empty sequence instead of None; raise exceptions for error conditions).
Goals

Make runtime-required fields non-optional and initialize them via constructor/factory.
Replace runtime checks with construction-time errors.
Eliminate T | list[T] style return types by normalizing to a single shape (prefer Sequence[T]).
Eliminate T | None when absence can be expressed more explicitly:
Use empty collections to represent “no items”
Use exceptions to represent “no valid value” when it’s an error
Only use Optional when the absence is a legitimate, stable API contract (e.g., optional configuration).
Reduce consumer-side type narrowing and asserts to nearly zero in hot paths.
Use Iterable[T] or Sequence[T] instead of list[T] whenever applicable.
Non-goals

Rewriting public HTTP or wire API shapes (keep backward compatibility for external clients).
Refactoring business logic or changing runtime semantics except as required to normalize types.
Removing legitimate discriminated unions in data models where both shapes are intentionally encoded (e.g., tool action variants with “kind” tags).
Proposed changes

Required fields must be non-optional
General rule: Avoid X | None for runtime fields that are mandatory for correct operation. If construction requires multiple steps, use:
A factory/builder pattern that returns a fully initialized object
A dedicated “uninitialized” type (with a different API surface) to prevent misuse
Post-init hooks (e.g., Pydantic model validators) to enforce presence
Normalize return shapes
Replace T | list[T] with Sequence[T] (or list[T]) only. Always return a collection; use empty collection when there is nothing to return.

Replace T | None with:

empty collection when “absence of items”
explicit exceptions for “no result / error”
T | None only when “absence is semantically valid and expected” (e.g., optional configuration)
Where functions must produce two very different outputs:

Prefer split functions (e.g., get_pending_actions() and get_single_action()) instead of overloading one function to sometimes return one, sometimes many.
Or use a discriminated union (dataclass/pydantic model) with a “kind” field so the consumer branches once on a single field, not structural type.
Strengthen function and container types
Replace dict[str, Any] with TypedDict/Protocol/dataclass/Pydantic model to make shapes explicit.

Prefer Sequence[T] over list[T] for parameters; return concrete list[T] if you mutate or need list semantics, else Sequence[T] is often sufficient and more flexible.

Avoid Any; prefer Unknown/Unstructured modeled via TypedDict or generic type variables.

Replace dict[str, Any] in frequently used APIs with TypedDict/Protocol/data classes where feasible.
Success metrics

Reduced code paths that require type narrowing.
Fewer runtime assertions and None checks in hot paths.
Increased coverage of pyright strict checks without suppressions.
Clearer, easier-to-use APIs for downstream code.
Scope

Prefer ripgrep (rg) for speed; fallback to grep -R.
Exclude virtualenv/build/cache folders to reduce noise (e.g., --glob '!/.venv/' etc.).
Typing smells to find

Union return types (e.g., T | U), which force consumer narrowing:
rg -n --glob '!/.venv/' '->[^\\n]*\|'
Union in annotations that encode absence via T | None:
rg -n --glob '!/.venv/' ':[^\\n]\|\sNone\b'
rg -n --glob '!/.venv/' '->[^\\n]\|\sNone\b'
Union with list (e.g., T | list[T]), which forces isinstance(list) checks:
rg -n --glob '!/.venv/' '\|\s*(list\[|Sequence\[)'
rg -n --glob '!/.venv/' 'list\[.\]\s\|'
Stragglers that still use Optional:
rg -n --glob '!/.venv/' '\bOptional\['
Overly vague types:
rg -n --glob '!/.venv/' '\bAny\b'
rg -n --glob '!/.venv/' '->\s*Any\b'
rg -n --glob '!/.venv/' '\bdict\s*\[\sstr\s,\sAny\s\]'
rg -n --glob '!/.venv/' '\bMapping\s*\[\sstr\s,\sAny\s\]'
Required-at-runtime fields that are allowed to be None:
rg -n --glob '!/.venv/' 'executor\s*:\s*[^#\\n]\|\sNone'
rg -n --glob '!/.venv/' 'executor\s*=\s*None\b'
Use similar patterns for other fields known to be required at runtime.
Type-narrowing smells to find (symptoms of the above)

None checks indicating Optional/union-with-None upstream:
rg -n --glob '!/.venv/' '\bis\s+not\s+None\b|\bis\s+None\b|!=\sNone\b|==\sNone\b'
rg -n --glob '!/.venv/' 'assert\s+[^\\n]*\bis\s+not\s+None\b'
Narrowing unions via isinstance, especially list/tuple checks:
rg -n --glob '!/.venv/' 'isinstance\s*\([^\\)]list\s\)'
rg -n --glob '!/.venv/' 'isinstance\s*\([^\\)]tuple\s\)'
rg -n --glob '!/.venv/' 'assert\s+isinstance\s*\('
Casting to paper over vague types:
rg -n --glob '!/.venv/' '\btyping\.cast\('
rg -n --glob '!/.venv/' '\bcast\('
Suppressions hinting at typing issues:
rg -n --glob '!/.venv/' '#\stype:\signore'
rg -n --glob '!/.venv/' 'pyright:\s*ignore'
rg -n --glob '!/.venv/' 'noqa'
Defensive runtime checks caused by optional executors or late init:
rg -n --glob '!/.venv/' "raise\s+NotImplementedError\([^\\)]*has no executor"
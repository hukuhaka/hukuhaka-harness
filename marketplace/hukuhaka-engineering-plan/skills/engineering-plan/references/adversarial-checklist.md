# Adversarial Checklist

Apply one concrete counterexample to every material invariant. Read and use only
the sections relevant to the task.

## Numeric and aggregation

- Negative, zero, near-zero, and very large values
- `null` mixed with valid values
- Partial availability and omitted contributors
- Rounding and floating-point accumulation order
- Division by zero and normalized percentages
- Claimed identities such as totals, balances, or stack heights

Calculate the example. If two requirements cannot hold simultaneously, revise
the plan or mark the decision blocked.

## Temporal

- First and last sample
- Partial and current periods
- Empty periods and missing boundary samples
- Custom windows and sampling transitions
- Cumulative index versus period return
- Timezone and date-boundary behavior

Trace at least two adjacent periods when a rate or return is derived.

## Filesystem, Git, and state

- Missing root and empty workspace
- Malformed candidate and missing reference
- Symlinked file, directory, or path component
- Tracked, untracked, ignored, mixed, staged, deleted, renamed, conflicted
- Non-Git workspace, detached HEAD, and dirty worktree
- Cross-platform paths and permission failures
- Interrupted write, rollback, recovery, and retry

Define the scope of classification before assigning state labels.

## Scale and performance

- Maximum expected entity and sample counts
- Response size, serialization, parsing, and memory
- Repeated subprocess, filesystem, or network calls
- Cache scope and invalidation
- Hidden `O(N × M)` work behind a zero-cost claim

State which cost is actually eliminated and which costs remain.

## Integration and rollout

- Existing transitive callers of a changed helper
- Generated contract or schema drift
- Stale server, client, cache, or generated artifact
- Branch ancestry and fast-forward feasibility
- Backward compatibility and mixed-version operation
- Browser, runtime, console, and observability failures

Tie each surviving risk to a gate, accepted limitation, or blocking decision.

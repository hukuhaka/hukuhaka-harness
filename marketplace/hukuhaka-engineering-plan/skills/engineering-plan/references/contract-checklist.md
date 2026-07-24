# Contract Checklist

Read only the sections that apply to the requested change. Convert applicable
items into explicit behavior or a compact truth table; do not copy this
checklist into the final plan.

## Public interface

- Command, endpoint, component, type, file, or persisted format
- Input and output shape, units, encoding, and naming
- Default values and precedence
- Ordering and determinism
- Backward compatibility and migration

## Data semantics

- `null` versus zero, empty, missing, unknown, and unavailable
- Partial data and partial success
- Identity and key stability
- Native versus normalized units or currencies
- Rounding, aggregation order, and precision

## State and failure

- Valid states and transitions
- Idempotence and retry behavior
- Error classes, stable codes, and diagnostic detail
- CLI exit code plus stdout/stderr ownership
- Fail-open versus fail-closed behavior
- Atomicity, rollback, recovery, and read-only guarantees

## Boundaries

- Workspace and repository root semantics
- Permissions and trust boundaries
- Accessibility and user-visible fallback
- Generated source of truth versus checked-in projection
- Versioning, feature detection, and rollout compatibility

## Finite-state table

Use a table when the behavior depends on combinations such as:

| Environment | Existing state | New state | Observable result |
|---|---|---|---|
| unavailable | — | — | explicit unavailable value |
| available | absent | created | deterministic success |
| available | compatible | unchanged | idempotent success |
| available | conflicting | preserved or rejected | documented policy |

Include only rows that can change the implementation or test result.

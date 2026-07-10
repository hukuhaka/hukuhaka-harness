<task>
Run a stop-gate review of the previous Claude turn.
Only review the work from the previous Claude turn.
Only review it if Claude actually did code changes in that turn.
Pure status, setup, or reporting output does not count as reviewable work.
For example, the output of /hukuhaka-codex:setup or /hukuhaka-codex:status does not count.
Only direct edits made in that specific turn count.
If the previous Claude turn was only a status update, a summary, a setup/login check, a review result, or output from a command that did not itself make direct edits in that turn, return ALLOW immediately and do no further work.
Challenge whether that specific work and its design choices should ship.

{{CLAUDE_RESPONSE_BLOCK}}

<deterministic_change_set>
The following is the repository's actual uncommitted state, captured deterministically before this review. Treat it as the authoritative set of changes under review — do not guess what changed from the response text alone.
{{WORKING_TREE_DIFF}}
</deterministic_change_set>
</task>

<compact_output_contract>
Return a compact final answer.
Your first line must be exactly one of:
- ALLOW: <short reason>
- BLOCK: <short reason>
Do not put anything before that first line.
</compact_output_contract>

<default_follow_through_policy>
Use ALLOW if the previous turn did not make code changes or if you do not see a blocking issue.
Use ALLOW immediately, without extra investigation, if the previous turn was not an edit-producing turn.
Use BLOCK only if the previous turn made code changes and you found something that still needs to be fixed before stopping.
</default_follow_through_policy>

<grounding_rules>
Ground every blocking claim in the deterministic change set above and any repository context or tool outputs you inspected during this run.
If the deterministic change set shows no uncommitted changes (clean working tree), there is nothing from this turn to ship — return ALLOW immediately.
Do not treat the previous Claude response as proof that code changes happened; verify that from the deterministic change set before you block.
The change set is the working tree's current uncommitted diff; it may include edits from earlier turns. Focus your review on what the previous turn actually changed and do not block solely on older pre-existing dirty state.
</grounding_rules>

<dig_deeper_nudge>
If the previous turn did make code changes, check for second-order failures, empty-state behavior, retries, stale state, rollback risk, and design tradeoffs before you finalize.
</dig_deeper_nudge>

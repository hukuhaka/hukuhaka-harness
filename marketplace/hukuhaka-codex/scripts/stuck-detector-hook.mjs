#!/usr/bin/env node

// PostToolUseFailure hook (matcher: Bash). Opt-in via config `stuckDetector`.
//
// Deterministic "detect -> surface" proactive trigger: it counts consecutive
// Bash failures and, after a short streak, nudges Claude to consider a Codex
// second opinion. It NEVER acts on its own (no delegation, no edits) — it only
// adds a one-line note to Claude's context. This is the safe shape of proactive
// Codex use: a deterministic signal, not free-form orchestration.
//
// It runs only on Bash FAILURES (PostToolUseFailure), so successful commands
// cost nothing, and it early-exits instantly when the detector is disabled.

import fs from "node:fs";
import process from "node:process";

import { getConfig, setConfig } from "./lib/state.mjs";
import { resolveWorkspaceRoot } from "./lib/workspace.mjs";

const WINDOW_MS = 5 * 60 * 1000; // failures further apart than this restart the streak
const THRESHOLD = 3; // consecutive failures before nudging
const COOLDOWN_MS = 10 * 60 * 1000; // do not re-nudge within this window

function readHookInput() {
  try {
    const raw = fs.readFileSync(0, "utf8").trim();
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function emit(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

function main() {
  const input = readHookInput();
  // Defense in depth: the matcher already scopes this to Bash.
  if (input.tool_name && input.tool_name !== "Bash") {
    return;
  }

  const cwd = input.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const workspaceRoot = resolveWorkspaceRoot(cwd);
  const config = getConfig(workspaceRoot);
  if (config?.stuckDetector !== true) {
    return; // opt-in; near-zero cost when off
  }

  const now = Date.now();
  const prev = config.stuckState ?? {};
  const withinWindow = typeof prev.lastFailureAt === "number" && now - prev.lastFailureAt <= WINDOW_MS;
  const count = (withinWindow ? Number(prev.count) || 0 : 0) + 1;

  let lastNudgeAt = Number(prev.lastNudgeAt) || 0;
  const cooledDown = now - lastNudgeAt > COOLDOWN_MS;

  if (count >= THRESHOLD && cooledDown) {
    emit({
      hookSpecificOutput: {
        hookEventName: "PostToolUseFailure",
        additionalContext:
          `hukuhaka-codex: ${count} Bash commands have failed in a row, which often means the current approach is stuck. ` +
          "Consider a Codex second opinion before pushing further — /hukuhaka-codex:rescue for a read-only diagnosis/root-cause pass, " +
          "or /hukuhaka-codex:duel to solve it two ways. If you already know the fix, ignore this."
      }
    });
    lastNudgeAt = now;
    // Reset the streak after nudging so the next nudge needs a fresh streak.
    setConfig(workspaceRoot, "stuckState", { count: 0, lastFailureAt: now, lastNudgeAt });
    return;
  }

  setConfig(workspaceRoot, "stuckState", { count, lastFailureAt: now, lastNudgeAt });
}

try {
  main();
} catch (error) {
  // Best-effort: a detector failure must never disrupt the session.
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
}

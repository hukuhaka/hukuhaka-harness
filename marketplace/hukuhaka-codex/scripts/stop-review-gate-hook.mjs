#!/usr/bin/env node

import fs from "node:fs";
import process from "node:process";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { getCodexAvailability } from "./lib/codex.mjs";
import { loadPromptTemplate, interpolateTemplate } from "./lib/prompts.mjs";
import { getConfig, listJobs } from "./lib/state.mjs";
import { sortJobsNewestFirst } from "./lib/job-control.mjs";
import { SESSION_ID_ENV } from "./lib/tracked-jobs.mjs";
import { resolveWorkspaceRoot } from "./lib/workspace.mjs";

const STOP_REVIEW_TIMEOUT_MS = 15 * 60 * 1000;
const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(SCRIPT_DIR, "..");
const STOP_REVIEW_TASK_MARKER = "Run a stop-gate review of the previous Claude turn.";

function readHookInput() {
  const raw = fs.readFileSync(0, "utf8").trim();
  if (!raw) {
    return {};
  }
  return JSON.parse(raw);
}

function emitDecision(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

function logNote(message) {
  if (!message) {
    return;
  }
  process.stderr.write(`${message}\n`);
}

function filterJobsForCurrentSession(jobs, input = {}) {
  const sessionId = input.session_id || process.env[SESSION_ID_ENV] || null;
  if (!sessionId) {
    return jobs;
  }
  return jobs.filter((job) => job.sessionId === sessionId);
}

function getWorkingTreeDiff(cwd) {
  // Deterministic baseline for the stop review: the actual uncommitted change
  // set, computed here rather than left for Codex to infer from the repo. Codex
  // cannot reliably tell "edits from this turn" apart from older dirty state by
  // inspection alone, so we hand it the real working-tree diff. Best-effort:
  // returns "" outside a git repo or on any failure (the review then degrades to
  // the previous infer-from-repo behavior instead of breaking).
  const run = (args) => {
    try {
      const out = spawnSync("git", args, { cwd, encoding: "utf8", timeout: 5000 });
      return out.status === 0 ? String(out.stdout ?? "").trim() : "";
    } catch {
      return "";
    }
  };
  const status = run(["status", "--porcelain"]);
  if (!status) {
    return "";
  }
  const diffstat = run(["diff", "--stat"]);
  const sections = [
    "Working-tree status (git status --porcelain):",
    status,
    diffstat ? "\nChanged files (git diff --stat):" : "",
    diffstat
  ].filter(Boolean);
  return sections.join("\n");
}

function buildStopReviewPrompt(input = {}, cwd = process.cwd()) {
  const lastAssistantMessage = String(input.last_assistant_message ?? "").trim();
  const template = loadPromptTemplate(ROOT_DIR, "stop-review-gate");
  const claudeResponseBlock = lastAssistantMessage
    ? ["Previous Claude response:", lastAssistantMessage].join("\n")
    : "";
  const workingTreeDiff = getWorkingTreeDiff(cwd);
  const workingTreeBlock = workingTreeDiff
    ? ["Current uncommitted changes in the repository:", workingTreeDiff].join("\n")
    : "No uncommitted changes are present in the working tree.";
  return interpolateTemplate(template, {
    CLAUDE_RESPONSE_BLOCK: claudeResponseBlock,
    WORKING_TREE_DIFF: workingTreeBlock
  });
}

function buildSetupNote(cwd) {
  const availability = getCodexAvailability(cwd);
  if (availability.available) {
    return null;
  }

  const detail = availability.detail ? ` ${availability.detail}.` : "";
  return `Codex is not set up for the review gate.${detail} Run /hukuhaka-codex:setup.`;
}

function parseStopReviewOutput(rawOutput) {
  const text = String(rawOutput ?? "").trim();
  if (!text) {
    return {
      ok: false,
      reason:
        "The stop-time Codex review task returned no final output. Run /hukuhaka-codex:review --wait manually or bypass the gate."
    };
  }

  const firstLine = text.split(/\r?\n/, 1)[0].trim();
  if (firstLine.startsWith("ALLOW:")) {
    return { ok: true, reason: null };
  }
  if (firstLine.startsWith("BLOCK:")) {
    const reason = firstLine.slice("BLOCK:".length).trim() || text;
    return {
      ok: false,
      reason: `Codex stop-time review found issues that still need fixes before ending the session: ${reason}`
    };
  }

  return {
    ok: false,
    reason:
      "The stop-time Codex review task returned an unexpected answer. Run /hukuhaka-codex:review --wait manually or bypass the gate."
  };
}

function runStopReview(cwd, input = {}) {
  const scriptPath = path.join(SCRIPT_DIR, "codex-companion.mjs");
  const prompt = buildStopReviewPrompt(input, cwd);
  const childEnv = {
    ...process.env,
    ...(input.session_id ? { [SESSION_ID_ENV]: input.session_id } : {})
  };
  const result = spawnSync(process.execPath, [scriptPath, "task", "--json", prompt], {
    cwd,
    env: childEnv,
    encoding: "utf8",
    timeout: STOP_REVIEW_TIMEOUT_MS
  });

  if (result.error?.code === "ETIMEDOUT") {
    return {
      ok: false,
      reason:
        "The stop-time Codex review task timed out after 15 minutes. Run /hukuhaka-codex:review --wait manually or bypass the gate."
    };
  }

  if (result.status !== 0) {
    const detail = String(result.stderr || result.stdout || "").trim();
    return {
      ok: false,
      reason: detail
        ? `The stop-time Codex review task failed: ${detail}`
        : "The stop-time Codex review task failed. Run /hukuhaka-codex:review --wait manually or bypass the gate."
    };
  }

  try {
    const payload = JSON.parse(result.stdout);
    return parseStopReviewOutput(payload?.rawOutput);
  } catch {
    return {
      ok: false,
      reason:
        "The stop-time Codex review task returned invalid JSON. Run /hukuhaka-codex:review --wait manually or bypass the gate."
    };
  }
}

function main() {
  const input = readHookInput();
  const cwd = input.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const workspaceRoot = resolveWorkspaceRoot(cwd);
  const config = getConfig(workspaceRoot);

  const jobs = sortJobsNewestFirst(filterJobsForCurrentSession(listJobs(workspaceRoot), input));
  const runningJob = jobs.find((job) => job.status === "queued" || job.status === "running");
  const runningTaskNote = runningJob
    ? `Codex task ${runningJob.id} is still running. Check /hukuhaka-codex:status and use /hukuhaka-codex:cancel ${runningJob.id} if you want to stop it before ending the session.`
    : null;

  // A prior Stop hook already continued this turn. Running the review again
  // can never resolve by itself and may create an expensive continuation loop.
  // Surface only any still-running task and allow Claude to stop.
  if (input.stop_hook_active === true) {
    logNote(runningTaskNote);
    return;
  }

  if (!config.stopReviewGate) {
    logNote(runningTaskNote);
    return;
  }

  const setupNote = buildSetupNote(cwd);
  if (setupNote) {
    logNote(setupNote);
    logNote(runningTaskNote);
    return;
  }

  const review = runStopReview(cwd, input);
  // reviewGateBlocking defaults to true (block on a finding). In report-only
  // mode it runs the same review but never blocks — the finding is surfaced as
  // a non-blocking note and Claude is free to stop. (Latency is still paid at
  // stop time; a fully async no-wait variant is a separate follow-up.)
  const blocking = config.reviewGateBlocking !== false;
  if (!review.ok) {
    if (blocking) {
      emitDecision({
        decision: "block",
        reason: runningTaskNote ? `${runningTaskNote} ${review.reason}` : review.reason
      });
      return;
    }
    emitDecision({
      systemMessage: runningTaskNote ? `${runningTaskNote}\n${review.reason}` : review.reason
    });
    return;
  }

  logNote(runningTaskNote);
}

try {
  main();
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
}

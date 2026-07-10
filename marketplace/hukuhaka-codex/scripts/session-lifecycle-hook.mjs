#!/usr/bin/env node

import fs from "node:fs";
import process from "node:process";

import { terminateProcessTree } from "./lib/process.mjs";
import { BROKER_ENDPOINT_ENV } from "./lib/app-server.mjs";
import {
  clearBrokerSession,
  LOG_FILE_ENV,
  loadBrokerSession,
  PID_FILE_ENV,
  sendBrokerShutdown,
  teardownBrokerSession
} from "./lib/broker-lifecycle.mjs";
import { TRANSCRIPT_PATH_ENV } from "./lib/claude-session-transfer.mjs";
import { getConfig, loadState, resolveStateFile, saveState, setConfig } from "./lib/state.mjs";
import { resolveWorkspaceRoot } from "./lib/workspace.mjs";

export const SESSION_ID_ENV = "CODEX_COMPANION_SESSION_ID";
const PLUGIN_DATA_ENV = "CLAUDE_PLUGIN_DATA";

function readHookInput() {
  const raw = fs.readFileSync(0, "utf8").trim();
  if (!raw) {
    return {};
  }
  return JSON.parse(raw);
}

function shellEscape(value) {
  return `'${String(value).replace(/'/g, `'\"'\"'`)}'`;
}

function appendEnvVar(name, value) {
  if (!process.env.CLAUDE_ENV_FILE || value == null || value === "") {
    return;
  }
  fs.appendFileSync(process.env.CLAUDE_ENV_FILE, `export ${name}=${shellEscape(value)}\n`, "utf8");
}

function cleanupSessionJobs(cwd, sessionId) {
  if (!cwd || !sessionId) {
    return;
  }

  const workspaceRoot = resolveWorkspaceRoot(cwd);
  const stateFile = resolveStateFile(workspaceRoot);
  if (!fs.existsSync(stateFile)) {
    return;
  }

  const state = loadState(workspaceRoot);
  const sessionJobs = state.jobs.filter((job) => job.sessionId === sessionId);
  if (sessionJobs.length === 0) {
    return;
  }

  // On session end, terminate jobs still running and mark them cancelled, but
  // RETAIN completed jobs. Their Codex thread ids are what lets `/plan`,
  // `/full`, and `/rescue --resume` continue in a later session — deleting them
  // (the old behavior) silently broke cross-session resume despite the docs
  // promising it. Active jobs from a dead session can't be continued, so they
  // are marked cancelled rather than left dangling as "running".
  const nextJobs = state.jobs.map((job) => {
    if (job.sessionId !== sessionId) {
      return job;
    }
    const stillRunning = job.status === "queued" || job.status === "running";
    if (!stillRunning) {
      return job;
    }
    try {
      terminateProcessTree(job.pid ?? Number.NaN);
    } catch {
      // Ignore teardown failures during session shutdown.
    }
    return { ...job, status: "cancelled" };
  });

  saveState(workspaceRoot, {
    ...state,
    jobs: nextJobs
  });
}

function emitReviewGateNudge(input) {
  // One-line, actionable-only nudge: surface the opt-in Stop review-gate while
  // it is OFF so the proactive-review surface is discoverable without flipping
  // the default on. Fires once per repo (not every session) so a user who
  // deliberately leaves the gate off is not nagged forever. Silent on any
  // failure; never blocks session start.
  try {
    const cwd = input.cwd || process.cwd();
    const workspaceRoot = resolveWorkspaceRoot(cwd);
    const config = getConfig(workspaceRoot);
    if (config?.stopReviewGate === true || config?.reviewGateNudgeShown === true) {
      return;
    }
    const additionalContext =
      "hukuhaka-codex: Codex can proactively review and diagnose your work read-only " +
      "(it never edits files unless you explicitly ask). The Stop review-gate — Codex " +
      "auto-reviews each turn's code changes before Claude stops — is currently OFF. " +
      "Enable it with /hukuhaka-codex:setup --enable-review-gate (blocking) or --report-only " +
      "(never blocks). You can also run /hukuhaka-codex:setup --enable-stuck-detector to get " +
      "nudged toward a Codex second opinion after a streak of command failures.";
    process.stdout.write(
      `${JSON.stringify({
        hookSpecificOutput: {
          hookEventName: "SessionStart",
          additionalContext
        }
      })}\n`
    );
    // Mark as shown so the nudge fires once per repo, not every session. An
    // explicit `setup --disable-review-gate` leaves this set, so disabling the
    // gate also suppresses future nags.
    setConfig(workspaceRoot, "reviewGateNudgeShown", true);
  } catch {
    // Discoverability nudge is best-effort; never fail session start over it.
  }
}

function handleSessionStart(input) {
  appendEnvVar(SESSION_ID_ENV, input.session_id);
  appendEnvVar(TRANSCRIPT_PATH_ENV, input.transcript_path);
  appendEnvVar(PLUGIN_DATA_ENV, process.env[PLUGIN_DATA_ENV]);
  emitReviewGateNudge(input);
}

async function handleSessionEnd(input) {
  const cwd = input.cwd || process.cwd();
  const brokerSession =
    loadBrokerSession(cwd) ??
    (process.env[BROKER_ENDPOINT_ENV]
      ? {
          endpoint: process.env[BROKER_ENDPOINT_ENV],
          pidFile: process.env[PID_FILE_ENV] ?? null,
          logFile: process.env[LOG_FILE_ENV] ?? null
        }
      : null);
  const brokerEndpoint = brokerSession?.endpoint ?? null;
  const pidFile = brokerSession?.pidFile ?? null;
  const logFile = brokerSession?.logFile ?? null;
  const sessionDir = brokerSession?.sessionDir ?? null;
  const pid = brokerSession?.pid ?? null;

  if (brokerEndpoint) {
    await sendBrokerShutdown(brokerEndpoint);
  }

  cleanupSessionJobs(cwd, input.session_id || process.env[SESSION_ID_ENV]);
  teardownBrokerSession({
    endpoint: brokerEndpoint,
    pidFile,
    logFile,
    sessionDir,
    pid,
    killProcess: terminateProcessTree
  });
  clearBrokerSession(cwd);
}

async function main() {
  const input = readHookInput();
  const eventName = process.argv[2] ?? input.hook_event_name ?? "";

  if (eventName === "SessionStart") {
    handleSessionStart(input);
    return;
  }

  if (eventName === "SessionEnd") {
    await handleSessionEnd(input);
  }
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(1);
});

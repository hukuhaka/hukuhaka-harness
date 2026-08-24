import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { loadState, saveState } from "../../../marketplace/hukuhaka-codex/scripts/lib/state.mjs";

const ROOT = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const PLUGIN = path.join(ROOT, "marketplace", "hukuhaka-codex");
const STOP_HOOK = path.join(PLUGIN, "scripts", "stop-review-gate-hook.mjs");
const STUCK_HOOK = path.join(PLUGIN, "scripts", "stuck-detector-hook.mjs");

function withFixture(callback) {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "hukuhaka-hook-contract-"));
  const workspace = path.join(fixtureRoot, "workspace");
  const pluginData = path.join(fixtureRoot, "plugin-data");
  fs.mkdirSync(workspace);
  const previousPluginData = process.env.CLAUDE_PLUGIN_DATA;
  process.env.CLAUDE_PLUGIN_DATA = pluginData;
  try {
    callback({ workspace, pluginData });
  } finally {
    if (previousPluginData == null) {
      delete process.env.CLAUDE_PLUGIN_DATA;
    } else {
      process.env.CLAUDE_PLUGIN_DATA = previousPluginData;
    }
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

function runHook(script, input, pluginData) {
  return spawnSync(process.execPath, [script], {
    input: `${JSON.stringify(input)}\n`,
    env: {
      ...process.env,
      CLAUDE_PLUGIN_DATA: pluginData,
      PATH: ""
    },
    encoding: "utf8"
  });
}

test("Stop re-entry allows stop without setup checks or another review", () => {
  withFixture(({ workspace, pluginData }) => {
    saveState(workspace, {
      config: { stopReviewGate: true },
      jobs: [
        {
          id: "task-running",
          status: "running",
          sessionId: "session-1",
          updatedAt: "2026-08-24T00:00:00Z"
        }
      ]
    });

    const result = runHook(
      STOP_HOOK,
      {
        cwd: workspace,
        session_id: "session-1",
        hook_event_name: "Stop",
        stop_hook_active: true
      },
      pluginData
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, "");
    assert.match(result.stderr, /task-running is still running/);
    assert.doesNotMatch(result.stderr, /Codex is not set up/);
  });
});

test("stuck detector nudges on the third Bash failure within five minutes", () => {
  withFixture(({ workspace, pluginData }) => {
    saveState(workspace, {
      config: {
        stuckDetector: true,
        stuckState: {
          count: 2,
          windowStartedAt: Date.now(),
          lastFailureAt: Date.now(),
          lastNudgeAt: 0
        }
      }
    });

    const result = runHook(
      STUCK_HOOK,
      { cwd: workspace, hook_event_name: "PostToolUseFailure", tool_name: "Bash" },
      pluginData
    );

    assert.equal(result.status, 0, result.stderr);
    const payload = JSON.parse(result.stdout);
    assert.match(payload.hookSpecificOutput.additionalContext, /3 Bash commands failed within five minutes/);
    assert.equal(loadState(workspace).config.stuckState.count, 0);
  });
});

test("stuck detector restarts the count after five minutes", () => {
  withFixture(({ workspace, pluginData }) => {
    saveState(workspace, {
      config: {
        stuckDetector: true,
        stuckState: {
          count: 2,
          windowStartedAt: Date.now() - 5 * 60 * 1000 - 1000,
          lastFailureAt: Date.now() - 1000,
          lastNudgeAt: 0
        }
      }
    });

    const result = runHook(
      STUCK_HOOK,
      { cwd: workspace, hook_event_name: "PostToolUseFailure", tool_name: "Bash" },
      pluginData
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, "");
    assert.equal(loadState(workspace).config.stuckState.count, 1);
  });
});

test("stuck detector keeps the count but suppresses nudges during cooldown", () => {
  withFixture(({ workspace, pluginData }) => {
    saveState(workspace, {
      config: {
        stuckDetector: true,
        stuckState: {
          count: 2,
          windowStartedAt: Date.now(),
          lastFailureAt: Date.now(),
          lastNudgeAt: Date.now() - 1000
        }
      }
    });

    const result = runHook(
      STUCK_HOOK,
      { cwd: workspace, hook_event_name: "PostToolUseFailure", tool_name: "Bash" },
      pluginData
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, "");
    assert.equal(loadState(workspace).config.stuckState.count, 3);
  });
});

test("stuck detector does not chain adjacent failures across a longer total window", () => {
  withFixture(({ workspace, pluginData }) => {
    const now = Date.now();
    saveState(workspace, {
      config: {
        stuckDetector: true,
        stuckState: {
          count: 2,
          windowStartedAt: now - 9 * 60 * 1000,
          lastFailureAt: now - 4 * 60 * 1000,
          lastNudgeAt: 0
        }
      }
    });

    const result = runHook(
      STUCK_HOOK,
      { cwd: workspace, hook_event_name: "PostToolUseFailure", tool_name: "Bash" },
      pluginData
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, "");
    assert.equal(loadState(workspace).config.stuckState.count, 1);
  });
});

test("stuck detector fails safe when migrating state without a window start", () => {
  withFixture(({ workspace, pluginData }) => {
    saveState(workspace, {
      config: {
        stuckDetector: true,
        stuckState: { count: 2, lastFailureAt: Date.now(), lastNudgeAt: 0 }
      }
    });

    const result = runHook(
      STUCK_HOOK,
      { cwd: workspace, hook_event_name: "PostToolUseFailure", tool_name: "Bash" },
      pluginData
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, "");
    assert.equal(loadState(workspace).config.stuckState.count, 1);
  });
});

test("stuck detector observes failures only and rescue defaults to foreground", () => {
  const hooks = JSON.parse(fs.readFileSync(path.join(PLUGIN, "hooks", "hooks.json"), "utf8"));
  assert.ok(hooks.hooks.PostToolUseFailure);
  assert.equal(hooks.hooks.PostToolUse, undefined);

  const command = fs.readFileSync(path.join(PLUGIN, "commands", "rescue.md"), "utf8");
  const agent = fs.readFileSync(path.join(PLUGIN, "agents", "codex-rescue.md"), "utf8");
  assert.match(command, /If neither flag is present, default to foreground/);
  assert.match(agent, /use foreground execution\. Background execution is opt-in only/);
  assert.doesNotMatch(agent, /task looks complicated/);
});

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const TRANSFER_MODULE = path.join(
  ROOT,
  "marketplace",
  "hukuhaka-codex",
  "scripts",
  "lib",
  "claude-session-transfer.mjs"
);
const SESSION_HOOK = path.join(
  ROOT,
  "marketplace",
  "hukuhaka-codex",
  "scripts",
  "session-lifecycle-hook.mjs"
);

const testRoot = fs.mkdtempSync(path.join(os.tmpdir(), "hukuhaka-transfer-test-"));
const fakeHome = path.join(testRoot, "home");
const projectsDir = path.join(fakeHome, ".claude", "projects", "workspace");
const transcriptPath = path.join(projectsDir, "session.jsonl");
fs.mkdirSync(projectsDir, { recursive: true });
fs.writeFileSync(transcriptPath, '{"type":"user","message":{"role":"user","content":"hello"}}\n');

process.env.HOME = fakeHome;
const { TRANSCRIPT_PATH_ENV, resolveClaudeSessionPath } = await import(
  `${pathToFileURL(TRANSFER_MODULE).href}?test=${Date.now()}`
);

test.after(() => {
  fs.rmSync(testRoot, { recursive: true, force: true });
});

test("resolves an explicit Claude transcript inside ~/.claude/projects", () => {
  assert.equal(resolveClaudeSessionPath(testRoot, { source: transcriptPath }), fs.realpathSync(transcriptPath));
});

test("uses the SessionStart transcript environment variable", () => {
  process.env[TRANSCRIPT_PATH_ENV] = transcriptPath;
  try {
    assert.equal(resolveClaudeSessionPath(testRoot), fs.realpathSync(transcriptPath));
  } finally {
    delete process.env[TRANSCRIPT_PATH_ENV];
  }
});

test("requires a JSONL source", () => {
  const invalidPath = path.join(projectsDir, "session.txt");
  fs.writeFileSync(invalidPath, "not jsonl\n");
  assert.throws(
    () => resolveClaudeSessionPath(testRoot, { source: invalidPath }),
    /must be a JSONL file/
  );
});

test("rejects a source outside ~/.claude/projects", () => {
  const outsidePath = path.join(testRoot, "outside.jsonl");
  fs.writeFileSync(outsidePath, "{}\n");
  assert.throws(
    () => resolveClaudeSessionPath(testRoot, { source: outsidePath }),
    /only from .*\.claude.*projects/
  );
});

test("rejects a symlink that escapes ~/.claude/projects", () => {
  const outsidePath = path.join(testRoot, "outside-symlink-target.jsonl");
  const symlinkPath = path.join(projectsDir, "escaped.jsonl");
  fs.writeFileSync(outsidePath, "{}\n");
  fs.symlinkSync(outsidePath, symlinkPath);
  assert.throws(
    () => resolveClaudeSessionPath(testRoot, { source: symlinkPath }),
    /only from .*\.claude.*projects/
  );
});

test("SessionStart exports the current transcript path", () => {
  const envFile = path.join(testRoot, "claude-env");
  const result = spawnSync(process.execPath, [SESSION_HOOK, "SessionStart"], {
    cwd: testRoot,
    env: {
      ...process.env,
      HOME: fakeHome,
      CLAUDE_ENV_FILE: envFile,
      CLAUDE_PLUGIN_DATA: path.join(testRoot, "plugin-data")
    },
    input: JSON.stringify({
      hook_event_name: "SessionStart",
      session_id: "session-123",
      transcript_path: transcriptPath,
      cwd: testRoot
    }),
    encoding: "utf8"
  });

  assert.equal(result.status, 0, result.stderr);
  const exports = fs.readFileSync(envFile, "utf8");
  assert.match(exports, /CODEX_COMPANION_SESSION_ID='session-123'/);
  assert.match(exports, /CODEX_COMPANION_TRANSCRIPT_PATH='.*session\.jsonl'/);
});

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { findLatestResumableTaskJob } from "../../../marketplace/hukuhaka-codex/scripts/lib/job-control.mjs";
import { saveState } from "../../../marketplace/hukuhaka-codex/scripts/lib/state.mjs";

const ROOT = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const PLUGIN = path.join(ROOT, "marketplace", "hukuhaka-codex");
const COMPANION = path.join(PLUGIN, "scripts", "codex-companion.mjs");

function read(relativePath) {
  return fs.readFileSync(path.join(PLUGIN, relativePath), "utf8");
}

test("selects only a resumable task from the requested workflow", () => {
  const jobs = [
    { id: "rescue-newer", jobClass: "task", workflow: "task", status: "completed", threadId: "rescue-thread" },
    { id: "plan-running", jobClass: "task", workflow: "plan", status: "running", threadId: "running-plan" },
    { id: "plan-ready", jobClass: "task", workflow: "plan", status: "completed", threadId: "plan-thread" }
  ];

  assert.equal(findLatestResumableTaskJob(jobs, "plan")?.id, "plan-ready");
  assert.equal(findLatestResumableTaskJob(jobs, "task")?.id, "rescue-newer");
});

test("does not treat a legacy unclassified task as a plan", () => {
  const jobs = [
    { id: "legacy", jobClass: "task", status: "completed", threadId: "legacy-thread" }
  ];

  assert.equal(findLatestResumableTaskJob(jobs, "plan"), null);
  assert.equal(findLatestResumableTaskJob(jobs, "task")?.id, "legacy");
});

test("task-resume-candidate returns the exact plan workflow candidate", () => {
  const pluginData = fs.mkdtempSync(path.join(os.tmpdir(), "hukuhaka-plan-state-"));
  const previousPluginData = process.env.CLAUDE_PLUGIN_DATA;
  process.env.CLAUDE_PLUGIN_DATA = pluginData;
  try {
    saveState(ROOT, {
      jobs: [
        { id: "rescue-newer", jobClass: "task", workflow: "task", status: "completed", threadId: "rescue-thread", updatedAt: "2026-07-10T02:00:00Z" },
        { id: "plan-ready", jobClass: "task", workflow: "plan", status: "completed", threadId: "plan-thread", updatedAt: "2026-07-10T01:00:00Z" }
      ]
    });

    const result = spawnSync(
      process.execPath,
      [COMPANION, "task-resume-candidate", "--workflow", "plan", "--cwd", ROOT, "--json"],
      {
        env: { ...process.env, CLAUDE_PLUGIN_DATA: pluginData },
        encoding: "utf8"
      }
    );
    assert.equal(result.status, 0, result.stderr);
    const payload = JSON.parse(result.stdout);
    assert.equal(payload.workflow, "plan");
    assert.equal(payload.candidate.id, "plan-ready");
    assert.equal(payload.candidate.threadId, "plan-thread");
  } finally {
    if (previousPluginData == null) {
      delete process.env.CLAUDE_PLUGIN_DATA;
    } else {
      process.env.CLAUDE_PLUGIN_DATA = previousPluginData;
    }
    fs.rmSync(pluginData, { recursive: true, force: true });
  }
});

test("uses model-neutral prompting without stale GPT-5.4 references", () => {
  const files = [
    "agents/codex-rescue.md",
    "commands/debate.md",
    "commands/duel.md",
    "commands/full.md",
    "commands/plan.md",
    "skills/codex-cli-runtime/SKILL.md",
    "skills/codex-plan/SKILL.md",
    "skills/codex-prompting/SKILL.md",
    "skills/codex-prompting/references/codex-prompt-antipatterns.md",
    "skills/codex-prompting/references/codex-prompt-recipes.md",
    "skills/codex-prompting/references/prompt-blocks.md"
  ];
  const combined = files.map(read).join("\n");

  assert.doesNotMatch(combined, /gpt-5-4-prompting|GPT-5\.4/);
  assert.match(read("agents/codex-rescue.md"), /skills:\s+[\s\S]*- codex-prompting/);
  assert.match(read("skills/codex-prompting/SKILL.md"), /name: codex-prompting/);
});

test("keeps the plan contract canonical and workflow-scoped", () => {
  const skill = read("skills/codex-plan/SKILL.md");
  const planCommand = read("commands/plan.md");
  const fullCommand = read("commands/full.md");

  for (const section of ["GOAL", "ASSUMPTIONS", "FILES", "STEPS", "RISKS", "VERIFICATION", "OPEN QUESTIONS"]) {
    assert.match(skill, new RegExp(`\\b${section}\\b`));
  }
  for (const block of ["grounding_rules", "missing_context_gating", "completeness_contract", "verification_loop"]) {
    assert.match(skill, new RegExp(`<${block}>`));
  }
  assert.match(skill, /task-resume-candidate --workflow plan/);
  assert.match(skill, /task --workflow plan/);
  assert.doesNotMatch(skill, /codex-prompting/);
  assert.match(planCommand, /task --workflow plan/);
  assert.match(fullCommand, /task --workflow plan/);
  assert.doesNotMatch(`${planCommand}\n${fullCommand}`, /codex-prompting/);
});

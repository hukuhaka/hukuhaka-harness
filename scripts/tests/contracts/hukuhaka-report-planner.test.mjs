import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const PLUGIN_ROOT = path.join(ROOT, "marketplace", "hukuhaka-report-planner");
const SKILL_ROOT = path.join(PLUGIN_ROOT, "skills", "hukuhaka-report-planner");
const DESIGNER_SKILL = path.join(PLUGIN_ROOT, "skills", "artifact-designer", "SKILL.md");
const DESIGNER_AGENT = path.join(PLUGIN_ROOT, "agents", "artifact-designer.md");
const STAGES_ROOT = path.join(SKILL_ROOT, "stages");
const EVAL_FIXTURE = path.join(
  ROOT,
  "eval",
  "cases",
  "report-planner-plan-only",
  "fixture"
);

function read(relativePath) {
  return fs.readFileSync(path.join(SKILL_ROOT, relativePath), "utf8");
}

function markdownFiles(root) {
  return fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const candidate = path.join(root, entry.name);
    if (entry.isDirectory()) {
      return markdownFiles(candidate);
    }
    return entry.name.endsWith(".md") ? [candidate] : [];
  });
}

test("skill exposes the four-stage dual-mode contract", () => {
  const skill = read("SKILL.md");
  const frontmatter = skill.match(/^---\n([\s\S]*?)\n---/)?.[1] ?? "";
  const description = frontmatter.match(/^description:\s*"([\s\S]*?)"$/m)?.[1] ?? "";
  const stageFiles = fs.readdirSync(STAGES_ROOT).sort();

  assert.ok(Buffer.byteLength(description, "utf8") < 1024, "description exceeds 1024 bytes");
  assert.deepEqual(stageFiles, [
    "1-frame.md",
    "2-structure.md",
    "3-direct.md",
    "4-lock.md"
  ]);
  for (const stage of stageFiles) {
    assert.match(skill, new RegExp(`stages/${stage.replace(".", "\\.")}`));
  }
  assert.match(skill, /Plan mode/);
  assert.match(skill, /Build-preflight mode/);
  assert.match(skill, /run all four stages/);
  assert.match(skill, /finalized spec/);
  assert.match(skill, /one `artifact-designer` subagent/);
  assert.match(skill, /\.hukuhaka\/reports\/<short-name>\/spec\.md/);
  assert.match(skill, /\.claude\/reports\/<short-name>\/spec\.md.*legacy fallback/);
  assert.match(skill, /Legacy paths are read-only/);
});

test("Stage 2 structures meaning and Stage 3 owns anchor construction", () => {
  const stage2 = read("stages/2-structure.md");
  const stage3 = read("stages/3-direct.md");
  const stage4 = read("stages/4-lock.md");
  const schema = read("references/spec-schema.md");

  assert.match(stage2, /does not choose its visual form|Do not choose chart/);
  assert.match(stage3, /construction brief/i);
  assert.match(stage3, /designer-view self-critique/i);
  assert.match(stage3, /`material`/);
  assert.match(stage3, /`composition`/);
  assert.match(stage3, /`treatment`/);
  assert.match(stage3, /path and symbol/);
  assert.match(stage3, /static or reduced-motion fallback/);
  assert.match(stage3, /Do not spawn a\s+designer/);
  assert.match(stage4, /final self-review/i);
  assert.match(stage4, /Stages 3 and 4/);
  assert.match(schema, /material:/);
  assert.match(schema, /composition:/);
  assert.match(schema, /treatment:/);
  assert.match(schema, /A prose-only document uses `- none:`/);
  assert.match(schema, /not an executable schema/);
});

test("references stay progressive without external design-source support", () => {
  const stage3 = read("stages/3-direct.md");
  const index = read("references/reference-index.md");
  const craftDir = path.join(SKILL_ROOT, "references", "craft");

  assert.match(stage3, /Do not read all of `references\/craft\/`/);
  assert.match(stage3, /select zero to\s+three files/i);
  assert.match(index, /bundled craft knowledge, not style targets or templates/i);

  for (const filename of fs.readdirSync(craftDir).filter((name) => name.endsWith(".md"))) {
    const content = fs.readFileSync(path.join(craftDir, filename), "utf8");
    assert.match(content, /^use_when:/m, `${filename} has no use_when route`);
    assert.match(content, /^do_not_use_when:/m, `${filename} has no do_not_use_when route`);
    assert.match(content, /^style_risk:/m, `${filename} has no style_risk warning`);
  }

  const runtimeMarkdown = markdownFiles(PLUGIN_ROOT)
    .map((filename) => fs.readFileSync(filename, "utf8"))
    .join("\n");
  assert.doesNotMatch(runtimeMarkdown, /DESIGN\.md/);
  assert.doesNotMatch(runtimeMarkdown, /design source:/i);
});

test("build-preflight delegates one finalized contract to the portable designer", () => {
  const skill = read("SKILL.md");
  const stage3 = read("stages/3-direct.md");
  const stage4 = read("stages/4-lock.md");
  const handoff = read("references/build-handoff.md");
  const designerSkill = fs.readFileSync(DESIGNER_SKILL, "utf8");
  const designerAgent = fs.readFileSync(DESIGNER_AGENT, "utf8");

  assert.match(stage3, /Do not spawn a\s+designer/);
  assert.match(stage4, /delegate the finalized spec/);
  assert.match(stage4, /Do not set `run_in_background`/);
  assert.match(handoff, /Stage 4 finalizes/);
  assert.match(handoff, /Do not build in the parent/i);
  assert.match(handoff, /do not set `run_in_background`/i);
  assert.match(handoff, /return before the receipt/i);
  assert.match(handoff, /write-capable worker/i);
  assert.doesNotMatch(handoff, /design source/i);
  assert.match(designerSkill, /missing planning input/i);
  assert.match(designerSkill, /source has drifted/i);
  assert.match(designerSkill, /construction-brief deviations/i);
  assert.match(designerSkill, /visual\s+inspection/i);
  assert.match(designerSkill, /every exact width/i);
  assert.match(designerSkill, /no horizontal overflow/i);
  assert.match(designerSkill, /reduced motion/i);
  assert.match(designerSkill, /Do not edit `spec\.md`/);
  assert.match(designerAgent, /^name:\s*artifact-designer$/m);
  assert.match(designerAgent, /^skills:\s*\n\s+- artifact-designer$/m);
  assert.match(designerAgent, /^disallowedTools:\s*Agent, Task$/m);
  assert.doesNotMatch(designerAgent, /^tools:/m);
  assert.doesNotMatch(`${skill}\n${stage4}\n${handoff}\n${designerSkill}`, /validate-spec/);
});

test("validator and static design fixtures are absent", () => {
  const validator = path.join(SKILL_ROOT, "scripts", "validate-spec.sh");
  const runtimeFigma = path.join(SKILL_ROOT, "references", "fixtures", "figma");
  const ibmFixture = path.join(EVAL_FIXTURE, "design", "IBM");

  assert.equal(fs.existsSync(validator), false);
  assert.deepEqual(
    fs.existsSync(ibmFixture) ? fs.readdirSync(ibmFixture) : [],
    [],
    "IBM fixture files still exist"
  );
  assert.deepEqual(
    fs.existsSync(runtimeFigma) ? fs.readdirSync(runtimeFigma) : [],
    [],
    "runtime Figma fixture files still exist"
  );
});

test("design-led eval fixture exposes the backend-contract-frontend seam", () => {
  if (!fs.existsSync(path.join(ROOT, "eval"))) {
    return;
  }

  const expected = [
    "README.md",
    "contracts/report.schema.json",
    "backend/app.py",
    "frontend/report-api.ts",
    "frontend/report-view.ts",
    "tests/test_contract.py"
  ];

  for (const relativePath of expected) {
    assert.ok(fs.existsSync(path.join(EVAL_FIXTURE, relativePath)), `${relativePath} missing`);
  }
  const prompt = fs.readFileSync(
    path.join(ROOT, "eval", "cases", "report-planner-plan-only", "prompt.md"),
    "utf8"
  );
  assert.match(prompt, /frontend\/backend connection/);
  assert.match(prompt, /exact source excerpt/);
  assert.match(prompt, /stop after Stage 4/);
  assert.doesNotMatch(prompt, /DESIGN\.md|IBM|validate/i);
});

test("Claude and Codex manifests share the report-planner version", () => {
  const claude = JSON.parse(
    fs.readFileSync(path.join(PLUGIN_ROOT, ".claude-plugin", "plugin.json"), "utf8")
  );
  const codex = JSON.parse(
    fs.readFileSync(path.join(PLUGIN_ROOT, ".codex-plugin", "plugin.json"), "utf8")
  );

  assert.equal(claude.version, codex.version);
  assert.equal(claude.version, "0.6.0");
});

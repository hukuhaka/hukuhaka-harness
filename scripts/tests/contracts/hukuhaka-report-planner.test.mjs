import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const SKILL_ROOT = path.join(
  ROOT,
  "marketplace",
  "hukuhaka-report-planner",
  "skills",
  "hukuhaka-report-planner"
);
const PLUGIN_ROOT = path.dirname(path.dirname(SKILL_ROOT));
const DESIGNER_SKILL_ROOT = path.join(PLUGIN_ROOT, "skills", "artifact-designer");
const DESIGNER_AGENT = path.join(PLUGIN_ROOT, "agents", "artifact-designer.md");
const IBM_FIXTURE_ROOT = path.join(
  ROOT,
  "eval",
  "cases",
  "report-planner-plan-only",
  "fixture",
  "design",
  "IBM"
);
const VALIDATOR = path.join(SKILL_ROOT, "scripts", "validate-spec.sh");

function read(relativePath) {
  return fs.readFileSync(path.join(SKILL_ROOT, relativePath), "utf8");
}

function validate(spec) {
  return spawnSync("bash", [VALIDATOR], { input: spec, encoding: "utf8" });
}

const VALID_SPEC = `# Runtime migration - document plan - 2026-07-14

## Document Model

- job: decide
- reading behavior: scan
- form: web document
- audience: maintainers deciding whether to migrate
- success test: reader can choose a migration route in two minutes
- prose level: balanced

## Evidence

- established: current and target runtime behavior is verified
- source S1: src/runtime.ts - supports: U1, A1
- conflict: none
- gap: none
- freshness: checked 2026-07-14

## Structure

- trunk: compare the two routes against the migration decision
- U1 Route comparison
  - reader question: which route minimizes compatibility risk?
  - reader outcome: choose route A or B
  - evidence: S1
  - anchor: A1

## Anchors

### A1 Route matrix

- reader question: which route minimizes compatibility risk?
- evidence: S1 compatibility fields
- selected form: decision matrix
- takeaway: route A preserves the required contract
- caveat: deployment cost remains estimated

## Design Direction

- concept: compact comparison surface with a strong decision path and quiet evidence detail
- selected references: references/craft/tables.md
- borrow: aligned criteria and explicit units
- transform: use decision outcomes rather than a generic data table
- reject: decorative ranking and unrelated KPI tiles
- clone risk: exact composition and typography derive from the host product

## Build Contract

- locked: facts, route criteria, decision outcome, source labels, accessible reading order
- guided: compact density, clear comparison roles, restrained state color
- open: exact grid, typography, spacing, and interaction treatment

## Acceptance Tests

- [ ] Reader can choose a migration route in two minutes.
- [ ] Every factual comparison resolves to S1.
`;

test("skill exposes the three-stage dual-mode contract", () => {
  const skill = read("SKILL.md");
  const frontmatter = skill.match(/^---\n([\s\S]*?)\n---/)?.[1] ?? "";
  const description = frontmatter.match(/^description:\s*"([\s\S]*?)"$/m)?.[1] ?? "";

  assert.ok(Buffer.byteLength(description, "utf8") < 1024, "description exceeds 1024 bytes");
  assert.match(skill, /Plan mode/);
  assert.match(skill, /Build-preflight mode/);
  assert.match(skill, /stages\/2-lock\.md/);
  assert.match(skill, /select no more than\s+three optional references/);
  assert.match(skill, /relative to this `SKILL\.md` file/);
  assert.match(skill, /contract depth proportional to the artifact/);
  assert.match(skill, /\.hukuhaka\/reports\/<short-name>\/spec\.md/);
  assert.match(skill, /\.claude\/reports\/<short-name>\/spec\.md.*legacy fallback/);
  assert.match(skill, /Legacy paths are read-only/);
  assert.match(skill, /Never dual-write/);
  assert.doesNotMatch(skill, /new, unconstrained turn|separate, unconstrained step/);

  const stage0 = read("stages/0-frame.md");
  const stage2 = read("stages/2-lock.md");
  assert.match(stage0, /\.hukuhaka\/reports\/tmp-draft\/spec\.md/);
  assert.match(stage2, /\.hukuhaka\/reports\/<short-name>\/spec\.md/);
  assert.doesNotMatch(`${stage0}\n${stage2}`, /\.claude\/reports/);
});

test("reference routing is progressive and external design targets are opt-in", () => {
  const stage = read("stages/1-plan.md");
  const index = read("references/reference-index.md");
  const craftDir = path.join(SKILL_ROOT, "references", "craft");

  assert.match(stage, /Do not read all of `references\/craft\/`/);
  assert.match(stage, /Select zero to three files/);
  assert.match(index, /external style target is off by default/i);
  assert.match(index, /explicitly supplies a `DESIGN\.md`/);

  for (const filename of fs.readdirSync(craftDir).filter((name) => name.endsWith(".md"))) {
    const content = fs.readFileSync(path.join(craftDir, filename), "utf8");
    assert.match(content, /^use_when:/m, `${filename} has no use_when route`);
    assert.match(content, /^do_not_use_when:/m, `${filename} has no do_not_use_when route`);
    assert.match(content, /^style_risk:/m, `${filename} has no style_risk warning`);
  }

  const combined = fs.readdirSync(craftDir)
    .filter((name) => name.endsWith(".md"))
    .map((name) => fs.readFileSync(path.join(craftDir, name), "utf8"))
    .join("\n");
  assert.doesNotMatch(combined, /Every section, ideally every page|Never Mermaid|one accent per report|Inter as primary or fallback/);
});

test("build-preflight delegates construction to the portable designer contract", () => {
  const skill = read("SKILL.md");
  const stage2 = read("stages/2-lock.md");
  const handoff = read("references/build-handoff.md");
  const designerSkill = fs.readFileSync(path.join(DESIGNER_SKILL_ROOT, "SKILL.md"), "utf8");
  const designerAgent = fs.readFileSync(DESIGNER_AGENT, "utf8");

  assert.match(skill, /artifact-designer/);
  assert.match(stage2, /references\/build-handoff\.md/);
  assert.match(stage2, /delegate/i);
  assert.doesNotMatch(stage2, /continue building in the same task/i);

  assert.match(handoff, /Claude Code/);
  assert.match(handoff, /Codex/);
  assert.match(handoff, /write-capable worker/i);
  assert.match(handoff, /Do not build in the parent/i);
  assert.match(handoff, /spec path/i);
  assert.match(handoff, /output target/i);
  assert.match(handoff, /craft references/i);
  assert.match(handoff, /absolute paths/i);

  assert.match(designerSkill, /^name:\s*artifact-designer$/m);
  assert.match(designerSkill, /locked/);
  assert.match(designerSkill, /guided/);
  assert.match(designerSkill, /open/);
  assert.match(designerSkill, /DESIGN\.md/);
  assert.match(designerSkill, /render/i);
  assert.match(designerSkill, /visual inspection/i);
  assert.match(designerSkill, /Do not edit `spec\.md`/);
  assert.match(designerSkill, /craft.reference/i);

  assert.match(designerAgent, /^name:\s*artifact-designer$/m);
  assert.match(designerAgent, /^skills:\s*\n\s+- artifact-designer$/m);
  assert.match(designerAgent, /^disallowedTools:\s*Agent, Task$/m);
  assert.doesNotMatch(designerAgent, /^tools:/m);
});

test("IBM DESIGN.md is an eval-only snapshot and runtime Figma fixtures are gone", () => {
  const runtimeFigma = path.join(SKILL_ROOT, "references", "fixtures", "figma");
  const runtimeFigmaFiles = fs.existsSync(runtimeFigma) ? fs.readdirSync(runtimeFigma) : [];
  assert.deepEqual(runtimeFigmaFiles, [], "runtime Figma fixture files still exist");

  if (!fs.existsSync(IBM_FIXTURE_ROOT)) {
    assert.equal(
      fs.existsSync(path.join(ROOT, "eval")),
      false,
      "private checkout is missing the eval-only IBM fixture"
    );
    return;
  }

  const designMd = fs.readFileSync(path.join(IBM_FIXTURE_ROOT, "DESIGN.md"), "utf8");
  const source = fs.readFileSync(path.join(IBM_FIXTURE_ROOT, "SOURCE.md"), "utf8");
  assert.match(designMd, /^version:\s*alpha$/m);
  assert.match(designMd, /^name:\s*IBM-design-analysis$/m);
  assert.match(designMd, /^## Overview$/m);
  assert.match(designMd, /^## Colors$/m);
  assert.match(designMd, /^## Typography$/m);
  assert.match(designMd, /^## Layout$/m);
  assert.match(source, /VoltAgent\/awesome-design-md/);
  assert.match(source, /[0-9a-f]{40}/);
  assert.match(source, /MIT/);
  assert.match(source, /eval-only/i);
});

test("validator accepts a complete build contract", () => {
  const result = validate(VALID_SPEC);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /OK: document plan contract valid/);
});

test("validator rejects each missing contract block", () => {
  const headings = [
    "Document Model",
    "Evidence",
    "Structure",
    "Anchors",
    "Design Direction",
    "Build Contract",
    "Acceptance Tests"
  ];

  for (const [index, heading] of headings.entries()) {
    const next = headings[index + 1];
    const end = next ? `(?=## ${next})` : "$";
    const malformed = VALID_SPEC.replace(new RegExp(`## ${heading}\\n[\\s\\S]*?${end}`), "");
    const result = validate(malformed);
    assert.notEqual(result.status, 0, `${heading} was not required`);
    assert.match(result.stdout, new RegExp(`block missing: ${heading}`));
  }
});

test("validator rejects broken source and anchor references", () => {
  const missingSource = validate(VALID_SPEC.replace("- evidence: S1", "- evidence: S9"));
  assert.notEqual(missingSource.status, 0);
  assert.match(missingSource.stdout, /plan references missing source: S9/);

  const missingAnchor = validate(VALID_SPEC.replace("  - anchor: A1", "  - anchor: A9"));
  assert.notEqual(missingAnchor.status, 0);
  assert.match(missingAnchor.stdout, /Structure references missing anchor: A9/);
});

test("validator rejects duplicated or reordered contract blocks", () => {
  const duplicated = validate(`${VALID_SPEC}\n## Evidence\n\n- established: duplicate\n`);
  assert.notEqual(duplicated.status, 0);
  assert.match(duplicated.stdout, /block duplicated: Evidence/);

  const reordered = validate(VALID_SPEC
    .replace("## Document Model", "## TEMP")
    .replace("## Evidence", "## Document Model")
    .replace("## TEMP", "## Evidence"));
  assert.notEqual(reordered.status, 0);
  assert.match(reordered.stdout, /block out of order:/);
});

test("validator enforces per-anchor fields and unit references", () => {
  // A1 gains a duplicate caveat, A2 has none — a global field count would still pass.
  // A2 is also referenced by no unit.
  const twoAnchors = VALID_SPEC
    .replace(
      "- caveat: deployment cost remains estimated",
      "- caveat: deployment cost remains estimated\n- caveat: duplicated caveat line"
    )
    .replace(
      "## Design Direction",
      [
        "### A2 Cost table",
        "",
        "- reader question: what does each route cost?",
        "- evidence: S1 cost fields",
        "- selected form: table",
        "- takeaway: route B costs more to deploy",
        "",
        "## Design Direction"
      ].join("\n")
    );
  const result = validate(twoAnchors);
  assert.notEqual(result.status, 0);
  assert.match(result.stdout, /Anchors A2 missing field: caveat/);
  assert.match(result.stdout, /anchor not referenced by any unit: A2/);
});

test("validator permits an intentionally prose-only plan", () => {
  const proseOnly = VALID_SPEC.replace(
    /### A1 Route matrix[\s\S]*?(?=## Design Direction)/,
    "- none: the decision is fully expressed by the short recommendation and evidence list\n\n"
  ).replace("  - anchor: A1", "  - anchor: prose");
  const result = validate(proseOnly);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

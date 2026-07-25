import assert from "node:assert/strict";
import test from "node:test";

import { shouldReuseBroker } from "../../../marketplace/hukuhaka-codex/scripts/lib/broker-lifecycle.mjs";

const CURRENT = { codexVersion: "codex-cli 0.144.1" };

test("reuses a reachable broker with the current Codex version", () => {
  const existing = { runtimeFingerprint: CURRENT };
  assert.equal(shouldReuseBroker(existing, true, CURRENT), true);
});

test("recycles a reachable legacy broker without a fingerprint", () => {
  assert.equal(shouldReuseBroker({}, true, CURRENT), false);
});

test("recycles a reachable broker from a different Codex version", () => {
  const existing = { runtimeFingerprint: { codexVersion: "codex-cli 0.143.0" } };
  assert.equal(shouldReuseBroker(existing, true, CURRENT), false);
});

test("keeps a reachable broker when the current Codex version cannot be read", () => {
  const existing = { runtimeFingerprint: { codexVersion: "codex-cli 0.143.0" } };
  assert.equal(shouldReuseBroker(existing, true, null), true);
});

test("recycles an unreachable broker regardless of version", () => {
  const existing = { runtimeFingerprint: CURRENT };
  assert.equal(shouldReuseBroker(existing, false, CURRENT), false);
});

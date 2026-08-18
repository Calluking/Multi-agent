import assert from "node:assert/strict";
import test from "node:test";
import { parseMechanismSwitches } from "../src/config.js";

test("mechanisms can be independently enabled", () => {
  assert.deepEqual(parseMechanismSwitches("dependency"), {
    dependency: true, codomain: false, testing: false,
  });
  assert.deepEqual(parseMechanismSwitches("codomain"), {
    dependency: false, codomain: true, testing: false,
  });
  assert.deepEqual(parseMechanismSwitches("testing"), {
    dependency: false, codomain: false, testing: true,
  });
  assert.deepEqual(parseMechanismSwitches(""), {
    dependency: false, codomain: false, testing: false,
  });
  assert.deepEqual(parseMechanismSwitches(), {
    dependency: true, codomain: true, testing: true,
  });
});

test("unknown mechanism names are rejected", () => {
  assert.throws(() => parseMechanismSwitches("dependency,benchmark-adapter"), /unknown memory mechanism/);
});

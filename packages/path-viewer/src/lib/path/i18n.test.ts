import assert from "node:assert/strict";

import { copyFor, direction, LOCALES, reasonLabel, stateLabel, typeLabel } from "./i18n.ts";

export function testDirectionFollowsLocale() {
  assert.equal(direction("he"), "rtl");
  assert.equal(direction("ar"), "rtl");
  assert.equal(direction("en"), "ltr");
}

export function testEveryLocaleHasTheQuietShellCopy() {
  for (const { id } of LOCALES) {
    const copy = copyFor(id);
    assert.ok(copy.settings);
    assert.ok(copy.quality);
    assert.ok(copy.qualityNote);
    assert.ok(copy.view);
    assert.ok(copy.editing);
    assert.ok(copy.map);
    assert.ok(copy.list);
    assert.ok(copy.stage(1));
    assert.ok(copy.milliseconds(40));
    assert.ok(copy.masteredCount(1, 3));
    assert.ok(typeLabel(id, "explanation"));
    assert.ok(typeLabel(id, "practice"));
    assert.ok(typeLabel(id, "assessment"));
    assert.ok(typeLabel(id, "experience"));
    assert.ok(stateLabel(id, "not_started"));
    assert.ok(stateLabel(id, "needs_remediation"));
    assert.ok(reasonLabel(id, "branch"));
    assert.ok(reasonLabel(id, "retry"));
  }
}

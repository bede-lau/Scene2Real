import test from 'node:test';
import assert from 'node:assert/strict';
import { runTraining } from '../static/training-model.mjs';
import { fireEffect, fireIntensity, modelEndpoint, poseBlend, sprayPoint } from '../static/training-g1-motion.mjs';
import { readFileSync } from 'node:fs';

test('the browser demo fits examples and measures held-out positions', () => {
  const result = runTraining({ trainingCases: 24, seed: 7 });
  assert.equal(result.trainingCases, 24);
  assert.equal(result.test.length, 9);
  assert.ok(result.learnedMean < result.baselineMean);
  assert.ok(result.test.every(row => Number.isFinite(row.prediction) && Number.isFinite(row.learnedError)));
  assert.equal(result.steps.length, 25);
  assert.deepEqual(result.steps[0], { count: 0, slope: 0, intercept: 0 });
  assert.equal(result.steps[1].intercept, result.teachingExamples[0].angle);
  assert.equal(result.steps[24].slope, result.slope);
  assert.equal(result.steps[24].intercept, result.intercept);
  const [a, b] = result.teachingExamples;
  const expectedSlope = (b.angle - a.angle) / (b.lateral - a.lateral);
  assert.ok(Math.abs(result.steps[2].slope - expectedSlope) < 1e-9);
  assert.ok(result.teachingExamples.every(example => result.test.every(target => Math.abs(example.lateral - target.lateral) >= 1e-10)));
  assert.deepEqual(result, runTraining({ trainingCases: 24, seed: 7 }));
  assert.notEqual(result.slope, runTraining({ trainingCases: 24, seed: 8 }).slope);
});

test('the browser demo bounds inputs', () => {
  for (const trainingCases of [0, 7, 129, 3.5, NaN]) assert.throws(() => runTraining({ trainingCases }), RangeError);
  for (const seed of [-1, 2147483648, 1.5]) assert.throws(() => runTraining({ seed }), RangeError);
});

test('illustrative fire tracks accurate training steps deterministically', () => {
  const target = { lateral: 1, expected: 10 };
  const steps = [0, 6, 7, 10, 14, 11, 9].map(intercept => ({ slope: 0, intercept }));
  assert.deepEqual(steps.map((_, i) => fireIntensity(steps, target, i)), [1, 1, 0.75, 0.5, 0.5, 0.25, 0]);
  assert.equal(fireIntensity(steps, { lateral: 1, expected: -20 }, 6), 1);
  assert.equal(fireIntensity(steps, target, 2), 0.75);
  assert.equal(fireIntensity(steps, target, 100), 0);
  assert.deepEqual(fireEffect(steps, target, 5), { fire: 0.25, smoke: 0, spraying: true });
  assert.deepEqual(fireEffect(steps, target, 6), { fire: 0, smoke: 1, spraying: false });
  const extended = [...steps, ...Array.from({ length: 5 }, () => ({ slope: 0, intercept: 10 }))];
  assert.equal(fireEffect(extended, target, 7).smoke, 0.8);
  assert.deepEqual(fireEffect(extended, target, 11), { fire: 0, smoke: 0, spraying: false });
  assert.deepEqual(fireEffect(steps, target, 1), { fire: 1, smoke: 0, spraying: true });
});

test('G1 visual interpolation and aim guides follow the synthetic error', () => {
  assert.deepEqual(poseBlend(0), { side: 'right', weight: 0 });
  assert.equal(poseBlend(-8).side, 'left');
  assert.equal(poseBlend(8).side, 'right');
  assert.equal(poseBlend(100).weight, 1);
  const origin = [0.5, -0.1, 0.95], target = [2.7, -0.84, 0.9];
  const aligned = modelEndpoint(origin, target, 17, 17);
  for (let i = 0; i < 3; i++) assert.ok(Math.abs(aligned[i] - target[i]) < 1e-12);
  assert.ok(modelEndpoint(origin, target, 20, 17)[1] < target[1]);
  assert.deepEqual(sprayPoint(origin, target, 0, 64, 0), origin);
  const halfway = sprayPoint(origin, target, 32, 64, 0);
  assert.ok(halfway.every(Number.isFinite));
  assert.ok(Math.abs(halfway[0] - (origin[0] + target[0]) / 2) < 0.04);
  assert.notDeepEqual(halfway, sprayPoint(origin, target, 32, 64, 0.2));
});

test('the compact G1 asset contains the licensed meshes and aligned poses', () => {
  const path = new URL('../static/assets/unitree_g1/training-g1.json', import.meta.url);
  const bytes = readFileSync(path);
  assert.ok(bytes.length < 1200000);
  const asset = JSON.parse(bytes);
  assert.equal(asset.schema, 'scene2real-training-g1-visual-v1');
  assert.equal(asset.license, '/assets/unitree_g1/LICENSE');
  assert.ok(asset.geometries.length > 30);
  for (const name of ['left', 'center', 'right']) {
    assert.equal(asset.poses[name].geoms.length, asset.geometries.length);
    assert.equal(asset.poses[name].nozzle.length, 3);
    for (const transform of asset.poses[name].geoms) assert.equal(transform.length, 7);
  }
  assert.notDeepEqual(asset.poses.left.nozzle, asset.poses.right.nozzle);
});

test('reduced motion shows the final fit and allows explicit replay and scrubbing', async () => {
  const previous = { document: globalThis.document, matchMedia: globalThis.matchMedia,
    setInterval: globalThis.setInterval, clearInterval: globalThis.clearInterval };
  const elements = new Map();
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      value: '', textContent: '', disabled: false, hidden: false, handlers: {}, attributes: {},
      addEventListener(type, handler) { this.handlers[type] = handler; },
      setAttribute(name, value) { this.attributes[name] = value; },
      reportValidity() { return true; }, scrollIntoView() {}, replaceChildren() {}, append() {},
    });
    return elements.get(selector);
  }
  let scheduled = 0, cancelled = 0;
  try {
    globalThis.document = { querySelector: element, createElement: () => ({ textContent: '', append() {} }) };
    globalThis.matchMedia = () => ({ matches: true });
    globalThis.setInterval = () => { scheduled++; return 1; };
    globalThis.clearInterval = () => { cancelled++; };
    element('#training-cases').value = '24';
    element('#seed').value = '7';
    element('#target-select').value = '8';
    await import('../static/training-demo.mjs?reduced-motion-test');
    element('#training-form').handlers.submit({ preventDefault() {} });
    assert.equal(scheduled, 0);
    assert.equal(element('#status').textContent, 'Training complete');
    assert.equal(element('#timeline').value, '24');
    assert.equal(element('#timeline').attributes['aria-valuetext'], '24 of 24 examples');
    assert.equal(element('#model-ray').attributes.visibility, 'hidden');
    assert.match(element('#scene-description').textContent, /fire out; spray stopped/);
    element('#playback-button').handlers.click();
    assert.equal(scheduled, 1);
    element('#timeline').handlers.input({ target: { value: '1' } });
    assert.equal(cancelled, 1);
    assert.equal(element('#step-count').textContent, '1 / 24 examples');
    assert.equal(element('#model-ray').attributes.visibility, 'visible');
    assert.equal(element('#smoke-marker').attributes.opacity, 0);
    element('#target-select').value = '0';
    element('#target-select').handlers.change();
    assert.equal(element('#teacher-angle').textContent, '-17.28°');
  } finally {
    Object.assign(globalThis, previous);
  }
});

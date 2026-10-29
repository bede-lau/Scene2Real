import test from 'node:test';
import assert from 'node:assert/strict';
import { runTraining } from '../static/training-model.mjs';

test('the browser demo fits examples and measures held-out positions', () => {
  const result = runTraining({ trainingCases: 24, seed: 7 });
  assert.equal(result.trainingCases, 24);
  assert.equal(result.test.length, 9);
  assert.ok(result.learnedMean < result.baselineMean);
  assert.ok(result.test.every(row => Number.isFinite(row.prediction) && Number.isFinite(row.learnedError)));
  assert.deepEqual(result, runTraining({ trainingCases: 24, seed: 7 }));
  assert.notEqual(result.slope, runTraining({ trainingCases: 24, seed: 8 }).slope);
});

test('the browser demo bounds inputs', () => {
  for (const trainingCases of [0, 7, 129, 3.5, NaN]) assert.throws(() => runTraining({ trainingCases }), RangeError);
  for (const seed of [-1, 2147483648, 1.5]) assert.throws(() => runTraining({ seed }), RangeError);
});

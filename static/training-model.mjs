// A deliberately small 2D teaching exercise. It does not run a robot simulator.
const DISTANCE_METRES = 2.7;
const DEG = 180 / Math.PI;
const TEST_POSITIONS = [-0.84, -0.63, -0.42, -0.21, 0, 0.21, 0.42, 0.63, 0.84];

function randomGenerator(seed) {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

export function runTraining({ trainingCases = 24, seed = 7 } = {}) {
  if (!Number.isInteger(trainingCases) || trainingCases < 8 || trainingCases > 128) throw new RangeError('Choose 8 to 128 training cases.');
  if (!Number.isInteger(seed) || seed < 0 || seed > 2147483647) throw new RangeError('Choose a valid seed.');
  const random = randomGenerator(seed);
  const train = Array.from({ length: trainingCases }, () => {
    let lateral;
    do { lateral = random() * 1.8 - 0.9; }
    while (TEST_POSITIONS.some(position => Math.abs(position - lateral) < 1e-10));
    return { lateral, angle: Math.atan2(lateral, DISTANCE_METRES) * DEG };
  });
  const meanX = train.reduce((sum, row) => sum + row.lateral, 0) / train.length;
  const meanY = train.reduce((sum, row) => sum + row.angle, 0) / train.length;
  const variance = train.reduce((sum, row) => sum + (row.lateral - meanX) ** 2, 0);
  if (variance < 1e-12) throw new Error('The generated examples do not span enough positions.');
  const slope = train.reduce((sum, row) => sum + (row.lateral - meanX) * (row.angle - meanY), 0) / variance;
  const intercept = meanY - slope * meanX;
  // These fixed positions are held out of the generated teaching examples.
  const test = TEST_POSITIONS.map(lateral => {
    const expected = Math.atan2(lateral, DISTANCE_METRES) * DEG;
    const prediction = slope * lateral + intercept;
    return { lateral, expected, prediction, baselineError: Math.abs(expected), learnedError: Math.abs(prediction - expected) };
  });
  const mean = key => test.reduce((sum, row) => sum + row[key], 0) / test.length;
  return { trainingCases, seed, test, slope, intercept, baselineMean: mean('baselineError'), learnedMean: mean('learnedError') };
}

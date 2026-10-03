const assert = require('node:assert/strict');
const fs = require('node:fs');
const {classify} = require('../web/inference.js');
const model = JSON.parse(fs.readFileSync('artifacts/model.json','utf8'));
const cases = JSON.parse(fs.readFileSync('tests/inference_cases.json','utf8'));
let comparisons=0;
for(const example of cases){
  const actual=classify(model,example.text);
  for(const target of ['product','issue']){
    assert.equal(actual[target].label,example.expected[target].label);
    assert.ok(Math.abs(actual[target].confidence-example.expected[target].confidence)<1e-7);
    assert.equal(actual[target].review,example.expected[target].review);
    comparisons++;
  }
}
assert.throws(()=>classify(model,'no'),/five words/);
assert.throws(()=>classify(model,'qqzv qqzv qqzv qqzv qqzv'),/recognized vocabulary/);
console.log(`${comparisons} browser/Python model comparisons passed; invalid inputs rejected.`);

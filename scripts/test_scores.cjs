const assert=require('node:assert/strict');
const fs=require('node:fs');
const {calculate,rank}=require('../dist/scoring.js');
const data=JSON.parse(fs.readFileSync(__dirname+'/../dist/data.json','utf8'));
const weights=data.scoring.presets[0].weights;
assert.deepEqual(calculate([0,0,0,0,0,0],weights),{components:[0,0,0,0,0,0],total:0,covered:0});
assert.equal(calculate([5,5,5,5,5,5],weights).total,100);
assert.throws(()=>calculate([1,2],weights));
assert.throws(()=>calculate([0,0,0,0,0,6],weights));
assert.equal(data.items.filter(r=>r.scorecard).length,125);
for(const preset of data.scoring.presets){
  const ranks=rank(data.items,preset.weights);
  assert.equal(Object.keys(ranks).length,91);
  for(const item of data.items){
    const score=calculate(item.scorecard.levels,preset.weights);
    assert(score.total>=0&&score.total<=80);
    assert.equal(item.scorecard.reasons.length,6);
    if(preset.id==='balanced'){
      assert.equal(score.total,item.scorecard.total,item.id);
      assert.equal(ranks[item.id]?.position??null,item.scorecard.rank,item.id);
      assert.equal(ranks[item.id]?.tied??false,item.scorecard.tied,item.id);
    }
    if(item.businessStatus!=='confirmed')assert.equal(ranks[item.id],undefined);
  }
}
const fixture=[
  {id:'a',businessStatus:'confirmed',scorecard:{levels:[2,0,0,0,0,0]}},
  {id:'b',businessStatus:'confirmed',scorecard:{levels:[2,0,0,0,0,0]}},
  {id:'c',businessStatus:'confirmed',scorecard:{levels:[1,0,0,0,0,0]}},
  {id:'p',businessStatus:'platform',scorecard:{levels:[4,4,4,4,4,4]}},
];
const ties=rank(fixture,weights);
assert.deepEqual(ties,{a:{position:1,tied:true},b:{position:1,tied:true},c:{position:3,tied:false}});
const before=calculate([4,1,1,1,1,1],weights).total;
const emphasis=calculate([4,1,1,1,1,1],data.scoring.presets[1].weights).total;
assert(emphasis>before);
console.log('PASS: 125 scorecards; six components; all presets; 91 eligible ranks; ties; missing data; platform isolation.');

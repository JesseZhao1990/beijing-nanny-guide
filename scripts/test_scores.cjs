'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const {score,eligible,compare,rank}=require('../dist/scoring.js');
const data=JSON.parse(fs.readFileSync(__dirname+'/../dist/data.json','utf8'));
assert.equal(data.scoring.version,'2.0');assert.equal(data.items.length,125);
assert.deepEqual(data.scoring.presets.map(p=>p.weights),[[60,15,10,5,5,5]]);
const ranks=rank(data.items),sources=data.scoring.officialSources;
for(const r of data.items){
 const s=score(r),g=r.officialSelection;
 assert.equal(s.total,r.scorecard.total,r.id);assert.deepEqual(s.components,r.scorecard.components);
 assert(s.total>=0&&s.total<=92,r.id);assert.equal(r.scorecard.reasons.length,6);
 assert.equal(ranks[r.id]?.position??null,r.scorecard.rank,r.id);
 assert.equal(ranks[r.id]?.tied??false,r.scorecard.tied,r.id);
 assert.equal(g.points,Math.max(0,...g.matches.map(m=>m.points)),'recognitions must not stack');
 for(const m of g.matches){
  const source=sources.find(x=>x.sourceId===m.sourceId);assert(source,m.sourceId);
  assert(source.companies.includes(m.listedCompany),r.id+' entity must exist in source');
  if(m.recordType.startsWith('employee')){assert(m.points<=15);assert(/历史|已过/.test(m.validity));}
 }
 if(eligible(r)){assert.equal(g.points,60);assert.equal(g.identityGate,'pass');assert.equal(r.businessStatus,'confirmed');}
 else assert.equal(ranks[r.id],undefined,r.id);
 if(g.identityGate==='hold')assert.notEqual(g.group,'official');
}
const obscure=data.items.find(r=>r.name==='找个保姆');
assert.equal(obscure.officialSelection.group,'identity');assert(!eligible(obscure));assert.equal(obscure.officialSelection.points,0);
const jd=data.items.find(r=>r.name==='京东家政');assert.equal(jd.officialSelection.points,60);assert(!eligible(jd));
assert.equal(data.items.find(r=>r.id==='new-gov-hemeijia').officialSelection.group,'business');
const fixture=(id,group,points,levels=[0,0,0,0,0])=>({id,businessStatus:'confirmed',officialSelection:{group,points,identityGate:group==='identity'?'hold':'pass'},scorecard:{levels:[points/12,...levels]}});
const a=fixture('a','official',60),b=fixture('b','official',60),c=fixture('c','official',60,[1,0,0,0,0]);
assert.deepEqual(rank([a,b,c]),{c:{position:1,tied:false},a:{position:2,tied:true},b:{position:2,tied:true}});
assert(compare(a,fixture('unknown','identity',0,[5,5,5,5,5]))<0);
assert(compare(fixture('history','historical',10),fixture('supplement','supplement',0,[5,5,5,5,5]))<0);
assert.equal(score(fixture('none','supplement',0)).total,0);
console.log('PASS: 125 government comparisons; identity/business gates; source/entity matches; expired awards; no stacking; government-first order; ties; JD and obscure-brand isolation.');

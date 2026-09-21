'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root=__dirname+'/..',data=JSON.parse(fs.readFileSync(root+'/dist/data.json','utf8'));
const context=vm.createContext({URL,Map});
vm.runInContext(fs.readFileSync(root+'/dist/complaints.js','utf8'),context);
const cases=r=>context.publicCases(r);
assert.equal(data.items.length,125);
assert.equal(data.complaintReview.webQueries,511);
assert.equal(data.complaintReview.govQueries,131);
let web=0,gov=0,detail=0;
for(const r of data.items){
 assert.equal(r.complaintAudit.id,r.id);assert(r.complaintAudit.queries.length>=3,r.id);
 web+=r.complaintAudit.queries.length;gov+=r.governmentAudit.queries.length;detail+=r.governmentAudit.cases.length;
 const merged=cases(r);
 for(const c of merged){assert(c.id,r.id+' missing case id');assert(/^https?:\/\//.test(c.url),c.url);assert(c.resolution,r.id+' missing resolution');}
 const govcases=merged.filter(c=>c.platform==='12315官方公示');
 assert.equal(govcases.length,r.governmentAudit.cases.length,r.id+' lost official cases');
 for(const c of [...r.complaintAudit.cases,...r.governmentAudit.cases])assert(c.complaintUpdate);
 for(const c of r.complaintAudit.cases){
  if(c.existingCaseId)assert.equal(merged.filter(x=>x.id===c.existingCaseId).length,1,r.id+' duplicate update');
 }
}
assert.equal(web,511);assert.equal(gov,131);assert.equal(detail,16);
for(const id of ['agency-55','agency-56'])assert.equal(data.items.find(r=>r.id===id).governmentAudit.queries.length,0);
const tang=cases(data.items.find(r=>r.id==='agency-21')).filter(c=>c.id==='R009');
assert.equal(tang.length,1);assert(tang[0].resolution.includes('自动'));
const angel=cases(data.items.find(r=>r.id==='agency-52')).find(c=>c.id==='R014');
assert(angel.response.includes('2024-11-19'));assert(angel.limits.includes('未确认同一订单'));
const fixture={name:'测试',cases:[{id:'R',url:'https://tousu.sina.cn/complaint/view/123/',resolution:'旧'}],complaintAudit:{cases:[{id:'R',existingCaseId:'R',url:'https://tousu.sina.com.cn/complaint/view/123',resolution:'新'}]},governmentAudit:{cases:[{id:'G1',sourceKey:'gov:1',url:'https://tsgs.12315.cn/#/viewport'},{id:'G2',sourceKey:'gov:2',url:'https://tsgs.12315.cn/#/viewport'}]}};
assert.equal(cases(fixture).length,3);assert.equal(cases(fixture)[0].resolution,'新');
console.log('PASS: 125 audits, 511 web queries, 131 official queries, 16 official details; update deduplication; result boundaries; channel isolation.');

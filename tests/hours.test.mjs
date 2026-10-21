import test from 'node:test';
import assert from 'node:assert/strict';
import {openingStatus,hoursForDay,torontoTime,isTorontoWallTime,passes,haversine} from '../site/logic.mjs';
const now=Date.parse('2026-10-20T16:00:00Z');
const point=(day,hour,minute=0)=>({day,hour,minute});
const place=periods=>({google:{fetched_at:'2026-10-20T00:00:00Z',expires_at:'2026-10-22T00:00:00Z',data:{regularOpeningHours:{periods}}}});
const ordinary=place([{open:point(2,10),close:point(2,20)}]);
test('ordinary hours include opening, exclude closing',()=>{
  assert.equal(openingStatus(ordinary,'2026-10-20T10:00',now),'open');
  assert.equal(openingStatus(ordinary,'2026-10-20T19:59',now),'open');
  assert.equal(openingStatus(ordinary,'2026-10-20T20:00',now),'closed');
});
test('18:00–02:00 carries into next day',()=>{
  const p=place([{open:point(2,18),close:point(3,2)}]);
  assert.equal(openingStatus(p,'2026-10-20T19:00',now),'open');
  assert.equal(openingStatus(p,'2026-10-21T01:59',now),'open');
  assert.equal(openingStatus(p,'2026-10-21T02:00',now),'closed');
  assert.match(hoursForDay(p,'2026-10-21T12:00',now),/昨晚延续/);
});
test('Saturday across Sunday weekly boundary',()=>{
  const p=place([{open:point(6,18),close:point(0,2)}]);
  assert.equal(openingStatus(p,'2026-10-25T01:00',now),'open');
});
test('full closed day',()=>{
  assert.equal(openingStatus(ordinary,'2026-10-21T12:00',now),'closed');
  assert.equal(hoursForDay(ordinary,'2026-10-21T12:00',now),'全天休息');
});
test('missing hours are unknown, explicit empty periods are closed',()=>{
  assert.equal(openingStatus({},'2026-10-20T12:00',now),'unknown');
  assert.equal(openingStatus(place([]),'2026-10-20T12:00',now),'closed');
});
test('always open encoding',()=>assert.equal(openingStatus(place([{open:point(0,0)}]),'2026-10-20T03:00',now),'open'));
test('split shifts and midday closure',()=>{
  const p=place([{open:point(2,10),close:point(2,14)},{open:point(2,17),close:point(2,22)}]);
  assert.equal(openingStatus(p,'2026-10-20T15:00',now),'closed');
  assert.equal(openingStatus(p,'2026-10-20T18:00',now),'open');
});
test('expired Google data does not filter as current',()=>{
  assert.equal(openingStatus(ordinary,'2026-10-20T12:00',Date.parse('2026-10-23')),'unknown');
});
test('Toronto timezone independent of visitor zone and DST',()=>{
  assert.equal(torontoTime(new Date('2026-01-15T05:30:00Z')),'2026-01-15T00:30');
  assert.equal(torontoTime(new Date('2026-07-15T04:30:00Z')),'2026-07-15T00:30');
  assert.equal(isTorontoWallTime('2026-03-08T02:30'),false);
  assert.equal(isTorontoWallTime('2026-11-01T01:30'),true);
});
test('current exceptional closure overrides regular week',()=>{
  const p=structuredClone(ordinary);
  p.google.fetched_at='2026-10-20T16:00:00Z';
  p.google.data.currentOpeningHours={periods:[]};
  assert.equal(openingStatus(p,'2026-10-20T12:00',now),'closed');
  assert.equal(openingStatus(p,'2026-10-27T12:00',now),'open');
});
test('dated exceptional overnight periods',()=>{
  const p=structuredClone(ordinary);p.google.fetched_at='2026-10-20T16:00:00Z';
  p.google.data.currentOpeningHours={periods:[{open:{date:{year:2026,month:10,day:20},hour:18,minute:0},close:{date:{year:2026,month:10,day:21},hour:2,minute:0}}]};
  assert.equal(openingStatus(p,'2026-10-21T01:00',now),'open');
  assert.equal(openingStatus(p,'2026-10-21T03:00',now),'closed');
});
test('unknown is not zero, false or closed in filters',()=>{
  const f={spicy:'0',includeMissing:false};
  assert.equal(passes({spicy:null},f,now),false);
  assert.equal(passes({spicy:0},f,now),true);
  assert.equal(passes({spicy:null},{...f,includeMissing:true},now),true);
  assert.equal(passes({},{openOnly:true,time:'2026-10-20T12:00'},now),false);
});
test('distance and inactive distance filter',()=>{
  assert.equal(haversine({latitude:0,longitude:0},{latitude:0,longitude:0}),0);
  assert.equal(passes({},{maxDistance:'1',origin:{latitude:0,longitude:0}},now),false);
  assert.equal(passes({},{maxDistance:''},now),true);
});

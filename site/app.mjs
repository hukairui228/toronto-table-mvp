import {torontoTime,isTorontoWallTime,openingStatus,hoursForDay,haversine,passes,regionOf,liveGoogle,coordinatesOf} from './logic.mjs';
const $=id=>document.getElementById(id);
const originDefault={latitude:43.6629,longitude:-79.3957};
let origin={...originDefault}, places=[], config={}, loadError=false, tracker=null;
const priceLabels={PRICE_LEVEL_FREE:'免费',PRICE_LEVEL_INEXPENSIVE:'$',PRICE_LEVEL_MODERATE:'$$',PRICE_LEVEL_EXPENSIVE:'$$$',PRICE_LEVEL_VERY_EXPENSIVE:'$$$$'};
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
function safeLink(value) {try {const u=new URL(value);return u.protocol==='https:'?u.href:null;}catch{return null;}}
function track(name,event=false) {
  if(tracker && navigator.doNotTrack!=='1' && globalThis.goatcounter?.count) {
    globalThis.goatcounter.count({path:event?`filter-${name}`:'/toronto-table',title:event?'Filter use':'Toronto Table',event,referrer:'',no_session:true});
  }
}
function analytics() {
  const code=config.goatcounter_code;
  if(!/^[a-z0-9][a-z0-9-]{1,60}$/.test(code||'') || navigator.doNotTrack==='1') return;
  const start=/^\d{4}-\d{2}-\d{2}$/.test(config.test_start_date||'')?Date.parse(`${config.test_start_date}T00:00:00-04:00`):NaN;
  const localToday=torontoTime().slice(0,10);
  // Date-only comparison uses Toronto calendar days, independent of visitor timezone.
  if(!Number.isFinite(start)) return;
  const endDate=new Date(Date.parse(`${config.test_start_date}T12:00:00Z`)+(config.test_days||14)*86400000).toISOString().slice(0,10);
  if(localToday<config.test_start_date || localToday>=endDate) return;
  globalThis.goatcounter={no_onload:true,allow_local:false,allow_frame:false};
  const script=document.createElement('script');script.async=true;script.src='https://gc.zgo.at/count.js';
  script.dataset.goatcounter=`https://${code}.goatcounter.com/count`;
  script.onload=()=>{
    const original=globalThis.goatcounter.get_data;
    globalThis.goatcounter.get_data=vars=>{const data=original(vars);delete data.q;delete data.s;return data;};
    tracker=code;track('view');
  };document.head.append(script);
  $('analytics-status').textContent='· 两周匿名使用统计已启用';
}
function filters() {return {query:$('query').value.trim(),openOnly:$('open-only').checked,
  time:$('time-mode').value==='now'?torontoTime():$('custom-time').value,
  price:$('price').value,cuisine_detail:$('cuisine').value,scenario:$('scenario').value,spicy:$('spicy').value,
  region:$('region').value,maxDistance:$('distance').value,origin,includeMissing:$('include-missing').checked,
  includeUnknownHours:$('unknown-hours').checked,showSkipped:$('show-skipped').checked};}
function addNote(card,label,value,cls='') {
  const box=el('section',`human-note ${cls}`);box.append(el('span','source-label',label),el('p','',value||'未填'));card.append(box);
}
function card(place,index,f) {
  const node=el('article','place-card');const g=liveGoogle(place)?.data;
  const top=el('div','card-top');top.append(el('span','card-index',String(index+1).padStart(2,'0')));
  const status=openingStatus(place,f.time);top.append(el('span',`badge ${status}`,{open:'● 该时间营业',closed:'○ 该时间休息',unknown:'◌ 营业时间未填'}[status]));node.append(top,el('h3','',place.name));
  const meta=el('div','card-meta');meta.append(el('span','',place.cuisine_detail||'菜系未填'),el('span','','/'),el('span','',place.scenario?.join(' · ')||'场景未填'));node.append(meta,el('p','card-address',`清单地址：${place.address||'未填'}`));
  addNote(node,'我的评价',place.my_take);addNote(node,'列表作者备注',place.owner_note,'owner');
  const dish=el('dl','dish');dish.append(el('dt','','必点 · 手填'),el('dd','',place.best_dish||'未填'));node.append(dish);
  const details=el('dl','dish');details.append(el('dt','','人均 / 辣度 · 手填'),el('dd','',`${place.price_per_person_cad===null||place.price_per_person_cad===undefined?'人均未填':`CA$${place.price_per_person_cad}`} · ${place.spicy===null||place.spicy===undefined?'辣度未填':`辣度 ${place.spicy}/3`}`));node.append(details);
  const google=el('section','google-data');const label=el('span','source-label','Google 数据');label.append(el('span','google-attribution','Google Maps'));label.lastChild.setAttribute('translate','no');google.append(label);
  google.append(el('p','',`${g?.rating??'评分未填'}${g?.userRatingCount!==undefined?` · ${g.userRatingCount} 条评分`:''}　价位 ${priceLabels[g?.priceLevel]||'未填'}`));
  google.append(el('p','',`今天 ${hoursForDay(place)}`));
  google.append(el('p','',`区域 ${regionOf(g)||'未填'} · ${g?.formattedAddress||'Google 地址未填'}`));
  if(g?.regularOpeningHours && !g.currentOpeningHours) google.append(el('p','', '按常规周营业表判断，节假日需核实。'));
  for(const attr of g?.attributions||[]) {
    const url=safeLink(attr.providerUri);
    if(url){const a=el('a','',attr.provider||'数据提供方');a.href=url;a.target='_blank';a.rel='noopener noreferrer';google.append(a);}
    else if(attr.provider)google.append(el('p','',attr.provider));
  }
  node.append(google);const bottom=el('div','card-bottom');const distance=haversine(origin,coordinatesOf(place));
  bottom.append(el('span','',distance===null?'距离未填':`直线 ${distance.toFixed(1)} km`));
  const url=safeLink(place.maps_url)||`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.name)}&query_place_id=${encodeURIComponent(place.place_id)}`;
  const a=el('a','','去 Google Maps ↗');a.href=url;a.target='_blank';a.rel='noopener noreferrer';bottom.append(a);node.append(bottom);return node;
}
function render() {
  const f=filters();$('custom-time-wrap').hidden=$('time-mode').value!=='custom';
  if(!isTorontoWallTime(f.time)) {$('form-message').textContent='请选择有效的多伦多日期时间；夏令时跳过的时间无法选择。';return;}
  if($('form-message').textContent.startsWith('请选择有效'))$('form-message').textContent='';
  let matches=places.filter(p=>passes(p,f));
  if($('sort').value==='distance')matches=matches.map((p,i)=>({p,i,d:haversine(origin,coordinatesOf(p))??Infinity})).sort((a,b)=>a.d-b.d||a.i-b.i).map(x=>x.p);
  $('result-count').textContent=`${matches.length} / ${places.length}`;
  $('result-context').textContent=`${f.time.replace('T',' ')} · America/Toronto`;
  $('cards').replaceChildren(...matches.map((p,i)=>card(p,i,f)));
  $('empty').hidden=matches.length>0;$('clear-empty').hidden=!places.length;
  $('empty-title').textContent=loadError?'食单暂时无法读取':places.length?'这次还没找到合适的':'食单正在准备中';
  $('empty-description').textContent=loadError?'请刷新重试。若仍失败，检查 data.json 是否成功部署。':places.length?'试试放宽距离、取消营业筛选，或打开“包含未填”。':'店铺清单尚未导入。这里会保留原作者的备注，等你补上自己的必点与评价。';
  const unavailable=places.filter(p=>!liveGoogle(p)).length;
  $('data-notice').hidden=!unavailable;
  $('data-notice').textContent=`${unavailable} 家的 Google 数据缺失或已过期，显示为“未填”。开启价位、区域、距离或营业筛选可能将它们排除；出发前请在 Google Maps 核实。`;
}
function reset() { $('filters').reset();origin={...originDefault};$('origin-label').textContent='UofT St. George · 近似校区中心';$('form-message').textContent='';$('custom-time').value=torontoTime();render(); }
const filterNames={query:'search','time-mode':'time','custom-time':'time',price:'price',cuisine:'cuisine',scenario:'scenario',spicy:'spicy',region:'region',distance:'distance',sort:'sort','open-only':'hours','include-missing':'include-missing','unknown-hours':'unknown-hours','show-skipped':'skipped'};
let typingTimer;
$('filters').addEventListener('submit',e=>e.preventDefault());
$('filters').addEventListener('input',e=>{if(e.target.id==='query'){clearTimeout(typingTimer);typingTimer=setTimeout(()=>{render();track('search',true);},350);}});
$('filters').addEventListener('change',e=>{if(filterNames[e.target.id]&&e.target.id!=='query'){render();track(filterNames[e.target.id],true);}});
$('filters').addEventListener('reset',()=>setTimeout(()=>{origin={...originDefault};$('origin-label').textContent='UofT St. George · 近似校区中心';$('form-message').textContent='';$('custom-time').value=torontoTime();render();},0));
$('clear-empty').addEventListener('click',()=>{reset();track('reset',true);});
$('apply-origin').addEventListener('click',()=>{
  const lat=$('latitude').value,lng=$('longitude').value;
  if(!lat||!lng||!$('latitude').checkValidity()||!$('longitude').checkValidity()) {$('form-message').textContent='请输入有效纬度（-90–90）和经度（-180–180）。';return;}
  origin={latitude:Number(lat),longitude:Number(lng)};$('origin-label').textContent='自定起点';$('form-message').textContent='';render();track('origin',true);
});
$('locate').addEventListener('click',()=>{
  if(!navigator.geolocation){$('form-message').textContent='浏览器不支持定位，可以手动输入经纬度。';return;}
  $('locate').disabled=true;$('form-message').textContent='正在获取位置…';
  navigator.geolocation.getCurrentPosition(pos=>{origin={latitude:pos.coords.latitude,longitude:pos.coords.longitude};$('latitude').value=origin.latitude;$('longitude').value=origin.longitude;$('origin-label').textContent='我的当前位置';$('locate').disabled=false;$('form-message').textContent='';render();track('geolocation',true);},()=>{$('locate').disabled=false;$('form-message').textContent='未取得定位权限或暂时无法定位。可以手动输入经纬度。';},{enableHighAccuracy:false,timeout:10000,maximumAge:60000});
});
async function load() {
  const results=await Promise.allSettled([fetch('./data.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('data');return r.json();}),fetch('./config.json').then(r=>r.json())]);
  if(results[0].status==='fulfilled'&&Array.isArray(results[0].value.places)){
    places=results[0].value.places;
    $('updated-at').textContent=`食单更新：${torontoTime(new Date(results[0].value.generated_at)).replace('T',' ')} · 多伦多时间`;
  } else loadError=true;
  if(results[1].status==='fulfilled')config=results[1].value;
  $('source-author').textContent=config.source_author||'【待填写作者名】';
  if(safeLink(config.source_url))$('source-link').href=safeLink(config.source_url);
  const options=(id,values)=>{for(const v of [...new Set(values.filter(Boolean))].sort()){const o=el('option','',v);o.value=v;$(id).append(o);}};
  options('cuisine',places.map(p=>p.cuisine_detail));options('region',places.map(p=>regionOf(liveGoogle(p)?.data)));
  $('custom-time').value=torontoTime();$('today-label').textContent=torontoTime().slice(0,10)+' / TORONTO';render();analytics();
}
load().catch(()=>{$('form-message').textContent='页面加载出现问题，请刷新重试。';});
setInterval(render,30000);

export const ZONE = 'America/Toronto';
const DAY = 1440, WEEK = 7 * DAY;
const formatter = new Intl.DateTimeFormat('en-CA', {timeZone:ZONE, year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
export function torontoTime(instant = new Date()) {
  const p = Object.fromEntries(formatter.formatToParts(instant).map(x=>[x.type,x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
export function civil(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value || '');
  if (!match) return null;
  const [y,m,d,h,min] = match.slice(1).map(Number);
  const date = new Date(Date.UTC(y,m-1,d));
  if(date.getUTCFullYear()!==y || date.getUTCMonth()!==m-1 || date.getUTCDate()!==d || h>23 || min>59) return null;
  return {day:date.getUTCDay(), date:value.slice(0,10), minute:h*60+min, serial:date.getTime()/60000+h*60+min};
}
export function isTorontoWallTime(value) {
  const c = civil(value);
  if (!c) return false;
  // Toronto's UTC offsets are -04/-05. Reject spring-forward nonexistent local times.
  return [240,300].some(offset=>torontoTime(new Date((c.serial+offset)*60000))===value);
}
export function liveGoogle(place, now=Date.now()) {
  return place.google?.expires_at && Date.parse(place.google.expires_at)>now ? place.google : null;
}
export function coordinatesOf(place, now=Date.now()) {
  const record = place.coordinates;
  if (record?.expires_at && Date.parse(record.expires_at)>now) return record.location;
  return liveGoogle(place,now)?.data?.location || null;
}
function dateString(p) {
  const d = p?.date;
  return d?.year && d?.month && d?.day ? `${d.year}-${String(d.month).padStart(2,'0')}-${String(d.day).padStart(2,'0')}` : null;
}
function pointMinutes(p) {
  const h=p?.hour??0, m=p?.minute??0;
  return Number.isInteger(h)&&h>=0&&h<=23&&Number.isInteger(m)&&m>=0&&m<=59 ? h*60+m : null;
}
function selectHours(place, value, now) {
  const g=liveGoogle(place,now);
  if (!g) return {unknown:true};
  const data=g.data||{};
  if (['CLOSED_PERMANENTLY','CLOSED_TEMPORARILY'].includes(data.businessStatus)) return {closed:true};
  const c=civil(value);
  if(!c) return {unknown:true};
  const current=data.currentOpeningHours;
  const fetched=civil(torontoTime(new Date(g.fetched_at)));
  // The current response includes exceptions and covers fetch date + six days.
  if(current && fetched && c.serial-c.minute>=fetched.serial-fetched.minute && c.serial-c.minute<fetched.serial-fetched.minute+WEEK && Array.isArray(current.periods)) {
    return {hours:current,current:true,c};
  }
  if(!Array.isArray(data.regularOpeningHours?.periods)) return {unknown:true};
  return {hours:data.regularOpeningHours,current:false,c};
}
function intervals(selection) {
  const {hours,current,c}=selection;
  const result=[];
  for(const p of hours.periods) {
    const o=p.open, close=p.close, om=pointMinutes(o), cm=pointMinutes(close);
    if(!o || om===null) continue;
    const od=dateString(o), cd=dateString(close);
    if(current && od) {
      const start=civil(`${od}T00:00`).serial+om;
      if(!close) { result.push([start,Infinity]); continue; }
      if(cd && cm!==null) result.push([start,civil(`${cd}T00:00`).serial+cm]);
      continue;
    }
    if(!Number.isInteger(o.day)||o.day<0||o.day>6) continue;
    if(!close) {
      if(o.day===0 && om===0) return {always:true,items:[]};
      continue;
    }
    if(cm===null||!Number.isInteger(close.day)||close.day<0||close.day>6) continue;
    const start=o.day*DAY+om;
    let end=close.day*DAY+cm;
    if(end<=start) end+=WEEK;
    // Generate adjacent-week copies so Saturday -> Sunday and Monday carryover work.
    const weekStart=c.serial-c.minute-c.day*DAY;
    for(const shift of [-WEEK,0,WEEK]) result.push([weekStart+start+shift,weekStart+end+shift]);
  }
  return {items:result,always:false};
}
export function openingStatus(place,value=torontoTime(),now=Date.now()) {
  const s=selectHours(place,value,now);
  if(s.unknown) return 'unknown';
  if(s.closed) return 'closed';
  const data=intervals(s);
  if(data.always) return 'open';
  if(s.hours.periods.length && !data.items.length) return 'unknown';
  return data.items.some(([start,end])=>s.c.serial>=start && s.c.serial<end) ? 'open' : 'closed';
}
function clock(minutes) { return `${String(Math.floor(minutes/60)).padStart(2,'0')}:${String(minutes%60).padStart(2,'0')}`; }
export function hoursForDay(place,value=torontoTime(),now=Date.now()) {
  const s=selectHours(place,value,now);
  if(s.unknown) return '营业时间未填';
  if(s.closed) return '暂停营业';
  const data=intervals(s);
  if(data.always) return '24 小时营业';
  if(s.hours.periods.length && !data.items.length) return '营业时间未填';
  const midnight=s.c.serial-s.c.minute;
  const matches=data.items.filter(([a,b])=>a<midnight+DAY && b>midnight);
  if(!matches.length) return '全天休息';
  return matches.map(([a,b])=>{
    const left=a<midnight?'00:00':clock(a-midnight);
    const right=b===Infinity?'24:00':b>midnight+DAY?`次日 ${clock((b-midnight)%DAY)}`:clock(b-midnight);
    return `${left}–${right}${a<midnight?'（昨晚延续）':''}`;
  }).join(' / ');
}
export function haversine(a,b) {
  if(!a||!b||![a.latitude,a.longitude,b.latitude,b.longitude].every(Number.isFinite)) return null;
  const rad=n=>n*Math.PI/180, dlat=rad(b.latitude-a.latitude), dlng=rad(b.longitude-a.longitude);
  const x=Math.sin(dlat/2)**2+Math.cos(rad(a.latitude))*Math.cos(rad(b.latitude))*Math.sin(dlng/2)**2;
  return 6371*2*Math.atan2(Math.sqrt(Math.min(1,x)),Math.sqrt(Math.max(0,1-x)));
}
export function passes(place,f,now=Date.now()) {
  if(place.skip===true && !f.showSkipped) return false;
  if(f.query && ![place.name,place.address,place.best_dish,place.owner_note,place.my_take].filter(Boolean).join(' ').toLowerCase().includes(f.query.toLowerCase())) return false;
  const g=liveGoogle(place,now)?.data;
  if(f.openOnly) {
    const status=openingStatus(place,f.time,now);
    if(status!=='open' && !(status==='unknown'&&f.includeUnknownHours)) return false;
  }
  if(f.price && g?.priceLevel!==f.price) return false;
  if(f.region && regionOf(g)!==f.region) return false;
  for(const field of ['cuisine_detail','scenario','spicy']) {
    const selected=f[field];
    if(selected===''||selected===null||selected===undefined) continue;
    const actual=place[field];
    if(actual===null||actual===undefined||actual===''||(Array.isArray(actual)&&!actual.length)) {
      if(!f.includeMissing) return false;
    } else if(field==='scenario' ? !actual.includes(selected) : String(actual)!==String(selected)) return false;
  }
  if(f.maxDistance) {
    const dist=haversine(f.origin,coordinatesOf(place,now));
    if(dist===null||dist>Number(f.maxDistance)) return false;
  }
  return true;
}
export function regionOf(data) {
  for(const type of ['neighborhood','sublocality_level_1','sublocality']) {
    const component=data?.addressComponents?.find(c=>c.types?.includes(type));
    if(component) return component.longText||component.shortText||null;
  }
  return null;
}

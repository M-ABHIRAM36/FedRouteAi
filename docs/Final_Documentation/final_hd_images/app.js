/* FedRouteAI — HD figure generator (pure SVG, no dependencies).
   Renders 22 vector figures (4.1–7.1) matching the report's figure numbers/names,
   grounded in the real project structure, with 2-line captions and PNG/SVG export. */
"use strict";

const FONT = "'Segoe UI','Inter',system-ui,Arial,sans-serif";
const C = {
  ink:"#1f2937", sub:"#5b6472", line:"#8a97a8",
  blue:"#2563eb", blueF:"#e8f0fe", blueB:"#4f7ce0",
  teal:"#0d9488", tealF:"#e6f6f3", tealB:"#3bb0a0",
  amber:"#d97706", amberF:"#fdf1e0", amberB:"#e0a458",
  red:"#dc2626", redF:"#fdeaea", redB:"#e08a8a",
  slate:"#334155", slateF:"#eef2f7", slateB:"#b8c2d1",
  green:"#16a34a", greenF:"#e9f7ee", greenB:"#7cc79a",
  purpF:"#f0ebfb", purpB:"#a487d8", purp:"#7c3aed",
  grid:"#dfe5ee"
};
const CLASSES = ["normal","congestion","road_block","road_damage","construction","flood","accident","diversion"];

/* ---------- primitives ---------- */
const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
function T(x,y,str,o={}){
  const size=o.size||13, weight=o.weight||400, anchor=o.anchor||"middle", fill=o.fill||C.ink;
  const rot = o.rot ? ` transform="rotate(${o.rot} ${x} ${y})"` : "";
  return `<text x="${x}" y="${y}" font-family="${FONT}" font-size="${size}" font-weight="${weight}" text-anchor="${anchor}" fill="${fill}" dominant-baseline="middle"${rot}>${esc(str)}</text>`;
}
function box(x,y,w,h,title,sub,o={}){
  const fill=o.fill||C.blueF, stroke=o.stroke||C.blueB, rx=o.rx??10;
  let s=`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="1.6" filter="url(#sh)"/>`;
  const lines = sub ? (Array.isArray(sub)?sub:String(sub).split("\n")) : [];
  const cy=y+h/2, th=o.size||13.5, sh=o.subsize||11;
  if(!lines.length){ s+=T(x+w/2,cy,title,{size:th,weight:700,fill:o.tcolor||C.ink}); return s; }
  const total=th+5+lines.length*(sh+2);
  let ty=cy-total/2+th/2;
  s+=T(x+w/2,ty,title,{size:th,weight:700,fill:o.tcolor||C.ink});
  ty+=th/2+5+sh/2;
  for(const ln of lines){ s+=T(x+w/2,ty,ln,{size:sh,weight:400,fill:o.subcolor||C.sub}); ty+=sh+2; }
  return s;
}
function band(x,y,w,h,label,o={}){
  let s=`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12" fill="${o.fill||"#fbfcfe"}" stroke="${o.stroke||"#cbd5e1"}" stroke-width="1.4"/>`;
  if(label) s+=T(x+14,y+16,label,{anchor:"start",size:12.5,weight:700,fill:o.lc||C.slate});
  return s;
}
function arrow(x1,y1,x2,y2,o={}){
  const dash=o.dash?`stroke-dasharray="6 5"`:"";
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${o.color||C.line}" stroke-width="${o.w||2}" ${dash} marker-end="url(#arr)"/>`;
}
function elbowHV(x1,y1,x2,y2,o={}){const dash=o.dash?`stroke-dasharray="6 5"`:"";return `<path d="M ${x1} ${y1} H ${x2} V ${y2}" fill="none" stroke="${o.color||C.line}" stroke-width="${o.w||2}" ${dash} marker-end="url(#arr)"/>`;}
function elbowVH(x1,y1,x2,y2,o={}){const dash=o.dash?`stroke-dasharray="6 5"`:"";return `<path d="M ${x1} ${y1} V ${y2} H ${x2}" fill="none" stroke="${o.color||C.line}" stroke-width="${o.w||2}" ${dash} marker-end="url(#arr)"/>`;}
function cyl(x,y,w,h,label,o={}){
  const fill=o.fill||C.slateF, stroke=o.stroke||C.slateB, ry=9;
  let s=`<path d="M ${x} ${y+ry} A ${w/2} ${ry} 0 0 1 ${x+w} ${y+ry} V ${y+h-ry} A ${w/2} ${ry} 0 0 1 ${x} ${y+h-ry} Z" fill="${fill}" stroke="${stroke}" stroke-width="1.6" filter="url(#sh)"/>`;
  s+=`<ellipse cx="${x+w/2}" cy="${y+ry}" rx="${w/2}" ry="${ry}" fill="${fill}" stroke="${stroke}" stroke-width="1.6"/>`;
  const lines=Array.isArray(label)?label:[label]; let ty=y+h/2-(lines.length-1)*7.5+2;
  for(const ln of lines){ s+=T(x+w/2,ty,ln,{size:11.5,weight:600}); ty+=15; }
  return s;
}
function legend(x,y,items,o={}){
  const pad=10,rowH=19,w=o.w||210,h=pad*2+items.length*rowH;
  let s=`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="9" fill="#ffffff" stroke="#e2e8f0" stroke-width="1.2" filter="url(#sh)"/>`;
  let cy=y+pad+9;
  for(const it of items){
    s+=`<rect x="${x+pad}" y="${cy-6}" width="15" height="12" rx="3" fill="${it.color}" stroke="${it.stroke||"none"}"/>`;
    s+=T(x+pad+23,cy,it.label,{anchor:"start",size:11,fill:C.ink}); cy+=rowH;
  }
  return s;
}
function pin(x,y,label,color){return `<circle cx="${x}" cy="${y}" r="11" fill="${color}" stroke="#fff" stroke-width="2" filter="url(#sh)"/>`+T(x,y,label,{size:11,weight:700,fill:"#fff"});}
const DEFS = `<defs>
<marker id="arr" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="${C.line}"/></marker>
<filter id="sh" x="-12%" y="-15%" width="124%" height="140%"><feDropShadow dx="0" dy="1.4" stdDeviation="1.5" flood-color="#0f172a" flood-opacity="0.12"/></filter>
</defs>`;
function wrap(id,w,h,body){
  return `<svg id="svg-${id}" viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" font-family="${FONT}"><rect class="bg" x="0" y="0" width="${w}" height="${h}" fill="#ffffff"/>${DEFS}${body}</svg>`;
}
/* horizontal pipeline of stages */
function hflow(stages,x,y,bw,bh,gap,o={}){
  let s="",cx=x;
  stages.forEach((st,i)=>{
    s+=box(cx,y,bw,bh,st.t,st.s,{fill:st.fill||o.fill||C.blueF,stroke:st.stroke||o.stroke||C.blueB,size:o.size||12.5,subsize:o.subsize||10});
    if(i<stages.length-1) s+=arrow(cx+bw,y+bh/2,cx+bw+gap,y+bh/2);
    cx+=bw+gap;
  });
  return s;
}
/* neural net columns */
function drawNet(x,y,w,h,layers){
  const colGap=w/(layers.length-1), cols=layers.map((L,i)=>({cx:x+i*colGap,...L}));
  const pos=cols.map(L=>{const n=L.n,gapY=h/(n+1);return Array.from({length:n},(_,k)=>y+gapY*(k+1));});
  let s="";
  for(let i=0;i<cols.length-1;i++)for(const y1 of pos[i])for(const y2 of pos[i+1])
    s+=`<line x1="${cols[i].cx}" y1="${y1}" x2="${cols[i+1].cx}" y2="${y2}" stroke="#dbe3ee" stroke-width="1"/>`;
  cols.forEach((L,i)=>{ pos[i].forEach(cy=>{ s+=`<circle cx="${L.cx}" cy="${cy}" r="9" fill="${L.fill||C.blueF}" stroke="${L.stroke||C.blueB}" stroke-width="1.6"/>`; });
    s+=T(L.cx,y+h+18,L.label,{size:11.5,weight:600,fill:C.slate});
    if(L.sub) s+=T(L.cx,y-14,L.sub,{size:11,weight:700,fill:C.blue});
  });
  return s;
}
/* shared stylised road network */
const ROADS=[[[80,150],[930,150]],[[80,300],[930,300]],[[80,450],[930,450]],
  [[200,80],[200,510]],[[420,80],[420,510]],[[640,80],[640,510]],[[840,80],[840,510]],
  [[200,300],[420,150]],[[640,450],[840,300]]];
const NODES=[[200,150],[420,150],[640,150],[840,150],[200,300],[420,300],[640,300],[840,300],[200,450],[420,450],[640,450],[840,450]];
function roadScene(opts={}){
  let s="";
  for(const r of ROADS){ s+=`<polyline points="${r.map(p=>p.join(",")).join(" ")}" fill="none" stroke="#c8d2e0" stroke-width="9" stroke-linecap="round"/>`; }
  for(const r of ROADS){ s+=`<polyline points="${r.map(p=>p.join(",")).join(" ")}" fill="none" stroke="#eef2f8" stroke-width="2" stroke-dasharray="8 8"/>`; }
  (opts.colored||[]).forEach(c=>{ const r=ROADS[c.road]; s+=`<polyline points="${r.map(p=>p.join(",")).join(" ")}" fill="none" stroke="${c.color}" stroke-width="9" stroke-linecap="round" opacity="0.92"/>`; });
  for(const n of NODES){ s+=`<circle cx="${n[0]}" cy="${n[1]}" r="3.4" fill="#9aa7b8"/>`; }
  if(opts.route){ s+=`<polyline points="${opts.route.map(p=>p.join(",")).join(" ")}" fill="none" stroke="${opts.routeColor||C.blue}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" opacity="0.95"/>`; }
  (opts.vehicles||[]).forEach(v=>{ s+=`<circle cx="${v[0]}" cy="${v[1]}" r="5" fill="${v[2]||C.blue}" stroke="#fff" stroke-width="1.4"/>`; });
  (opts.pins||[]).forEach(p=>{ s+=pin(p[0],p[1],p[2],p[3]); });
  if(opts.legend) s+=legend(opts.legend.x,opts.legend.y,opts.legend.items,{w:opts.legend.w});
  return s;
}
function mixBlue(v){v=Math.max(0,Math.min(1,v));const r=Math.round(255+(29-255)*v),g=Math.round(255+(78-255)*v),b=Math.round(255+(216-255)*v);return `rgb(${r},${g},${b})`;}

/* ============================ FIGURES ============================ */
const FIGS = [
{num:"4.1", name:"Overall System Architecture of FedRouteAI",
 desc:"End-to-end view linking offline federated training to the runtime inference and visualization path. A shared 23-feature Geo V2 contract and an OSM/PostGIS network tie the data, model, backend and map together.",
 build(){const W=1000,H=600;let b="";
  b+=band(30,44,940,150,"Federated training (offline)");
  b+=box(60,92,180,66,"8 Regional clients","REGION_01 … 08",{fill:C.tealF,stroke:C.tealB});
  b+=box(300,92,180,66,"Local GeoV2MLP","train locally",{fill:C.tealF,stroke:C.tealB});
  b+=box(560,92,180,66,"AdaptiveFedAvg","aggregate",{fill:C.purpF,stroke:C.purpB});
  b+=box(800,92,150,66,"Global model","GeoV2MLP",{fill:C.purpF,stroke:C.purpB});
  b+=arrow(240,125,300,125);b+=arrow(480,125,560,125);b+=arrow(740,125,800,125);
  b+=band(30,214,940,350,"Runtime inference & visualization");
  const st=[{t:"GPS telemetry",s:"live batches"},{t:"Segment assoc.",s:"OSM segments"},{t:"Aggregation",s:"per-tick"},{t:"Historical memory",s:"120s ×3"},{t:"23 features",s:"Geo V2"}];
  b+=hflow(st,55,272,168,66,14,{});
  const st2=[{t:"Frozen MLP",s:"loads global model",fill:C.blueF,stroke:C.blueB},{t:"Prediction store",s:"segment_predictions",fill:C.slateF,stroke:C.slateB},{t:"FastAPI",s:"/live-map · /routes",fill:C.amberF,stroke:C.amberB},{t:"React + Leaflet",s:"roads · events · route",fill:C.greenF,stroke:C.greenB}];
  b+=hflow(st2,120,392,190,66,20,{});
  b+=`<path d="M 867 338 V 365 H 215 V 392" fill="none" stroke="${C.line}" stroke-width="2" marker-end="url(#arr)"/>`;
  b+=arrow(875,158,875,214,{color:C.purp});
  b+=T(866,186,"frozen model",{anchor:"end",size:10.5,fill:C.purp});
  b+=cyl(360,478,260,66,["OSM / PostGIS network · 2,968 segments"]);
  b+=arrow(300,458,360,500,{});
  return {w:W,h:H,body:b};}},

{num:"4.2", name:"Federated Learning Architecture",
 desc:"Eight regional clients train a local GeoV2MLP and share only model updates. AdaptiveFedAvg re-weights them into a global model over 50 rounds — raw regional data never leaves the client.",
 build(){const W=1000,H=560,cx=500,cy=290,R=185;let b="";
  b+=box(cx-105,cy-46,210,92,"AdaptiveFedAvg server","Global GeoV2MLP · 50 rounds",{fill:C.purpF,stroke:C.purpB,size:14});
  for(let i=0;i<8;i++){const a=(-90+i*45)*Math.PI/180,x=cx+R*Math.cos(a),y=cy+R*Math.sin(a);
   const bx=x-64,by=y-24;
   b+=`<line x1="${cx+(x-cx)*0.28}" y1="${cy+(y-cy)*0.28}" x2="${cx+(x-cx)*0.72}" y2="${cy+(y-cy)*0.72}" stroke="${C.line}" stroke-width="1.8" marker-end="url(#arr)"/>`;
   b+=`<line x1="${cx+(x-cx)*0.72}" y1="${cy+(y-cy)*0.72}" x2="${cx+(x-cx)*0.30}" y2="${cy+(y-cy)*0.30}" stroke="${C.teal}" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#arr)"/>`;
   b+=box(bx,by,128,48,"REGION_"+String(i+1).padStart(2,"0"),"local MLP",{fill:C.tealF,stroke:C.tealB,size:12,subsize:10});}
  b+=legend(40,470,[{color:C.line,label:"Global weights broadcast ↓"},{color:C.teal,label:"Model updates returned ↑ (no raw data)"}],{w:330});
  return {w:W,h:H,body:b};}},

{num:"4.3", name:"Regional Client and Server Interaction",
 desc:"One federated round shown as a sequence: the server broadcasts global weights, each client trains locally and returns an update, and AdaptiveFedAvg re-weights the contributions.",
 build(){const W=1000,H=520;let b="";
  b+=box(150,50,220,54,"AdaptiveFedAvg Server",null,{fill:C.purpF,stroke:C.purpB});
  b+=box(640,50,220,54,"Regional Client (×8)",null,{fill:C.tealF,stroke:C.tealB});
  b+=`<line x1="260" y1="104" x2="260" y2="470" stroke="#c3ccd8" stroke-width="2"/>`;
  b+=`<line x1="750" y1="104" x2="750" y2="470" stroke="#c3ccd8" stroke-width="2"/>`;
  const steps=[[150,"Broadcast global weights",true],[230,"Load local regional data",false,"self"],[300,"Local training (2 epochs, class-weighted + FedProx)",false,"self"],[370,"Return model update + metrics",false],[440,"AdaptiveFedAvg: re-weight & aggregate",true,"selfL"]];
  steps.forEach(s=>{const y=s[0];
    if(s[3]==="self"){b+=`<path d="M 750 ${y} h -120 v 26 h 120" fill="none" stroke="${C.teal}" stroke-width="2" marker-end="url(#arr)"/>`;b+=T(745,y-11,s[1],{anchor:"end",size:11.5,fill:C.ink});}
    else if(s[3]==="selfL"){b+=`<path d="M 260 ${y} h -120 v 26 h 120" fill="none" stroke="${C.purp}" stroke-width="2" marker-end="url(#arr)"/>`;b+=T(150,y-11,s[1],{anchor:"start",size:11.5,fill:C.ink});}
    else if(s[2]){b+=arrow(262,y,748,y,{color:C.purp});b+=T(505,y-11,s[1],{size:11.5,fill:C.ink});}
    else{b+=arrow(748,y,262,y,{color:C.teal});b+=T(505,y-11,s[1],{size:11.5,fill:C.ink});}
  });
  return {w:W,h:H,body:b};}},

{num:"4.4", name:"End-to-End Data Pipeline",
 desc:"Telemetry flows through segment association, aggregation, historical memory, Geo V2 feature construction, MLP inference and persistence. Each stage is isolated and independently testable.",
 build(){const W=1000,H=430;let b="";
  const top=[{t:"GPS telemetry",s:"live batches"},{t:"Segment association",s:"OSM canonical"},{t:"Traffic aggregation",s:"per-tick state"},{t:"Historical memory",s:"baselines"}];
  b+=hflow(top,45,80,205,72,18,{});
  const bot=[{t:"Geo V2 features",s:"23 ordered",fill:C.blueF,stroke:C.blueB},{t:"MLP inference",s:"GeoV2MLP",fill:C.blueF,stroke:C.blueB},{t:"Prediction persist",s:"segment_predictions",fill:C.slateF,stroke:C.slateB},{t:"API / Map",s:"snapshot",fill:C.greenF,stroke:C.greenB}];
  b+=hflow(bot,45,270,205,72,18,{});
  b+=`<path d="M 816 152 V 211 H 147 V 270" fill="none" stroke="${C.line}" stroke-width="2" marker-end="url(#arr)"/>`;
  b+=T(500,205,"one directional, stage-isolated pipeline",{size:11.5,fill:C.sub});
  return {w:W,h:H,body:b};}},

{num:"4.5", name:"Geo V2 Feature Construction Pipeline",
 desc:"Builds the ordered 23-feature causal vector: 11 current-traffic features, 11 historical / deviation / trend features (120 s cadence, 3 prior ticks), and 1 directed-neighbor feature.",
 build(){const W=1000,H=470;let b="";
  b+=box(40,60,150,80,"Current state","speed, count,\nocc., flow",{fill:C.tealF,stroke:C.tealB});
  b+=box(40,175,150,80,"Historical memory","baselines +\n3 prior ticks",{fill:C.tealF,stroke:C.tealB});
  b+=box(40,290,150,80,"Directed neighbors","upstream\nsegment",{fill:C.tealF,stroke:C.tealB});
  b+=box(270,150,220,140,"CausalFeatureBuilder","reject_forbidden_columns()\n(no label / scenario leak)",{fill:C.blueF,stroke:C.blueB,size:13.5});
  b+=arrow(190,100,270,200);b+=arrow(190,215,270,220);b+=arrow(190,330,270,240);
  b+=box(560,150,180,140,"23-feature vector","history_spatial_strong",{fill:C.purpF,stroke:C.purpB});
  b+=arrow(490,220,560,220);
  b+=box(810,175,150,90,"Preprocess","scale → MLP",{fill:C.slateF,stroke:C.slateB});
  b+=arrow(740,220,810,220);
  b+=T(650,315,"11 current + 11 history + 1 neighbor = 23",{size:11.5,fill:C.sub});
  b+=T(650,120,"version: geo-v2-history_spatial_strong-23-v2",{size:11,weight:600,fill:C.purp});
  return {w:W,h:H,body:b};}},

{num:"4.6", name:"Historical Traffic Memory and Causal Windows",
 desc:"Per-segment baselines and prior 120 s windows supply causal context without leaking the future. Known-event windows are excluded when the baseline is built.",
 build(){const W=1000,H=430;let b="";
  b+=T(120,60,"time →",{anchor:"start",size:11,fill:C.sub});
  const y=110,bw=120,gap=12; let x=90;
  const wins=[["t−3",C.slateF],["t−2",C.slateF],["t−1",C.slateF],["t (now)",C.blueF]];
  wins.forEach((wn,i)=>{b+=box(x,y,bw,60,wn[0],i<3?"prior tick":"current",{fill:wn[1],stroke:i<3?C.slateB:C.blueB,size:12.5,subsize:10});if(i<3)b+=arrow(x+bw,y+30,x+bw+gap,y+30);x+=bw+gap;});
  b+=box(x+20,y,150,60,"Predict",null,{fill:C.purpF,stroke:C.purpB});b+=arrow(x-12,y+30,x+20,y+30);
  b+=cyl(120,250,190,80,["Baselines","(excl. event windows)"]);
  b+=box(420,255,220,70,"Deviations & trends","speed/count vs baseline",{fill:C.tealF,stroke:C.tealB});
  b+=arrow(310,290,420,290);
  b+=arrow(215,250,215,175)+T(230,215,"context",{anchor:"start",size:10.5,fill:C.sub});
  b+=arrow(530,255,470,175);
  b+=T(500,375,"120 s cadence · 3 history slots · causal (past-only) features",{size:11.5,fill:C.sub});
  return {w:W,h:H,body:b};}},

{num:"4.7", name:"OSM/PostGIS Network Import",
 desc:"Cached Beeramguda / Ashok Nagar OpenStreetMap data is normalized into canonical directed segments and stored in PostGIS (2,968 segments, 11,259 transitions).",
 build(){const W=1000,H=380;let b="";
  const st=[{t:"Cached OSM JSON",s:"Overpass export",fill:C.slateF,stroke:C.slateB},{t:"network.py",s:"load_overpass_json()",fill:C.blueF,stroke:C.blueB},{t:"CanonicalSegment",s:"highway→RoadType",fill:C.blueF,stroke:C.blueB},{t:"import_network.py",s:"additive version",fill:C.tealF,stroke:C.tealB}];
  b+=hflow(st,45,110,200,74,18,{});
  b+=cyl(700,230,230,90,["PostGIS","geo_segment_metadata","geo_segment_transitions"]);
  b+=arrow(845,184,815,230);
  b+=T(500,300,"network version: beeramguda-osm-20260506 · source: osm_geo_v2",{size:11.5,fill:C.sub});
  b+=T(500,330,"2,968 canonical segments · 11,259 directed transitions",{size:12,weight:700,fill:C.teal});
  return {w:W,h:H,body:b};}},

{num:"4.8", name:"Directed Road Network and Transitions",
 desc:"Segments are modeled as directed edges with turn transitions, preserving travel direction for both traffic representation and shortest-path routing.",
 build(){const W=1000,H=560;let b="";
  b+=roadScene({colored:[{road:1,color:"#93c5fd"},{road:4,color:"#93c5fd"}],
    legend:{x:720,y:430,w:250,items:[{color:"#c8d2e0",label:"Road segment (edge)"},{color:"#9aa7b8",label:"Intersection (node)"},{color:C.blue,label:"Directed transition"}]}});
  // direction arrows along a couple of roads
  [[80,150,930,150],[200,510,200,80]].forEach(a=>{const mx=(a[0]+a[2])/2,my=(a[1]+a[3])/2;b+=arrow(mx-30, my, mx+30, my,{color:C.blue,w:2.4});});
  b+=T(500,40,"",{});
  return {w:W,h:H,body:b};}},

{num:"4.9", name:"Backend Service and Repository Layers",
 desc:"FastAPI endpoints call services (business logic), which call repositories (PostGIS access), which map to SQLAlchemy models — a strict, one-directional layering.",
 build(){const W=1000,H=560;let b="";
  const lanes=[["API — app/api/v1/endpoints",C.amberF,C.amberB,["/live-ingest","/live-map","/routes","/events","/prediction"]],
    ["Services — app/services",C.blueF,C.blueB,["geo_v2","event_detection","routing","road_graph","historical_memory"]],
    ["Repositories — app/repositories",C.tealF,C.tealB,["segment_repo","geo_v2_repo","event_repo","gps_repo"]],
    ["Models (SQLAlchemy) — app/models",C.slateF,C.slateB,["segment","geo_v2","event","historical_memory"]]];
  let y=50;lanes.forEach((L,li)=>{b+=band(40,y,920,96,L[0],{fill:"#fff"});
    let x=70;L[3].forEach(m=>{const bw=(920-40)/L[3].length-14;b+=box(x,y+34,bw,46,m,null,{fill:L[1],stroke:L[2],size:11.5});x+=bw+14;});
    if(li<lanes.length-1)b+=arrow(500,y+96,500,y+118,{});
    y+=118;});
  return {w:W,h:H,body:b};}},

{num:"4.10", name:"Frontend Map and API Interaction",
 desc:"The React + Leaflet TrafficMap consumes REST endpoints for segments, live snapshot, routes and demo runs, rendering roads, predictions, vehicles, events and routes.",
 build(){const W=1000,H=470;let b="";
  b+=box(60,90,190,120,"React + Leaflet","TrafficMap page\n(react-query, axios)",{fill:C.greenF,stroke:C.greenB,size:14});
  b+=box(410,60,200,54,"FastAPI backend","/api/v1",{fill:C.amberF,stroke:C.amberB});
  const eps=[["GET /segments",150],["GET /live-map/snapshot",200],["POST /routes/shortest",250],["POST /demo/geo-v2/runs",300]];
  eps.forEach(e=>{b+=box(410,e[1]-20,240,40,e[0],null,{fill:"#fff",stroke:C.amberB,size:11.5});});
  eps.forEach(e=>{b+=arrow(250,150,410,e[1],{color:C.line});});
  b+=box(760,150,190,150,"Renders","roads · predictions\nvehicles · events\nroute",{fill:C.blueF,stroke:C.blueB});
  eps.forEach(e=>{b+=arrow(650,e[1],760,225,{color:"#cbd5e1"});});
  return {w:W,h:H,body:b};}},

{num:"4.11", name:"Directed Shortest-Path Routing",
 desc:"Origin/destination points are snapped to the directed graph and connected by Dijkstra's shortest path on distance; Geo V2 predictions are inspected but do not change cost.",
 build(){const W=1000,H=560;let b="";
  const route=[[200,450],[200,300],[420,300],[420,150],[640,150]];
  b+=roadScene({route,routeColor:C.blue,pins:[[200,450,"O",C.green],[640,150,"D",C.red]],
    legend:{x:700,y:430,w:270,items:[{color:C.blue,label:"Dijkstra shortest path (distance)"},{color:C.green,label:"Origin (snapped)"},{color:C.red,label:"Destination (snapped)"}]}});
  b+=box(40,30,320,54,"nx.dijkstra_path(weight = length_m)","predictions inspected, not repriced",{fill:C.blueF,stroke:C.blueB,size:12.5,subsize:10});
  return {w:W,h:H,body:b};}},

{num:"5.1", name:"Live GPS Ingestion Pipeline",
 desc:"Batched GPS telemetry is API-key gated, associated with segments, aggregated per tick and prepared for feature construction before inference.",
 build(){const W=1000,H=360;let b="";
  const st=[{t:"POST /live-ingest/batch",s:"API-key · ≤2000",fill:C.amberF,stroke:C.amberB},{t:"live_ingestion service",s:"validate & store",fill:C.blueF,stroke:C.blueB},{t:"Segment association",s:"geometry / alignment",fill:C.blueF,stroke:C.blueB},{t:"Per-tick aggregation",s:"segment state",fill:C.tealF,stroke:C.tealB},{t:"Feature build",s:"→ Geo V2",fill:C.purpF,stroke:C.purpB}];
  b+=hflow(st,30,140,180,80,10,{});
  b+=T(500,270,"batches are one device's trajectory · scenario labels excluded from features",{size:11.5,fill:C.sub});
  return {w:W,h:H,body:b};}},

{num:"5.2", name:"Frozen Geo V2 MLP Inference",
 desc:"The frozen GeoV2MLP (23→64→32→8) validates the feature contract, then outputs a predicted traffic-event class and confidence in a label-free manner.",
 build(){const W=1000,H=470;let b="";
  b+=box(30,200,160,70,"23-feature vector","contract-checked",{fill:C.purpF,stroke:C.purpB,size:12.5});
  b+=arrow(190,235,235,235);
  b+=drawNet(255,120,470,230,[{n:6,label:"input (23)",fill:C.tealF,stroke:C.tealB,sub:"23"},{n:6,label:"hidden",fill:C.blueF,stroke:C.blueB,sub:"64"},{n:5,label:"hidden",fill:C.blueF,stroke:C.blueB,sub:"32"},{n:8,label:"output",fill:C.purpF,stroke:C.purpB,sub:"8"}]);
  b+=arrow(740,235,795,235);
  b+=box(800,190,170,90,"log-softmax","class + confidence\n(label-free)",{fill:C.greenF,stroke:C.greenB,size:12.5,subsize:10});
  b+=T(500,410,"GeoV2MLP · BatchNorm + ReLU + Dropout 0.2 · frozen artifact (50 rounds, 2 epochs)",{size:11.5,fill:C.sub});
  return {w:W,h:H,body:b};}},

{num:"5.3", name:"Dynamic Traffic Map",
 desc:"Schematic of the live map: road segments colored by predicted state (normal / congestion / accident) with an interactive legend and region focus.",
 build(){const W=1000,H=560;let b="";
  b+=roadScene({colored:[{road:0,color:C.green},{road:1,color:C.amber},{road:4,color:C.red},{road:2,color:C.green},{road:5,color:C.green},{road:3,color:C.amber}],
    legend:{x:720,y:410,w:250,items:[{color:C.green,label:"Normal flow"},{color:C.amber,label:"Congestion"},{color:C.red,label:"Accident / blocked"}]}});
  b+=box(40,30,300,48,"GET /live-map/snapshot","segment predictions overlay",{fill:C.blueF,stroke:C.blueB,size:12.5,subsize:10});
  return {w:W,h:H,body:b};}},

{num:"5.4", name:"Moving Vehicle Visualization",
 desc:"Schematic of animated vehicle markers moving along segments between ticks, illustrating simulated traffic flow on the map.",
 build(){const W=1000,H=560;let b="";
  const veh=[[150,150,C.blue],[260,150,C.blue],[360,150,C.blue],[200,220,C.teal],[200,380,C.teal],[420,240,C.blue],[520,300,C.amber],[640,360,C.amber],[740,300,C.blue],[840,200,C.teal],[300,300,C.blue],[500,450,C.blue]];
  b+=roadScene({vehicles:veh,legend:{x:730,y:440,w:240,items:[{color:C.blue,label:"Vehicle marker (moving)"},{color:C.teal,label:"Turning / cross-street"},{color:C.amber,label:"Slowed vehicle"}]}});
  // motion hints
  b+=arrow(360,150,395,150,{color:C.blue,w:2.4});b+=arrow(740,300,705,300,{color:C.blue,w:2.4});
  b+=box(40,30,300,48,"AnimatedVehicleLayer","interpolated between ticks",{fill:C.greenF,stroke:C.greenB,size:12.5,subsize:10});
  return {w:W,h:H,body:b};}},

{num:"5.5", name:"Route-Bound Demonstration Flow",
 desc:"A user calculates a directed route (≥ 1.5 km) and selects a scenario; controlled behavior is bound to the route's ordered segments, kept separate from model inputs.",
 build(){const W=1000,H=420;let b="";
  const st=[{t:"Calculate route",s:"≥ 1.5 km directed",fill:C.blueF,stroke:C.blueB},{t:"Select scenario",s:"normal/congestion/accident",fill:C.amberF,stroke:C.amberB},{t:"Bind to segments",s:"ordered segment IDs",fill:C.tealF,stroke:C.tealB},{t:"Simulate on map",s:"vehicles + state",fill:C.greenF,stroke:C.greenB}];
  b+=hflow(st,40,120,205,80,20,{});
  b+=box(300,270,400,60,"Scenario truth kept OUT of model features","demonstration ≠ ground truth",{fill:"#fff",stroke:C.redB,size:12.5,subsize:10.5,tcolor:C.red});
  b+=arrow(245,260,430,270,{dash:true});b+=arrow(700,260,560,270,{dash:true});
  return {w:W,h:H,body:b};}},

{num:"5.6", name:"Normal Traffic Demonstration",
 desc:"Schematic of the baseline scenario: free-flow speeds along the route with segments shown in the normal state.",
 build(){const W=1000,H=560;let b="";
  const route=[[200,450],[200,300],[420,300],[420,150],[640,150]];
  b+=roadScene({colored:[{road:0,color:C.green},{road:1,color:C.green},{road:2,color:C.green},{road:4,color:C.green},{road:5,color:C.green}],route,routeColor:C.blue,
    vehicles:[[200,360,C.green],[300,300,C.green],[420,220,C.green],[520,150,C.green]],
    pins:[[200,450,"O",C.green],[640,150,"D",C.red]],
    legend:{x:720,y:440,w:230,items:[{color:C.green,label:"Normal (free flow)"},{color:C.blue,label:"Selected route"}]}});
  b+=box(40,30,260,48,"Scenario: NORMAL","baseline route behavior",{fill:C.greenF,stroke:C.greenB,size:12.5,subsize:10});
  return {w:W,h:H,body:b};}},

{num:"5.7", name:"Congestion and Accident Demonstrations",
 desc:"Schematic contrasting a congestion slowdown and an accident disturbance on route segments, shown as demonstration traffic (not model ground truth).",
 build(){const W=1000,H=560;let b="";
  const route=[[200,450],[200,300],[420,300],[420,150],[640,150]];
  b+=roadScene({colored:[{road:0,color:C.amber},{road:1,color:C.red},{road:4,color:C.amber},{road:2,color:C.green},{road:5,color:C.green}],route,routeColor:C.blue,
    vehicles:[[200,340,C.amber],[200,320,C.amber],[420,300,C.red],[420,240,C.amber],[520,150,C.green]],
    pins:[[420,300,"!",C.red],[200,450,"O",C.green],[640,150,"D",C.red]],
    legend:{x:700,y:410,w:270,items:[{color:C.amber,label:"Congestion (slowed)"},{color:C.red,label:"Accident disturbance"},{color:C.green,label:"Normal"}]}});
  b+=box(40,30,300,48,"Scenarios: CONGESTION / ACCIDENT","controlled disturbance on route",{fill:C.redF,stroke:C.redB,size:12.5,subsize:10,tcolor:C.red});
  return {w:W,h:H,body:b};}},

{num:"6.1", name:"Model Validation Results",
 desc:"Reported Geo V2 metrics: Validation Macro-F1 0.3042, Test Macro-F1 0.3200, Event-balanced Macro-F1 0.4459, Anomaly Recall 0.3444, Anomaly Precision 0.2093, Normal FPR 0.0031.",
 build(){const W=1000,H=460;let b="";
  const M=[["Validation Macro-F1",0.3042,C.blue],["Test Macro-F1",0.3200,C.blue],["Event-balanced Macro-F1",0.4459,C.teal],["Anomaly Recall",0.3444,C.amber],["Anomaly Precision",0.2093,C.amber],["Normal FPR",0.0031,C.green]];
  const x0=300,x1=930,y0=60,rh=56;
  for(let i=0;i<=4;i++){const gx=x0+(x1-x0)*i/4;b+=`<line x1="${gx}" y1="${y0-6}" x2="${gx}" y2="${y0+M.length*rh-18}" stroke="${C.grid}" stroke-width="1"/>`;b+=T(gx,y0+M.length*rh-2,(i/4).toFixed(2),{size:10.5,fill:C.sub});}
  M.forEach((m,i)=>{const y=y0+i*rh;b+=T(x0-14,y+14,m[0],{anchor:"end",size:12,fill:C.ink});
    b+=`<rect x="${x0}" y="${y+2}" width="${x1-x0}" height="24" rx="5" fill="#f1f5f9"/>`;
    b+=`<rect x="${x0}" y="${y+2}" width="${(x1-x0)*m[1]}" height="24" rx="5" fill="${m[2]}"/>`;
    b+=T(x0+(x1-x0)*m[1]+8,y+14,m[1].toFixed(4),{anchor:"start",size:11.5,weight:700,fill:C.ink});});
  b+=T(500,H-16,"macro-averaged / event-balanced metrics reflect class imbalance (values from the report)",{size:11,fill:C.sub});
  return {w:W,h:H,body:b};}},

{num:"6.2", name:"Model Confusion Matrix",
 desc:"Real held-out test confusion matrix (8 classes). Normal dominates (330,612 correct); minority events are weak and diversion is never recovered (0/112) — reflecting the dataset's class imbalance.",
 build(){const W=1000,H=620;let b="";
  const ab=["normal","congest.","diversion","road_dmg","constr.","accident","flood","rd_block"];
  const M=[[330612,46,116,288,104,246,163,57],[70,42,0,0,0,0,0,0],[112,0,0,0,0,0,0,0],[68,6,0,36,0,0,2,0],[100,0,0,0,12,0,0,0],[50,0,6,0,0,52,2,2],[58,0,0,0,0,15,39,0],[56,0,14,0,0,0,0,42]];
  const x0=250,y0=80,cs=52;
  const fmt=n=>String(n).replace(/\B(?=(\d{3})+(?!\d))/g,",");
  for(let i=0;i<8;i++){b+=T(x0-12,y0+i*cs+cs/2,ab[i],{anchor:"end",size:10.5,fill:C.ink});
    b+=T(x0+i*cs+cs/2,y0-14,ab[i],{size:10,fill:C.ink,rot:-40});}
  for(let r=0;r<8;r++){const rs=M[r].reduce((a,c)=>a+c,0)||1;
    for(let c=0;c<8;c++){const v=M[r][c],frac=v/rs,X=x0+c*cs,Y=y0+r*cs;
      b+=`<rect x="${X}" y="${Y}" width="${cs-2}" height="${cs-2}" rx="3" fill="${mixBlue(frac)}" stroke="#e2e8f0"/>`;
      if(v>0||r===c)b+=T(X+cs/2-1,Y+cs/2,fmt(v),{size:v>=100000?8:9.5,weight:600,fill:frac>0.5?"#fff":C.ink});}}
  b+=T(x0+4*cs,y0+8*cs+26,"Predicted class",{size:12,weight:700,fill:C.slate});
  b+=T(x0-72,y0+4*cs,"Actual class",{size:12,weight:700,fill:C.slate,rot:-90});
  for(let i=0;i<50;i++)b+=`<rect x="820" y="${80+i*7}" width="22" height="7" fill="${mixBlue(1-i/49)}"/>`;
  b+=T(852,84,"1.0",{anchor:"start",size:10,fill:C.sub});b+=T(852,80+49*7,"0.0",{anchor:"start",size:10,fill:C.sub});
  b+=T(831,80+50*7+14,"recall",{size:10,fill:C.sub});
  b+=T(500,H-16,"real held-out test counts · cell color = row-normalized recall · diversion recall = 0/112",{size:11,fill:C.sub});
  return {w:W,h:H,body:b};}},

{num:"6.3", name:"Backend and Frontend Test Evidence",
 desc:"Validation coverage summary: 117 backend tests and 17 focused frontend tests across services, features, artifact, routing, ingestion, build and runtime checks.",
 build(){const W=1000,H=480;let b="";
  b+=box(70,60,380,90,"117 backend tests","pytest · services, API, features",{fill:C.blueF,stroke:C.blueB,size:20,subsize:12});
  b+=box(550,60,380,90,"17 frontend tests","focused UI + build",{fill:C.greenF,stroke:C.greenB,size:20,subsize:12});
  const cats=[["Unit & service","backend suite"],["API contracts","Pydantic I/O"],["Geo V2 features","order · cadence · neighbors"],["Artifact","model · scaler · metadata"],["Routing","directed path · exclusions"],["Live ingestion","batch · persist · snapshot"],["Frontend","map · route · demo"],["Build","compile · bundle"]];
  let x=70,y=190;cats.forEach((c,i)=>{const bw=200,bh=64;const cx=x+(i%4)*(bw+15),cy=y+Math.floor(i/4)*(bh+15);
    b+=`<rect x="${cx}" y="${cy}" width="${bw}" height="${bh}" rx="9" fill="#fff" stroke="#e2e8f0" stroke-width="1.3" filter="url(#sh)"/>`;
    b+=`<circle cx="${cx+18}" cy="${cy+bh/2}" r="9" fill="${C.greenF}" stroke="${C.greenB}"/>`;b+=T(cx+18,cy+bh/2+0.5,"✓",{size:11,weight:700,fill:C.green});
    b+=T(cx+34,cy+24,c[0],{anchor:"start",size:12.5,weight:700,fill:C.ink});b+=T(cx+34,cy+42,c[1],{anchor:"start",size:10.5,fill:C.sub});});
  b+=T(500,H-16,"all suites passing under the tested environment (values from the report)",{size:11,fill:C.sub});
  return {w:W,h:H,body:b};}},

{num:"7.1", name:"Local Deployment Architecture",
 desc:"Local deployment: React frontend → FastAPI backend → processing / ML services → PostgreSQL/PostGIS, with federated training as a separate offline workflow.",
 build(){return {w:1000,h:430,body:cleanup71()};}}
];

/* figure 7.1 body */
function cleanup71(){let b="";
  const st=[{t:"React frontend",s:"Vite · Leaflet",fill:C.greenF,stroke:C.greenB},{t:"FastAPI backend",s:"/api/v1",fill:C.amberF,stroke:C.amberB},{t:"Processing / ML",s:"Geo V2 services",fill:C.blueF,stroke:C.blueB}];
  b+=hflow(st,50,120,210,80,30,{});
  b+=cyl(790,118,160,120,["PostgreSQL","+ PostGIS"]);
  b+=arrow(740,160,790,170,{});
  b+=band(50,280,760,110,"Federated training (separate offline workflow)");
  b+=box(80,315,200,50,"8 regional clients",null,{fill:C.tealF,stroke:C.tealB,size:12});
  b+=box(320,315,190,50,"AdaptiveFedAvg",null,{fill:C.purpF,stroke:C.purpB,size:12});
  b+=box(550,315,180,50,"Global model .pt",null,{fill:C.purpF,stroke:C.purpB,size:12});
  b+=arrow(280,340,320,340);b+=arrow(510,340,550,340);
  b+=arrow(640,315,470,200,{dash:true})+T(650,258,"frozen model loaded by backend",{anchor:"start",size:10.5,fill:C.sub});
  return b;}

/* ---------- render ---------- */
function render(){
  const grid=document.getElementById("grid");
  grid.innerHTML = FIGS.map(f=>{
    const key=f.num.replace(".","_");
    const {w,h,body}=f.build();
    const svg=wrap(key,w,h,body);
    return `<figure class="card">
      <div class="fig-holder" id="holder-${key}">${svg}</div>
      <figcaption class="cap">
        <div class="fnum">Figure <span>${f.num}</span> — ${esc(f.name)}</div>
        <p class="fdesc">${esc(f.desc)}</p>
      </figcaption>
      <div class="card-actions">
        <button class="btn small" data-png="${key}" data-name="${esc(f.name)}">PNG</button>
        <button class="btn small ghost" data-svg="${key}" data-name="${esc(f.name)}" style="color:#0f172a;border:1px solid #cbd5e1;">SVG</button>
      </div>
    </figure>`;
  }).join("");
}

/* ---------- export ---------- */
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function fileName(num,name,ext){return `Fig_${num}_${name.replace(/[^a-z0-9]+/gi,"_").replace(/^_|_$/g,"")}.${ext}`;}
function download(blob,name){const u=URL.createObjectURL(blob);const a=document.createElement("a");a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1500);}
function svgString(key){const el=document.getElementById("svg-"+key);return new XMLSerializer().serializeToString(el);}
function exportSvg(key,num,name){const s='<?xml version="1.0" encoding="UTF-8"?>\n'+svgString(key);download(new Blob([s],{type:"image/svg+xml"}),fileName(num,name,"svg"));}
function exportPng(key,num,name,scale=2.5){return new Promise(res=>{
  const el=document.getElementById("svg-"+key);const vb=el.viewBox.baseVal;
  const xml=new XMLSerializer().serializeToString(el);
  const src="data:image/svg+xml;base64,"+btoa(unescape(encodeURIComponent(xml)));
  const img=new Image();
  img.onload=()=>{const cv=document.createElement("canvas");cv.width=Math.round(vb.width*scale);cv.height=Math.round(vb.height*scale);
    const ctx=cv.getContext("2d");ctx.fillStyle="#ffffff";ctx.fillRect(0,0,cv.width,cv.height);ctx.drawImage(img,0,0,cv.width,cv.height);
    cv.toBlob(bl=>{download(bl,fileName(num,name,"png"));res();},"image/png");};
  img.onerror=()=>res();img.src=src;});}

function wire(){
  document.getElementById("grid").addEventListener("click",e=>{
    const t=e.target;
    if(t.dataset.png){const key=t.dataset.png;const f=FIGS.find(x=>x.num.replace(".","_")===key);exportPng(key,f.num,f.name);}
    if(t.dataset.svg){const key=t.dataset.svg;const f=FIGS.find(x=>x.num.replace(".","_")===key);exportSvg(key,f.num,f.name);}
  });
  document.getElementById("dlAllPng").addEventListener("click",async()=>{for(const f of FIGS){await exportPng(f.num.replace(".","_"),f.num,f.name);await sleep(300);}});
  document.getElementById("dlAllSvg").addEventListener("click",async()=>{for(const f of FIGS){exportSvg(f.num.replace(".","_"),f.num,f.name);await sleep(150);}});
  document.getElementById("toggleBg").addEventListener("change",e=>{
    const white=e.target.checked;
    document.querySelectorAll("svg .bg").forEach(r=>r.setAttribute("fill",white?"#ffffff":"none"));
    document.querySelectorAll(".fig-holder").forEach(h=>h.classList.toggle("dark",!white));
  });
}

if(typeof window!=="undefined"){window.addEventListener("DOMContentLoaded",()=>{render();wire();});}

/* expose for node --check / testing */
if(typeof module!=="undefined"){module.exports={FIGS,wrap,DEFS};}

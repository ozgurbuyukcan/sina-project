"use strict";
const stages = {
 scan: {title:"Sensor integrity comes first.", body:"Before interpreting anomalies, SINA checks incoming flow and pressure readings for problems such as missing values and data gaps.", note:"The visible screenshot includes a missing-flow flag. A data issue is not proof of a leak.", alt:"SCAN interface displaying flow, pressure and data-integrity flags"},
 identify: {title:"Spot the unusual. Don't guess the cause.", body:"An Isolation Forest fitted to early assumed-normal measurements produces an unsupervised anomaly evidence score.", note:"An anomaly evidence score is neither a leak probability nor a validated physical diagnosis.",alt:"IDENTIFY interface showing relative anomaly evidence and Isolation Forest metadata"},
 navigate: {title:"Turn signals into a queue.", body:"SINA groups events by line, time, type and priority. It distinguishes hydraulic anomalies from data-quality problems.", note:"NAVIGATE prioritizes human inspection. It does not pinpoint the physical location of a leak.",alt:"NAVIGATE interface showing event prioritization and inspection queue"},
 assess: {title:"Put an operator in the loop.", body:"Inspect the measurement window around an event, examine the signal and keep a record of the operator's findings.", note:"The selected demo event was WATCH_ONLY: an unusual signal, not a confirmed leak.",alt:"ASSESS interface showing a single event's local measurement context"},
 learning: {title:"Build evidence, not artificial certainty.", body:"The learning-data module keeps reviewed real-event candidates separate from synthetic and replayed demonstrations.", note:"The demo correctly shows zero eligible learning events. Human-entered labels are not independently certified ground truth.",alt:"LEARNING DATA interface showing zero eligible events and data provenance safeguards"}
};
const tabs = Array.from(document.querySelectorAll('[role="tab"][data-stage]'));
const panel = document.getElementById('panel-stage');
function selectStage(name, focus=false) {
 const s=stages[name]; if(!s)return;
 for(const tab of tabs){const active=tab.dataset.stage===name;tab.classList.toggle('is-active',active);tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;if(active&&focus)tab.focus();}
 document.getElementById('stage-image').src=`./assets/${name}.webp`;
 document.getElementById('stage-image').alt=s.alt;
 document.getElementById('screen-file').textContent=`sina_fresh_0_2_1 / ${name}`;
 document.getElementById('detail-kicker').textContent=`MODULE ${String(tabs.findIndex(t=>t.dataset.stage===name)+1).padStart(2,'0')} / 05`;
 document.getElementById('detail-title').textContent=s.title;
 document.getElementById('detail-body').textContent=s.body;
 document.getElementById('detail-note').textContent=s.note;
 panel.setAttribute('aria-labelledby',`tab-${name}`);
}
for(let i=0;i<tabs.length;i++){
 tabs[i].addEventListener('click',()=>selectStage(tabs[i].dataset.stage));
 tabs[i].addEventListener('keydown',e=>{
  if(['ArrowRight','ArrowLeft','Home','End'].includes(e.key)){
   e.preventDefault();
   let next=e.key==='Home'?0:e.key==='End'?tabs.length-1:e.key==='ArrowRight'?(i+1)%tabs.length:(i-1+tabs.length)%tabs.length;
   selectStage(tabs[next].dataset.stage,true);
  }
 });
}

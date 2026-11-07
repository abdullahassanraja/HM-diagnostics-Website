const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {JSDOM}=require('../widget/node_modules/jsdom');
const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://127.0.0.1:8001/demo',runScripts:'outside-only'});
const w=dom.window,d=w.document,requests=[];
const loader=d.createElement('script');loader.src='http://127.0.0.1:8001/widget/chatbot.js';
Object.defineProperty(d,'currentScript',{get:()=>loader});
Object.defineProperty(w,'localStorage',{get:()=>{throw Error('Widget must not use localStorage');}});
Object.defineProperty(w,'sessionStorage',{get:()=>{throw Error('Widget must not use sessionStorage');}});
let stage='idle',submissions=0;
const sid='x'.repeat(43);
function response(reply){return {session_id:sid,state:stage,reply,demo_mode:true,quick_actions:[{label:'Book an Appointment',action:'book'}]};}
w.fetch=async(url,options={})=>{
  const body=options.body?JSON.parse(options.body):null;requests.push({url,body});
  let data;
  if(url.endsWith('/api/config'))data={demo_mode:true,session_ttl_minutes:30};
  else if(url.endsWith('/api/appointments')){submissions++;data={saved:true,demo:true,status:'Pending',request_id:'00000000-0000-4000-8000-000000000001',message:'Demo request only, not sent to clinic.'};}
  else if(body.action==='cancel'){stage='idle';data=response('Cleared');}
  else if(body.action==='book'){stage='consent';data={...response('Consent first'),quick_actions:[{label:'I consent',action:'consent'}]};}
  else if(body.action==='consent'){assert.equal(body.consent,true);stage='name';data=response('Name?');}
  else if(stage==='name'){stage='phone';data=response('Mobile?');}
  else if(stage==='phone'){stage='service';data=response('Service?');}
  else if(stage==='service'){stage='date';data=response('Date?');}
  else if(stage==='date'){stage='time';data=response('Time?');}
  else if(stage==='time'){stage='notes';data={...response('Notes?'),quick_actions:[{label:'Skip',action:'skip'}]};}
  else if(stage==='notes'){stage='review';data={...response('Please review'),summary:{patient_name:'Demo Visitor',phone:'+923001234567',service:'CBC',preferred_date:'2027-01-01',preferred_time:'14:30',notes:''},confirmation_token:'c'.repeat(43),idempotency_key:'00000000-0000-4000-8000-000000000001'};}
  else data=response(body.message||'Welcome to the demo');
  return {ok:true,status:200,json:async()=>data};
};
async function until(predicate){for(let i=0;i<100;i++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,5));}throw Error('Widget did not become ready');}
async function main(){
  w.eval(fs.readFileSync(path.join(__dirname,'../widget/chatbot.js'),'utf8'));
  const host=d.querySelector('hm-receptionist'),root=host.shadowRoot;
  const input=root.querySelector('input'),form=root.querySelector('form');
  root.querySelector('.launcher').click();await until(()=>requests.some(r=>r.url.endsWith('/api/chat'))&&!input.disabled);
  assert.equal(root.querySelector('.panel').hidden,false);
  root.querySelector('.close').click();assert.equal(root.querySelector('.panel').hidden,true);
  root.querySelector('.launcher').click();assert.equal(root.querySelector('.panel').hidden,false);
  async function send(text){input.value=text;form.dispatchEvent(new w.Event('submit',{cancelable:true}));await until(()=>!input.disabled);}
  await send('<img src=x onerror=alert(1)>');
  assert.equal(root.querySelectorAll('img').length,0);
  assert(root.querySelector('.messages').textContent.includes('<img src=x onerror=alert(1)>'));
  root.querySelector('.actions button').click();await until(()=>stage==='consent'&&!input.disabled);
  root.querySelector('.actions button').click();await until(()=>stage==='name'&&!input.disabled);
  await send('Demo Visitor');assert.equal(input.type,'tel');
  await send('03001234567');await send('CBC');assert.equal(input.type,'date');
  await send('2027-01-01');assert.equal(input.type,'time');
  await send('14:30');root.querySelector('.actions button').click();await until(()=>stage==='review'&&!input.disabled);
  const submit=root.querySelector('.submit-request');submit.click();submit.click();
  await until(()=>submissions===1&&!input.disabled);
  assert.equal(submissions,1);
  assert(!root.querySelector('.messages').textContent.includes('Demo Visitor'));
  assert.equal(root.querySelectorAll('.review').length,0);
  assert(requests.find(r=>r.url.endsWith('/api/appointments')).body.confirmed);
  root.querySelector('.language').click();assert.equal(root.querySelector('.panel').dir,'rtl');
  console.log('PASS: widget opens/minimizes/reopens, uses text-only rendering, progresses input types, asks consent, submits only after review, blocks repeated clicks, clears contact display and supports RTL without persistent browser storage.');
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>w.close());

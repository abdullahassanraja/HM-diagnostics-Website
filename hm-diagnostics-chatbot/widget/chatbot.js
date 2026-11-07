(() => {
  'use strict';
  if (document.querySelector('hm-receptionist')) return;
  const script = document.currentScript;
  const base = new URL(script?.dataset.apiUrl || new URL(script.src).origin);
  if (base.protocol !== 'https:' && !['localhost', '127.0.0.1', '[::1]'].includes(base.hostname)) return;
  const api = base.origin;
  const host = document.createElement('hm-receptionist');
  const root = host.attachShadow({mode:'open'});
  const sheet = document.createElement('link'); sheet.rel='stylesheet'; sheet.href=api+'/widget/chatbot.css'; root.append(sheet);
  const ui = document.createElement('div');
  // This template is static. All visitor and API text below is rendered using textContent.
  ui.innerHTML = `<section class="panel" role="dialog" aria-modal="false" aria-label="HM virtual receptionist" hidden>
    <header class="header"><span class="brand-icon" aria-hidden="true">✳</span><div><h2>HM Care Assistant</h2><p class="subtitle">Your virtual receptionist</p></div><button class="language" type="button" aria-label="Switch language">اردو</button><button class="close" type="button" aria-label="Minimize chat">−</button></header>
    <div class="mode" hidden></div><div class="messages" role="log" aria-live="polite" aria-relevant="additions" tabindex="0"></div>
    <div class="typing" role="status" hidden><span></span><span></span><span></span><small>Receptionist is typing</small></div>
    <div class="actions" aria-label="Suggested actions"></div>
    <form class="composer"><label class="sr-only" for="hm-message">Your message</label><input id="hm-message" name="message" type="text" maxlength="1000" autocomplete="off" placeholder="How can we help?" required><button class="send" type="submit" aria-label="Send message">↑</button></form>
    <footer class="footer"><span>Clinic information, not medical advice.</span><button class="clear" type="button">Clear chat</button></footer>
  </section><button class="launcher" type="button" aria-label="Open HM virtual receptionist" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11.5a8 8 0 0 1-8 8H5l-4 3 1.5-6A8 8 0 1 1 20 11.5Z"/><path d="M6 10h8m-8 4h5"/></svg><span>Ask HM</span><i aria-hidden="true"></i></button>`;
  root.append(ui); document.body.append(host);
  const $ = selector => root.querySelector(selector);
  const panel=$('.panel'), launcher=$('.launcher'), messages=$('.messages'), actions=$('.actions'), input=$('input'), typing=$('.typing');
  let session=null, language='en', busy=false, started=false, review=null, config=null, stage='idle', expiryTimer;
  const initialActions=[['Book an Appointment','book'],['Ask About Tests','tests'],['Test Prices','prices'],['Opening Hours & Location','hours'],['Talk to Reception','reception']];
  const scroll = () => { messages.scrollTop=messages.scrollHeight; };
  function forgetContactDisplay(){root.querySelectorAll('.sensitive,.review').forEach(node=>node.remove());}
  function touch(){
    clearTimeout(expiryTimer);
    expiryTimer=setTimeout(()=>{session=null;review=null;started=false;stage='idle';messages.replaceChildren();actions.replaceChildren();input.value='';bubble('This chat was cleared after inactivity. Start a new chat when you’re ready.','notice');showActions([{label:'Start new chat',action:'newsession'}]);},(config?.session_ttl_minutes||30)*60000);
  }
  function bubble(text, kind='assistant') {
    const node=document.createElement('div'); node.className='bubble '+kind; node.textContent=text; node.dir='auto'; messages.append(node); scroll(); return node;
  }
  function setBusy(value) {
    busy=value; typing.hidden=!value; input.disabled=value; $('.send').disabled=value;
    actions.querySelectorAll('button').forEach(button=>button.disabled=value);
    root.querySelectorAll('.submit-request:not([data-stale])').forEach(button=>button.disabled=value);
    if (!value && !panel.hidden) input.focus({preventScroll:true});
  }
  async function json(path, body) {
    const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),45000);
    try {
      const response=await fetch(api+path,{method:body?'POST':'GET',credentials:'omit',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,signal:controller.signal,referrerPolicy:'no-referrer'});
      const data=await response.json();
      if (!response.ok) { const error=new Error(typeof data.detail==='string'?data.detail:'Please check your request or contact reception.'); error.status=response.status; throw error; }
      return data;
    } finally {clearTimeout(timer);}
  }
  function showActions(items) {
    actions.replaceChildren();
    items.forEach(item=>{
      const button=document.createElement('button'); button.type='button'; button.textContent=item.label;
      button.addEventListener('click',()=>{
        if (item.action==='reconnect') {started=false; session=null; initialize();}
        else if (item.action==='newsession') clearChat();
        else chat('',item.action,item.label);
      }); actions.append(button);
    });
  }
  function setMode(demo) {
    $('.mode').hidden=!demo;
    $('.mode').textContent=language==='ur'?'صرف ڈیمو · فرضی معلومات استعمال کریں · قیمتیں تصدیق شدہ نہیں':'DEMO · Fictional booking details only · Prices are illustrative';
    $('.subtitle').textContent=demo?'Virtual receptionist · Demo':'Your virtual receptionist';
  }
  function render(response) {
    root.querySelectorAll('.submit-request').forEach(button=>{button.disabled=true;button.dataset.stale='true';});
    session=response.session_id;
    stage=response.state; touch();
    if(stage==='idle'||stage==='consent')forgetContactDisplay();
    bubble(response.reply);
    setMode(response.demo_mode);
    input.type=({phone:'tel',date:'date',time:'time'})[response.state]||'text';
    input.value='';input.removeAttribute('min');input.maxLength=response.state==='notes'?240:1000;
    if (response.state==='date') input.min=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Karachi',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    input.placeholder=language==='ur'?'اپنا پیغام لکھیں…':'Type your message…';
    showActions(response.quick_actions||[]);
    if (response.sources?.length) {
      const sources=document.createElement('div');sources.className='sources';
      response.sources.slice(0,3).forEach((url,index)=>{
        try {const parsed=new URL(url);if(parsed.protocol!=='https:'||!['hmdiagnosticsandclinics.com','www.hmdiagnosticsandclinics.com'].includes(parsed.hostname))return;}catch{return;}
        const link=document.createElement('a');link.href=url;link.target='_blank';link.rel='noopener noreferrer';link.textContent='Clinic source '+(index+1)+' ↗';sources.append(link);
      }); messages.append(sources);
    }
    review=null;
    if (response.summary && response.confirmation_token) {
      review={confirmation_token:response.confirmation_token,idempotency_key:response.idempotency_key};
      const card=document.createElement('section');card.className='review';card.setAttribute('aria-label','Review your request');
      const labels={patient_name:'Name',phone:'Mobile',service:'Service',preferred_date:'Preferred date',preferred_time:'Preferred time',notes:'Scheduling note'};
      const list=document.createElement('dl');
      Object.entries(response.summary).forEach(([key,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=labels[key]||key;dd.textContent=value||'—';list.append(dt,dd);});
      const confirm=document.createElement('button');confirm.type='button';confirm.className='submit-request';confirm.textContent=language==='ur'?'تفصیلات درست ہیں، درخواست جمع کریں':'Details are correct — submit request';confirm.addEventListener('click',submitRequest);
      card.append(list,confirm);messages.append(card);
    }
    scroll();
  }
  function showError(error, submission=false) {
    const text=error.name==='AbortError'?'The service is taking longer than expected. It may be waking up. Please try again shortly.':error.message;
    const notice=bubble((submission?'We couldn’t verify your submission. Retry the same request or call reception. ':'')+text,'notice');
    const phone=config?.reception_phone||script?.dataset.receptionPhone||'0334-6333044';
    if(/^[+\d -]{7,20}$/.test(phone)){const link=document.createElement('a');link.href='tel:'+phone.replace(/[^+\d]/g,'');link.textContent='Call reception: '+phone;notice.append(document.createElement('br'),link);}
    if(error.status===401){session=null;review=null;showActions([{label:'Start new chat',action:'newsession'}]);}
    else if(!started||!session)showActions([{label:'Retry connection',action:'reconnect'}]);
    scroll();
  }
  async function chat(message='',action=null,label=null) {
    if(busy)return;
    if(message||label){const node=bubble(label||message,'visitor');if(!['idle','submitted','consent'].includes(stage))node.classList.add('sensitive');}
    setBusy(true);
    try {render(await json('/api/chat',{message,session_id:session,action,consent:action==='consent',language}));started=true;}
    catch(error){showError(error);}finally{setBusy(false);}
  }
  async function initialize(){
    if(started||busy)return;
    setBusy(true);
    try{config=await json('/api/config');setMode(config.demo_mode);}catch(error){showError(error);setBusy(false);return;}
    setBusy(false);await chat();
  }
  async function submitRequest(){
    if(busy||!review)return;
    setBusy(true);
    try{
      const result=await json('/api/appointments',{session_id:session,confirmation_token:review.confirmation_token,idempotency_key:review.idempotency_key,confirmed:true});
      bubble(result.message+'\nRequest ID: '+result.request_id+'\nStatus: '+result.status);
      root.querySelectorAll('.submit-request').forEach(button=>{button.disabled=true;button.textContent='Request received · Pending';});
      forgetContactDisplay();
      review=null;stage='submitted';touch();showActions(initialActions.map(([label,action])=>({label,action})));input.type='text';input.value='';
    }catch(error){showError(error,true);}finally{setBusy(false);if(!review)root.querySelectorAll('.submit-request').forEach(button=>button.disabled=true);}
  }
  function open(){panel.hidden=false;launcher.setAttribute('aria-expanded','true');launcher.setAttribute('aria-label','Minimize HM virtual receptionist');if(!started)initialize();else input.focus();}
  function close(){panel.hidden=true;launcher.setAttribute('aria-expanded','false');launcher.setAttribute('aria-label','Open HM virtual receptionist');launcher.focus();}
  launcher.addEventListener('click',()=>panel.hidden?open():close());$('.close').addEventListener('click',close);
  root.addEventListener('keydown',event=>{if(event.key==='Escape'&&!panel.hidden){event.preventDefault();close();}});
  $('.composer').addEventListener('submit',event=>{event.preventDefault();const message=input.value.trim();if(message){input.value='';chat(message);}});
  $('.language').addEventListener('click',()=>{language=language==='en'?'ur':'en';$('.language').textContent=language==='en'?'اردو':'English';panel.dir=language==='ur'?'rtl':'ltr';if(config)setMode(config.demo_mode);input.placeholder=language==='ur'?'اپنا پیغام لکھیں…':'Type your message…';});
  async function clearChat(){
    if(busy)return;
    if(session){try{await json('/api/chat',{session_id:session,message:'',action:'cancel',consent:false,language});}catch{}}
    session=null;review=null;started=false;stage='idle';clearTimeout(expiryTimer);messages.replaceChildren();actions.replaceChildren();input.type='text';input.value='';await initialize();
  }
  $('.clear').addEventListener('click',clearChat);
})();

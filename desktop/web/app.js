'use strict';
const $ = selector => document.querySelector(selector);
const tokenKey='bunnygram_controller_token_v3';
let token=localStorage.getItem(tokenKey)||'';
let current=null;
let previewURL=null;
let busy=false;
let polling=false;
let toastTimer=0;
const petLabels={bunny:'Bunny',cat:'Cat',fox:'Fox',frog:'Frog',cookie:'Chocolate chip cookie',bee:'Bee'};
const emotes={wave:'waving',hop:'hopping around',dance:'dancing',sleep:'taking a nap',sit:'sitting peacefully',curious:'looking around',heart:'feeling loved',star:'making a wish',flower:'admiring a flower',present:'opening a present',happy:'so happy',idle:'relaxing',blink:'blinking'};

function toast(message){let el=$('#toast');el.textContent=message;el.classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('visible'),2800);}
function online(status){$('#connection').classList.toggle('connected',status);$('#connectionText').textContent=status?'Connected':'Offline';}
function pairing(){ $('#pairScreen').hidden=false;$('#dashboard').hidden=true;online(false); }
function dashboard(){ $('#pairScreen').hidden=true;$('#dashboard').hidden=false;online(true); }
async function request(path, method='GET', obj=null){
  const headers={};if(token)headers['X-Bunnygram-Token']=token;
  if(obj!==null)headers['Content-Type']='application/json';
  const res=await fetch(path,{method,headers,body:obj===null?undefined:JSON.stringify(obj),cache:'no-store'});
  let result;try{result=await res.json();}catch{throw new Error('Unexpected server response')}
  if(res.status===401){token='';localStorage.removeItem(tokenKey);pairing();}
  if(!res.ok)throw new Error(result.error||'Something went wrong');
  return result;
}
async function command(action, opts={}){
  if(busy)return;
  busy=true;
  try{await request('/api/action','POST',{action,...opts});await refresh();}
  catch(e){toast(e.message)}finally{busy=false}
}
function renderPets(status){
  const picker=$('#petPicker');
  const ids=Object.keys(status.pets);
  if(picker.children.length!==ids.length){
    picker.replaceChildren();
    ids.forEach(id=>{
      const item=document.createElement('button');item.type='button';item.className='pet-card';item.dataset.pet=id;
      const pic=document.createElement('img');pic.src=`/assets/${id}/idle_0.png`;pic.alt='';
      const name=document.createElement('span');name.className='pet-name';
      const sub=document.createElement('span');sub.className='pet-type';sub.textContent=petLabels[id];
      item.append(pic,name,sub);picker.append(item);
      item.addEventListener('click',()=>command('switch_pet',{pet:id}));
    });
  }
  ids.forEach(id=>{
    const button=picker.querySelector(`[data-pet="${id}"]`);
    button.classList.toggle('chosen',id===status.pet);
    button.setAttribute('aria-pressed',id===status.pet?'true':'false');
    button.querySelector('.pet-name').textContent=status.pets[id].name;
  });
}
function mailDate(timestamp){return new Date(timestamp*1000).toLocaleDateString(undefined,{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});}
function renderMail(status){
  const host=$('#mailList');host.replaceChildren();
  $('#mailCount').textContent=String(status.mail.length);
  if(!status.mail.length){const empty=document.createElement('p');empty.className='muted';empty.textContent='No letters yet. Send the first one!';host.append(empty);return;}
  status.mail.slice(0,30).forEach(item=>{
    const card=document.createElement('article');card.className='mail-card'+(!item.opened?' is-unread':'');
    const meta=document.createElement('div');meta.className='mail-meta';
    const title=document.createElement('strong');title.textContent=(item.kind==='gift'?'🎁':'💌')+' From '+item.from;
    const when=document.createElement('span');when.textContent=mailDate(item.received_at);meta.append(title,when);card.append(meta);
    const body=document.createElement('p');body.textContent=item.opened?item.text:'A little message is waiting to be opened ♥';card.append(body);
    if(!item.opened){const button=document.createElement('button');button.type='button';button.className='button soft';button.textContent='Open letter';button.addEventListener('click',()=>command('open_mail',{id:item.id}));card.append(button);}
    host.append(card);
  });
}
function render(status){
  const different=!current||current.pet!==status.pet;
  current=status;dashboard();renderPets(status);
  $('#friendTitle').textContent=status.pet_name+' is here ♡';
  $('#personality').textContent=status.pets[status.pet].personality;
  $('#activity').textContent=status.pet_name+' is '+(emotes[status.activity]||'hanging out')+'.';
  $('#unreadTop').textContent=status.unread?`${status.unread} unread 💌`:'All letters read ♡';
  if(different||document.activeElement!==$('#renameInput')){$('#renameInput').value=status.pet_name;}
  [...document.querySelectorAll('input[data-setting]')].forEach(input=>{if(document.activeElement!==input)input.checked=!!status.settings[input.dataset.setting];});
  if(document.activeElement!==$('#brightness')){$('#brightness').value=status.settings.brightness;$('#brightnessValue').textContent=status.settings.brightness+'%';}
  renderMail(status);
}
async function refresh(){if(polling||!token)return;polling=true;
  try{let status=await request('/api/status');render(status);}catch(e){online(false);if(!String(e.message).includes('Pair your phone'))console.debug(e.message)}
  finally{polling=false}
}
async function preview(){if(!token||$('#dashboard').hidden)return;
  try{
    const response=await fetch('/api/preview',{headers:{'X-Bunnygram-Token':token},cache:'no-store'});
    if(!response.ok)return;
    const blob=await response.blob();const next=URL.createObjectURL(blob);
    const img=$('#displayPreview');img.src=next;
    if(previewURL)URL.revokeObjectURL(previewURL);previewURL=next;
  }catch(e){/* status polling handles the offline indicator */}
}
$('#pairForm').addEventListener('submit',async ev=>{
  ev.preventDefault();
  try{
    const code=$('#pairCode').value.trim();const response=await request('/api/pair','POST',{code});
    token=response.token;localStorage.setItem(tokenKey,token);toast('Paired! Your little friend says hello ♥');
    $('#pairCode').value='';await refresh();await preview();
  }catch(e){toast(e.message)}
});
document.querySelectorAll('[data-reaction]').forEach(btn=>btn.addEventListener('click',()=>command('react',{reaction:btn.dataset.reaction})));
$('#renameButton').addEventListener('click',()=>command('rename',{name:$('#renameInput').value}));
$('#letterForm').addEventListener('submit',async ev=>{
  ev.preventDefault();
  const choice=$('#giftType').value;
  const data={action:'send_mail',from:$('#sender').value,text:$('#letter').value,
              kind:choice==='letter'?'letter':'gift',gift:choice==='letter'?'heart':choice};
  if(!data.text.trim())return toast('Write a little message first');
  if(busy)return;busy=true;
  try{await request('/api/action','POST',data);$('#letter').value='';toast('Delivered to the display 💌');await refresh();}
  catch(e){toast(e.message)}finally{busy=false}
});
document.querySelectorAll('[data-setting]').forEach(input=>input.addEventListener('change',()=>command('setting',{setting:input.dataset.setting,value:input.checked})));
$('#brightness').addEventListener('input',ev=>{$('#brightnessValue').textContent=ev.target.value+'%'});
$('#brightness').addEventListener('change',ev=>command('setting',{setting:'brightness',value:Number(ev.target.value)}));
$('#reloadButton').addEventListener('click',()=>{command('reload_sprites');toast('Reload requested');});
$('#screenshotButton').addEventListener('click',()=>{command('save_screenshot');toast('Saved on display computer');});
$('#unpair').addEventListener('click',()=>{token='';localStorage.removeItem(tokenKey);pairing();toast('This phone is unpaired');});
if(token){refresh().then(preview)}else pairing();
setInterval(refresh,2200);setInterval(preview,3000);

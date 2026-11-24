'use strict';
const PETS = [['bunny','🐰'],['cat','🐱'],['fox','🦊'],['frog','🐸'],['cookie','🍪'],['bee','🐝']];
const RX = [['wave','👋 Wave'],['hop','✨ Hop'],['dance','🎵 Dance'],['happy','💖 Happy'],['sleep','💤 Nap'],['curious','👀 Curious'],['heart','💕 Heart'],['flower','🌷 Flower'],['present','🎁 Gift']];
const el = (id) => document.getElementById(id);
const error = (msg) => el('error').textContent = msg || '';
let role = null, displayed = null;
async function req(path, data) {
  const opts = {credentials:'same-origin',headers:{'Accept':'application/json'}};
  if (data !== undefined) { opts.method = 'POST'; opts.headers['Content-Type'] = 'application/json'; opts.body=JSON.stringify(data); }
  const response = await fetch(path,opts);
  let answer; try {answer = await response.json();} catch {throw new Error('Server returned an invalid response');}
  if (!response.ok) throw new Error(answer.detail || answer.error || `HTTP ${response.status}`);
  return answer;
}
function showLogin(msg='') {el('pair').classList.remove('hidden');el('app').classList.add('hidden');el('pairError').textContent=msg;}
function showApp() {el('pair').classList.add('hidden');el('app').classList.remove('hidden');}
async function login() {
  try { const info = await req('/api/login',{password:el('code').value}); el('code').value=''; role=info.role; showApp(); await refresh(); }
  catch(err) {el('pairError').textContent=err.message;}
}
async function logout() {try {await req('/api/logout',{});} catch(e){} showLogin();}
async function action(name, extra={}) {
  try {error(''); const queued=await req('/api/action',{action:name,...extra});
    el('queue').textContent=`Queued #${queued.command_id}`;await refresh();}
  catch(err){error(err.message);}
}
function pick(pet) {action('switch_pet',{pet});}
function renamePet() {action('rename',{name:el('newName').value});}
function setting(key,value) {action('setting',{setting:key,value});}
async function sendLetter() {
  const message=el('message').value.trim(); if(!message)return;
  try {const result=await req('/api/action',{action:'send_mail',text:message,sender:el('sender').value.trim()||'Your person'});
    el('message').value='';el('success').textContent=`Letter queued (#${result.command_id}). It will arrive when the display connects. ♥`;
    await refresh();}catch(err){error(err.message);}
}
function render(result) {
  role=result.role;
  el('letterCard').classList.toggle('hidden',role!=='owner');
  const online=result.online;
  el('status').textContent = online ? '● Connected' : '○ Offline';
  el('status').className = online ? 'online' : 'offline';
  el('queue').textContent = result.pending ? `${result.pending} queued` : 'Up to date';
  const s=result.state || {};displayed=s;
  if(!s.pet) {el('preview').textContent='♡';el('pets').textContent='Waiting for the companion to connect…';return;}
  el('preview').textContent=(PETS.find(p=>p[0]===s.pet)||PETS[0])[1];
  if(document.activeElement!==el('newName')) el('newName').value=(s.names||{})[s.pet]||'';
  el('unread').textContent=s.unread?`(${s.unread} new)`:'';
  const pets=el('pets');pets.replaceChildren();
  PETS.forEach(([pet,emoji]) => { const b=document.createElement('button');b.className='pet'+(pet===s.pet?' active':'');
    const e=document.createElement('span');e.className='emo';e.textContent=emoji;
    const n=document.createElement('span');n.className='pname';n.textContent=(s.names||{})[pet]||pet;
    b.append(e,n);b.addEventListener('click',()=>pick(pet));pets.append(b); });
  for(const key of ['display_on','mirror_x','mirror_y'])el(key).checked=!!s[key];
  for(const key of ['rotation','scale','brightness'])if(s[key]!==undefined)el(key).value=String(s[key]);
  el('brightLabel').textContent=s.brightness+'%';
  const area=el('mail');area.replaceChildren();
  if(!Array.isArray(s.mail)||!s.mail.length) {area.textContent='No letters yet ✨';return;}
  s.mail.forEach(m=>{const card=document.createElement('div');card.className='mail'+(!m.opened?' unread':'');
    const heading=document.createElement('strong');heading.textContent='💌 '+(m.from||'Someone')+(m.opened?'':' · NEW');
    const txt=document.createElement('p');txt.style.whiteSpace='pre-wrap';txt.textContent=m.text||'';
    card.append(heading,txt);
    if(!m.opened) {const b=document.createElement('button');b.textContent='Mark as read';b.onclick=()=>action('open_mail',{id:m.id});card.append(b);}
    area.append(card);});
}
async function refresh() {
  try {const response=await req('/api/state');showApp();render(response);error('');}
  catch(err) {if(err.message.includes('Sign in')||err.message.includes('session')||err.message.includes('Session'))showLogin('Please sign in.');else error('Could not refresh: '+err.message);}
}
function init() {
  el('loginButton').addEventListener('click',login);
  el('code').addEventListener('keydown',e=>{if(e.key==='Enter')login();});
  el('logoutButton').addEventListener('click',logout);
  el('renameButton').addEventListener('click',renamePet);
  el('sendButton').addEventListener('click',sendLetter);
  const reactions=el('reactions');
  RX.forEach(([key,name])=>{const b=document.createElement('button');b.textContent=name;b.onclick=()=>action('react',{reaction:key});reactions.append(b);});
  for(const key of ['mirror_x','mirror_y','display_on'])el(key).addEventListener('change',e=>setting(key,e.target.checked));
  for(const key of ['scale','rotation','brightness'])el(key).addEventListener('change',e=>setting(key,Number(e.target.value)));
  el('brightness').addEventListener('input',e=>el('brightLabel').textContent=e.target.value+'%');
  showLogin();refresh();setInterval(()=>{if(!el('app').classList.contains('hidden'))refresh();},4000);
}
init();

(() => {
  const root = document.querySelector('[data-design-studio]');
  if (!root) return;
  const initial = JSON.parse(document.getElementById('design-data').textContent || '{}');
  const fields = JSON.parse(document.getElementById('design-fields').textContent || '[]');
  const samples = JSON.parse(document.getElementById('design-samples').textContent || '{}');
  const canvas = document.getElementById('design-canvas');
  const pageTabs = document.getElementById('page-tabs');
  const widthInput = document.getElementById('page-width');
  const heightInput = document.getElementById('page-height');
  let state = JSON.parse(JSON.stringify(initial));
  if (!state.pages || !state.pages.length) state = {version:1,pages:[{id:'page-1',name:'Front',elements:[]}]};
  let activePage = 0, selectedId = null, zoom = 1, backgroundPreview = root.dataset.backgroundUrl || '';
  const undoStack = [], redoStack = [];
  const mmToPx = 3;
  const byId = id => document.getElementById(id);
  const currentPage = () => state.pages[activePage];
  const selected = () => currentPage().elements.find(e => e.id === selectedId) || null;
  const uid = prefix => `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,7)}`;
  const deep = obj => JSON.parse(JSON.stringify(obj));
  function remember(){ undoStack.push(deep(state)); if(undoStack.length>60) undoStack.shift(); redoStack.length=0; updateHistoryButtons(); }
  function updateHistoryButtons(){ byId('undo-btn').disabled=!undoStack.length; byId('redo-btn').disabled=!redoStack.length; }
  function undo(){ if(!undoStack.length)return; redoStack.push(deep(state)); state=undoStack.pop(); selectedId=null; render(); updateHistoryButtons(); }
  function redo(){ if(!redoStack.length)return; undoStack.push(deep(state)); state=redoStack.pop(); selectedId=null; render(); updateHistoryButtons(); }
  function sample(binding){ return samples[binding] || (binding ? binding.split('.').pop().replaceAll('_',' ') : ''); }
  function clampElement(el){ const w=parseFloat(widthInput.value),h=parseFloat(heightInput.value); el.width=Math.max(.5,Math.min(parseFloat(el.width)||1,w));el.height=Math.max(.5,Math.min(parseFloat(el.height)||1,h));el.x=Math.max(0,Math.min(parseFloat(el.x)||0,w-el.width));el.y=Math.max(0,Math.min(parseFloat(el.y)||0,h-el.height)); }
  function addElement(type,binding='',label=''){
    remember(); const w=parseFloat(widthInput.value),h=parseFloat(heightInput.value);
    const base={id:uid(type),type,x:Math.max(2,w*.08),y:Math.max(2,h*.08),width:Math.min(60,w*.55),height:Math.min(9,h*.12),fontSize:10,fontFamily:'Helvetica',align:'left',color:'#0F172A',borderColor:'#CBD5E1',borderWidth:.5,prefix:'',suffix:''};
    if(type==='text'){base.text='New text';}
    if(type==='field'){base.binding=binding;base.width=Math.min(70,w*.65);}
    if(type==='image'){base.binding=binding;base.width=Math.min(30,w*.3);base.height=Math.min(30,h*.3);base.fit='contain';}
    if(type==='qr'){base.binding=binding||'document.verification_url';base.width=Math.min(25,w*.25);base.height=base.width;}
    if(type==='rectangle'){base.width=Math.min(60,w*.55);base.height=Math.min(25,h*.25);base.backgroundColor='#E2E8F0';}
    if(type==='line'){base.width=Math.min(60,w*.55);base.height=2;}
    if(type==='results_table'){base.width=Math.min(180,w*.88);base.height=Math.min(140,h*.55);base.fontSize=8;base.headerColor='#1E3A8A';}
    currentPage().elements.push(base);selectedId=base.id;render();
  }
  function renderTabs(){pageTabs.innerHTML='';state.pages.forEach((p,i)=>{const b=document.createElement('button');b.type='button';b.className='ds-page-tab'+(i===activePage?' active':'');b.textContent=p.name||`Page ${i+1}`;b.onclick=()=>{activePage=i;selectedId=null;render();};pageTabs.appendChild(b);});}
  function elementContent(el){
    if(el.type==='text') return el.text||'';
    if(el.type==='field') return `${el.prefix||''}${sample(el.binding)}${el.suffix||''}`;
    if(el.type==='image') return `<div><i class="ph ph-image" style="font-size:20px"></i><br>${fields.find(f=>f.binding===el.binding)?.label||'Image'}</div>`;
    if(el.type==='qr') return '<div><i class="ph ph-qr-code" style="font-size:26px"></i><br>Verification QR</div>';
    if(el.type==='results_table') return '<table class="ds-mini-table"><tr><th>Subject</th><th>%</th><th>Grade</th></tr><tr><td>Mathematics</td><td>82</td><td>A</td></tr><tr><td>English</td><td>76</td><td>B+</td></tr><tr><td>Science</td><td>88</td><td>A</td></tr></table>';
    return '';
  }
  function renderCanvas(){
    const width=parseFloat(widthInput.value),height=parseFloat(heightInput.value);canvas.style.width=`${width*mmToPx}px`;canvas.style.height=`${height*mmToPx}px`;canvas.style.transform=`scale(${zoom})`;canvas.style.marginBottom=`${Math.max(0,(zoom-1)*height*mmToPx)}px`;
    if(backgroundPreview){canvas.style.backgroundImage=`url("${backgroundPreview}")`;const fit=byId('background-fit').value;canvas.style.backgroundSize=fit==='STRETCH'?'100% 100%':fit.toLowerCase();}else{canvas.style.backgroundImage='none';}
    canvas.innerHTML='';
    currentPage().elements.forEach(el=>{clampElement(el);const node=document.createElement('div');node.className='ds-element'+(el.id===selectedId?' selected':'');node.dataset.id=el.id;node.dataset.type=el.type;node.style.left=`${el.x*mmToPx}px`;node.style.top=`${el.y*mmToPx}px`;node.style.width=`${el.width*mmToPx}px`;node.style.height=`${el.height*mmToPx}px`;node.style.color=el.color||'#0F172A';node.style.fontSize=`${(el.fontSize||10)*0.82}px`;node.style.fontWeight=el.bold?'800':'400';node.style.textAlign=el.align||'left';if(el.type==='rectangle'){node.style.background=el.backgroundColor||'transparent';node.style.borderColor=el.borderColor||'#CBD5E1';node.style.borderWidth=`${el.borderWidth||0}px`;}
      const content=document.createElement('div');content.className='ds-content';content.innerHTML=elementContent(el);if(['text','field'].includes(el.type)){content.style.justifyContent=el.align==='center'?'center':el.align==='right'?'flex-end':'flex-start';}node.appendChild(content);const handle=document.createElement('span');handle.className='ds-resize-handle';node.appendChild(handle);node.addEventListener('pointerdown',e=>startPointer(e,el,handle.contains(e.target)));node.onclick=e=>{e.stopPropagation();selectElement(el.id);};canvas.appendChild(node);});
  }
  function render(){renderTabs();renderCanvas();renderProperties();}
  function selectElement(id){selectedId=id;renderCanvas();renderProperties();}
  function startPointer(event,el,resizing){event.preventDefault();event.stopPropagation();selectElement(el.id);remember();const startX=event.clientX,startY=event.clientY,ox=Number(el.x),oy=Number(el.y),ow=Number(el.width),oh=Number(el.height);const scale=mmToPx*zoom;const move=e=>{const dx=(e.clientX-startX)/scale,dy=(e.clientY-startY)/scale;if(resizing){el.width=Math.max(1,ow+dx);el.height=Math.max(1,oh+dy);}else{el.x=ox+dx;el.y=oy+dy;}clampElement(el);renderCanvas();syncProperties();};const up=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up);};window.addEventListener('pointermove',move);window.addEventListener('pointerup',up);}
  function renderProperties(){const el=selected();byId('empty-properties').hidden=!!el;byId('property-form').hidden=!el;if(!el)return;byId('prop-type').value=el.type;syncProperties();document.querySelector('[data-prop="text"]').style.display=el.type==='text'?'flex':'none';document.querySelector('[data-prop="binding"]').style.display=['field','image','qr'].includes(el.type)?'flex':'none';}
  function syncProperties(){const el=selected();if(!el)return;byId('prop-x').value=Number(el.x).toFixed(1);byId('prop-y').value=Number(el.y).toFixed(1);byId('prop-width').value=Number(el.width).toFixed(1);byId('prop-height').value=Number(el.height).toFixed(1);byId('prop-text').value=el.text||'';byId('prop-binding').value=el.binding||'';byId('prop-prefix').value=el.prefix||'';byId('prop-suffix').value=el.suffix||'';byId('prop-font-size').value=el.fontSize||10;byId('prop-align').value=el.align||'left';byId('prop-color').value=el.color||'#0F172A';byId('prop-border-color').value=el.borderColor||'#CBD5E1';byId('prop-bold').checked=!!el.bold;}
  function bindProperty(id,key,parser=v=>v){const input=byId(id);input.addEventListener('change',()=>{const el=selected();if(!el)return;remember();el[key]=parser(input.type==='checkbox'?input.checked:input.value);clampElement(el);render();});input.addEventListener('input',()=>{const el=selected();if(!el)return;el[key]=parser(input.type==='checkbox'?input.checked:input.value);clampElement(el);renderCanvas();});}
  bindProperty('prop-x','x',Number);bindProperty('prop-y','y',Number);bindProperty('prop-width','width',Number);bindProperty('prop-height','height',Number);bindProperty('prop-text','text');bindProperty('prop-binding','binding');bindProperty('prop-prefix','prefix');bindProperty('prop-suffix','suffix');bindProperty('prop-font-size','fontSize',Number);bindProperty('prop-align','align');bindProperty('prop-color','color');bindProperty('prop-border-color','borderColor');bindProperty('prop-bold','bold',Boolean);
  function deleteSelected(){if(!selectedId)return;remember();currentPage().elements=currentPage().elements.filter(e=>e.id!==selectedId);selectedId=null;render();}
  document.querySelectorAll('[data-add-element]').forEach(b=>b.onclick=()=>addElement(b.dataset.addElement));
  document.querySelectorAll('[data-add-binding]').forEach(b=>b.onclick=()=>{const kind=b.dataset.kind;addElement(kind==='results_table'?'results_table':kind,b.dataset.addBinding,b.dataset.label);});
  byId('delete-element-btn').onclick=deleteSelected;canvas.onclick=()=>{selectedId=null;renderCanvas();renderProperties();};
  byId('add-page-btn').onclick=()=>{remember();state.pages.push({id:uid('page'),name:`Page ${state.pages.length+1}`,elements:[]});activePage=state.pages.length-1;selectedId=null;render();};
  byId('zoom-range').oninput=e=>{zoom=Number(e.target.value)/100;byId('zoom-value').textContent=`${e.target.value}%`;renderCanvas();};
  byId('undo-btn').onclick=undo;byId('redo-btn').onclick=redo;
  [widthInput,heightInput].forEach(input=>input.onchange=()=>{remember();currentPage().elements.forEach(clampElement);render();});
  const bgInput=byId('background-input');bgInput.onchange=()=>{if(!bgInput.files[0])return;const reader=new FileReader();reader.onload=e=>{backgroundPreview=e.target.result;renderCanvas();};reader.readAsDataURL(bgInput.files[0]);};byId('background-fit').onchange=renderCanvas;
  function save(){byId('design-json').value=JSON.stringify(state);byId('save-width').value=widthInput.value;byId('save-height').value=heightInput.value;byId('save-background-fit').value=byId('background-fit').value;const target=byId('save-background');if(bgInput.files.length){const dt=new DataTransfer();dt.items.add(bgInput.files[0]);target.files=dt.files;}byId('save-form').requestSubmit();}
  byId('save-btn').onclick=save;
  byId('preview-btn').onclick=()=>{const student=byId('preview-student').value,term=byId('preview-term').value;const url=new URL(window.DESIGN_STUDIO_PREVIEW_URL,window.location.origin);url.searchParams.set('version',document.querySelector('[name=version_id]').value);if(student)url.searchParams.set('student',student);if(term)url.searchParams.set('term',term);window.open(url.toString(),'_blank','noopener');};
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();save();return;}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();e.shiftKey?redo():undo();return;}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='y'){e.preventDefault();redo();return;}const tag=document.activeElement?.tagName;if(['INPUT','TEXTAREA','SELECT'].includes(tag))return;const el=selected();if(!el)return;if(e.key==='Delete'||e.key==='Backspace'){e.preventDefault();deleteSelected();return;}const moves={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};if(moves[e.key]){e.preventDefault();remember();el.x+=moves[e.key][0]*(e.shiftKey?5:1);el.y+=moves[e.key][1]*(e.shiftKey?5:1);clampElement(el);render();}});
  updateHistoryButtons();render();
})();

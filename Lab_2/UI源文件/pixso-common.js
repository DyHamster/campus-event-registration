
const C={bg:'#F5F6F3',white:'#FFFFFF',ink:'#182E29',muted:'#73817B',green:'#174F43',deep:'#103D34',lime:'#DAF29A',line:'#E2E7E0',soft:'#E8F0E8',amber:'#9C6425',amberBg:'#FAEEDB',red:'#B4423E',redBg:'#FBECE9',blue:'#386B91',blueBg:'#EAF2F9'};
await pixso.loadFontAsync({family:'Noto Sans SC',style:'Regular'});
await pixso.loadFontAsync({family:'Noto Sans SC',style:'Medium'});
await pixso.loadFontAsync({family:'Noto Sans SC',style:'Bold'});
await pixso.loadFontAsync({family:'Inter',style:'Regular'});
await pixso.loadFontAsync({family:'Inter',style:'Bold'});
const created=[], actions=[];
function rgb(h){h=h.replace('#','');return {r:parseInt(h.slice(0,2),16)/255,g:parseInt(h.slice(2,4),16)/255,b:parseInt(h.slice(4,6),16)/255};}
function solid(h){return [{type:'SOLID',color:rgb(h)}];}
function rect(p,x,y,w,h,color,r=0,name=''){const n=pixso.createRectangle();p.appendChild(n);n.name=name||'背景';n.resize(w,h);n.x=x;n.y=y;n.fills=solid(color);if(r)n.cornerRadius=r;return n;}
function frame(p,x,y,w,h,color,r=0,name=''){const n=pixso.createFrame();p.appendChild(n);n.name=name||'容器';n.resize(w,h);n.x=x;n.y=y;n.fills=solid(color);n.clipsContent=true;if(r)n.cornerRadius=r;return n;}
function ellipse(p,x,y,w,h,color){const n=pixso.createEllipse();p.appendChild(n);n.resize(w,h);n.x=x;n.y=y;n.fills=solid(color);return n;}
function chev(p,x,y,color=C.muted){const n=pixso.createVector();p.appendChild(n);n.vectorPaths=[{windingRule:'NONZERO',data:'M 0 0 L 4 4 L 8 0'}];n.fills=[];n.strokes=solid(color);n.strokeWeight=1.5;n.x=x;n.y=y;n.name='下拉箭头';return n;}
function text(p,x,y,s,size=14,color=C.ink,bold=false,w=0){if(s.includes('⌄')){const clean=s.replace(/\s*⌄/g,'').trim();if(!clean)return chev(p,x,y+size*0.6,color);const t=text(p,x,y,clean,size,color,bold,w);chev(p,x+t.width+9,y+size*0.7,color);return t;}const n=pixso.createText();p.appendChild(n);n.fontName={family:'Noto Sans SC',style:bold?'Bold':'Regular'};n.fontSize=size;n.lineHeight={unit:'PERCENT',value:150};n.characters=s;n.fills=solid(color);if(w){n.textAutoResize='HEIGHT';n.resize(w,Math.max(size*1.5,n.height));}n.x=x;n.y=y;n.name=s.slice(0,45);return n;}
function num(p,x,y,s,size=32,color=C.ink){const n=text(p,x,y,s,size,color,true);n.fontName={family:'Inter',style:'Bold'};return n;}
function line(p,x,y,w,color=C.line){return rect(p,x,y,w,1,color);}
function panel(p,x,y,w,h,name='面板'){const n=frame(p,x,y,w,h,C.white,16,name);n.strokes=solid(C.line);n.strokeWeight=1;return n;}
function pill(p,x,y,label,tone='green',w=0){const colors={green:[C.soft,C.green],amber:[C.amberBg,C.amber],red:[C.redBg,C.red],blue:[C.blueBg,C.blue],gray:['#F0F2EE',C.muted]};let [bg,fg]=colors[tone]||colors.green;w=w||label.length*12+22;const n=frame(p,x,y,w,28,bg,14,'状态 / '+label);text(n,11,4,label,12,fg,true);return n;}
function button(p,x,y,w,label,kind='primary',target=''){const bg=kind==='primary'?C.green:kind==='lime'?C.lime:kind==='danger'?C.redBg:kind==='disabled'?'#E9ECE6':C.white;const fg=kind==='primary'?C.white:kind==='danger'?C.red:kind==='disabled'?C.muted:C.green;const n=frame(p,x,y,w,44,bg,8,'按钮 / '+label);if(kind==='secondary'){n.strokes=solid(C.line);n.strokeWeight=1;}const t=text(n,0,11,label,14,fg,true);t.x=(w-t.width)/2;if(target)actions.push({nodeId:n.id,target});return n;}
function field(p,x,y,w,label,value,opts={}){text(p,x,y,label,13,C.ink,true);const n=frame(p,x,y+28,w,46,opts.disabled?'#F0F2EE':C.white,8,'输入框 / '+label);n.strokes=solid(opts.error?C.red:C.line);n.strokeWeight=1;text(n,14,12,value,14,opts.placeholder?C.muted:C.ink,false,w-40);if(opts.select)text(n,w-27,12,'⌄',14,C.muted);return n;}
function icon(p,x,y,type,color=C.green,size=20){const n=frame(p,x,y,size,size,C.white,0,'图标 / '+type);n.fills=[];let k=size/20;
function r(a,b,c,d,col=color,rad=0){return rect(n,a*k,b*k,c*k,d*k,col,rad*k);}
if(type==='calendar'){r(2,4,16,14,color,3);r(3,7,14,10,C.white,1);r(5,1,2,6,color,1);r(13,1,2,6,color,1);r(6,10,3,3);r(11,10,3,3);}
else if(type==='ticket'){r(1,4,18,12,color,3);ellipse(n, -2*k,8*k,6*k,5*k,C.white);ellipse(n,16*k,8*k,6*k,5*k,C.white);r(12,6,1,8,C.white);}
else if(type==='search'){const e=ellipse(n,2*k,2*k,12*k,12*k,color);ellipse(n,4*k,4*k,8*k,8*k,C.white);const z=r(12,13,7,2);z.rotation=-45;}
else if(type==='grid'){[[2,2],[11,2],[2,11],[11,11]].forEach(([a,b])=>r(a,b,7,7,color,1));}
else if(type==='users'){ellipse(n,3*k,2*k,6*k,6*k,color);ellipse(n,11*k,3*k,5*k,5*k,color);r(1,10,11,8,color,5);r(12,10,7,8,color,4);}
else if(type==='check'){const v=pixso.createVector();n.appendChild(v);v.vectorPaths=[{windingRule:'NONZERO',data:'M 3 10 L 8 15 L 17 4'}];v.fills=[];v.strokes=solid(color);v.strokeWeight=2;v.x=1;v.y=2;}
else if(type==='bell'){r(5,4,10,11,color,5);r(3,13,14,2);ellipse(n,8*k,16*k,4*k,3*k,color);}
else if(type==='shield'){r(3,2,14,16,color,5);text(n,5,0,'✓',13,C.white,true);}
else if(type==='scan'){[[1,1],[12,1],[1,12],[12,12]].forEach(([a,b])=>{r(a,b,7,2);r(a,b,2,7);});}
else if(type==='file'){r(4,1,13,18,color,2);r(7,7,7,1,C.white);r(7,11,7,1,C.white);r(7,15,5,1,C.white);}
else {r(3,5,14,2);r(3,10,14,2);r(3,15,14,2);}
return n;}
function screen(name,x,y,w=1440,h=1000){if(pixso.currentPage.children.some(n=>n.name===name))throw new Error('画板已存在，请勿重复生成: '+name);const n=frame(pixso.currentPage,x,y,w,h,C.bg,0,name);created.push(n);return n;}
function logo(p,x,y,dark=false){const n=frame(p,x,y,34,34,dark?C.lime:C.green,10,'品牌标志');rect(n,8,8,7,18,dark?C.green:C.lime,3);rect(n,19,8,7,18,dark?C.green:C.lime,3);text(p,x+45,y-1,'集会',23,dark?C.white:C.ink,true);text(p,x+101,y+9,'CAMPUS',10,dark?'#AFC9BE':C.muted,true);}
function topbar(p,active='发现活动'){rect(p,0,0,1440,80,C.white);line(p,0,79,1440);logo(p,56,22);['发现活动','我的活动','消息通知'].forEach((s,i)=>{const x=350+i*128;text(p,x,28,s,15,s===active?C.green:C.muted,s===active);if(s===active)rect(p,x,76,60,3,C.green,1);});text(p,1025,29,'仙林校区',13,C.muted);icon(p,1143,29,'bell');ellipse(p,1213,21,36,36,C.soft);text(p,1224,27,'林',14,C.green,true);text(p,1262,28,'林同学',14,C.ink);text(p,1350,28,'⌄',14,C.muted);}
function side(p,role,active){rect(p,0,0,228,p.height,C.deep);logo(p,24,28,true);text(p,26,92,role+'工作台',12,'#9AB6AC',true);const nav=role==='平台管理员'?['活动审核','角色与权限','操作日志']:['工作概览','活动管理','报名与候补','名单与统计'];nav.forEach((s,i)=>{const y=142+i*56;if(s===active)rect(p,16,y-7,196,44,'#2A5B4E',8);icon(p,30,y+4,['grid','calendar','users','file'][i],s===active?C.lime:'#99B7AB');text(p,65,y,s,14,s===active?C.white:'#BED0C8',s===active);});line(p,22,p.height-150,184,'#31594B');ellipse(p,24,p.height-120,36,36,'#31594B');text(p,34,p.height-114,role==='平台管理员'?'管':'社',14,C.white,true);text(p,72,p.height-121,role==='平台管理员'?'平台管理中心':'校园文化中心',13,C.white,true);text(p,72,p.height-98,'当前身份 · '+role,10,'#99B7AB');text(p,26,p.height-42,'返回活动广场  ↗',12,'#BED0C8');rect(p,228,0,1212,72,C.white);line(p,228,71,1212);text(p,264,24,role+' / '+active,13,C.muted);icon(p,1320,25,'bell');ellipse(p,1371,18,34,34,C.soft);text(p,1381,24,role==='平台管理员'?'管':'社',13,C.green,true);}
function heading(p,x,y,kicker,title,desc){text(p,x,y,kicker,11,C.green,true);text(p,x,y+24,title,30,C.ink,true);if(desc)text(p,x,y+78,desc,13,C.muted);}
function stat(p,x,y,w,label,value,sub,color=C.green){const n=panel(p,x,y,w,116,label);text(n,20,16,label,13,C.muted);num(n,20,44,value,30,color);text(n,20,88,sub,11,C.muted);return n;}
function poster(p,x,y,w,h,kind=0){const palettes=[['#D9EDBB','#1C5143'],['#E8D9C6','#7C5539'],['#D7E6EE','#285A72']];const [bg,fg]=palettes[kind%3];const n=frame(p,x,y,w,h,bg,0,'活动视觉海报');if(kind===0){for(let i=0;i<7;i++){const a=rect(n,w*.48+i*16,h*.15,8,h*.65,fg,4);a.rotation=(i-3)*9;}ellipse(n,w*.67,h*.25,h*.36,h*.36,bg);text(n,24,h*.22,'声入\n秋夜',h*.22,fg,true);}else if(kind===1){ellipse(n,w*.61,-h*.3,h*1.5,h*1.5,fg);ellipse(n,w*.68,-h*.12,h*1.12,h*1.12,bg);text(n,24,h*.22,'思想\n正在发生',h*.17,fg,true);}else{for(let i=0;i<4;i++){const a=rect(n,w*.50+i*31,-20,17,h+80,fg,8);a.rotation=-28;}text(n,24,h*.22,'一起\n向前跑',h*.19,fg,true);}return n;}
function tabs(p,x,y,items,active=0,gap=106){items.forEach((s,i)=>{text(p,x+i*gap,y,s,14,i===active?C.green:C.muted,i===active);if(i===active)rect(p,x+i*gap,y+34,56,3,C.green,1);});}
function note(p,x,y,w,title,body,tone='green'){const bg=tone==='amber'?C.amberBg:tone==='red'?C.redBg:C.soft;const col=tone==='amber'?C.amber:tone==='red'?C.red:C.green;const n=frame(p,x,y,w,76,bg,10,'提示 / '+title);text(n,16,11,title,13,col,true);text(n,16,36,body,12,col,false,w-32);return n;}
function table(p,x,y,width,headers,rows,widths,rowH=58){const n=panel(p,x,y,width,52+rows.length*rowH,'数据表');rect(n,1,1,width-2,50,'#F8F9F6',15);let xx=20;headers.forEach((h,i)=>{text(n,xx,17,h,12,C.muted,true);xx+=widths[i];});rows.forEach((row,ri)=>{const yy=52+ri*rowH;line(n,0,yy,width);let xx=20;row.forEach((cell,ci)=>{if(typeof cell==='object'){pill(n,xx,yy+(rowH-28)/2,cell.label,cell.tone,cell.w);}else{text(n,xx,yy+(rowH-20)/2,String(cell),12,ci===0?C.ink:ci===row.length-1?C.green:C.muted,ci===0||ci===row.length-1,widths[ci]-10);}xx+=widths[ci];});});return n;}
function footer(p,label){line(p,56,p.height-53,p.width-112);text(p,56,p.height-35,label,11,C.muted);text(p,p.width-260,p.height-35,'集会 · 让校园生活发生',11,C.muted);}
function done(){return {createdNodeIds:created.map(n=>n.id),frames:created.map(n=>({id:n.id,name:n.name,width:n.width,height:n.height,children:n.children.length})),actions,verified:created.every(n=>n.width>0&&n.height>0)};}

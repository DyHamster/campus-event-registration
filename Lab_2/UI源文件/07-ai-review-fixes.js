
const changed=[];
function replace(rootId,from,to){const root=pixso.getNodeById(rootId);for(const n of root.findAll(n=>n.type==='TEXT'&&n.characters===from)){n.characters=to;changed.push(n.id);}}
const tick=pixso.getNodeById('4:169'),tickParent=tick.parent;tick.remove();const check=pixso.createVector();tickParent.appendChild(check);check.vectorPaths=[{windingRule:'NONZERO',data:'M 3 10 L 8 15 L 17 4'}];check.fills=[];check.strokes=solid(C.green);check.strokeWeight=2;check.x=1;check.y=2;changed.push(tickParent.id);
replace('4:194','请输入用于活动通知的手机号','使用账号绑定手机号（尾号 0176）');
const org=pixso.getNodeById('4:357'),tbl=org.children.find(n=>n.name==='数据表');
for(const n of tbl.children.filter(n=>n.type==='TEXT'&&n.characters==='名单管理  ·  编辑')){n.characters='名单管理 · 编辑 · 取消';changed.push(n.id);}
const musicWait=tbl.children.find(n=>n.type==='TEXT'&&n.characters==='12');musicWait.characters='0';changed.push(musicWait.id);
const edit=pixso.getNodeById('4:493'),rules=edit.children.find(n=>n.name==='报名设置');rules.resize(1140,249);changed.push(rules.id);
const roster=pixso.getNodeById('4:607'),waitStat=roster.children.find(n=>n.name==='候补人数');for(const n of waitStat.children.filter(n=>n.type==='TEXT'&&n.characters==='12')){n.characters='0';changed.push(n.id);}
replace('4:607','候补名单 12','候补名单 0');
replace('4:826','浏览与报名','浏览公开活动');
replace('4:826','检票人员仅能访问被授权的活动','检票人员仅能访问授权活动；报名操作使用参与者身份');
replace('4:1053','该名额将按候补队列顺序递补。','如存在候补，将按队列顺序自动递补。');
const camera=pixso.getNodeById('4:951').children.find(n=>n.name==='扫码取景区域');
for(const n of [...camera.children]){if(n.type==='RECTANGLE'&&((n.width===22&&n.height===3)||(n.width===3&&n.height===22)))n.remove();}
const corners=pixso.createVector();camera.appendChild(corners);corners.vectorPaths=[{windingRule:'NONZERO',data:'M 62 50 L 62 28 L 84 28 M 298 28 L 320 28 L 320 50 M 62 238 L 62 260 L 84 260 M 298 260 L 320 260 L 320 238'}];corners.fills=[];corners.strokes=solid(C.lime);corners.strokeWeight=3;corners.x=62;corners.y=28;corners.name='扫码四角';changed.push(camera.id);
const state=pixso.getNodeById('4:1053');state.resize(1440,1400);const stateFoot=state.children.find(n=>n.type==='TEXT'&&n.characters.startsWith('状态示例用于'));stateFoot.y=1344;changed.push(state.id);
const eventCancel=panel(state,48,986,1344,308,'取消活动确认');
pill(eventCancel,24,24,'影响整场活动','red',136);
text(eventCancel,24,80,'确认取消整场活动？',25,C.ink,true);
text(eventCancel,24,132,'秋日草坪音乐会 · 11月14日 晚场',15,C.ink,true);
text(eventCancel,24,182,'取消后停止接受新报名，已有电子票失效。\n保留相关业务记录，并向受影响的参与者发送状态变更通知。',13,C.muted,false,850);
text(eventCancel,24,261,'将影响 176 位已报名参与者，请与举办方确认后操作。',12,C.red,true);
button(eventCancel,974,112,342,'继续保留活动','secondary');
button(eventCancel,974,178,342,'确认取消活动','danger');
const rootNames=['03 / 确认报名','05 / 举办方活动管理','06 / 创建与编辑活动','07 / 报名名单与容量','09 / 角色权限与操作日志','10 / 现场扫码检票','12 / 状态与确认'];const roots=pixso.currentPage.children.filter(n=>rootNames.includes(n.name));
if(rules.height!==249||waitStat.findAll(n=>n.type==='TEXT'&&n.characters==='0').length!==1)throw new Error('校对结果不匹配');
return {updatedNodeIds:changed,createdNodeIds:[eventCancel.id],verified:true,frames:roots.map(n=>({id:n.id,name:n.name,height:n.height}))};


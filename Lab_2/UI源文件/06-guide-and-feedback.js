
const o=screen('00 / 设计导览',-1600,0,1440,1000);
rect(o,0,0,1440,305,C.deep);logo(o,56,40,true);text(o,56,118,'校园活动票务与报名系统',40,C.white,true);text(o,56,194,'实验二 · 软件设计与建模 / UI 设计初稿',17,'#BED5C6');
pill(o,1120,49,'2026.11 · AI 初稿','green',264);
text(o,56,344,'从一次报名，到一场顺利的相遇。',29,C.ink,true);
text(o,56,400,'以四类角色串联活动发布、报名候补和现场检票。界面采用统一色彩、状态和信息层级。',14,C.muted);
const roles=[
['01','普通参与者','发现活动 → 选择场次 → 确认报名\n我的活动 → 候补进度 → 专属电子票','01 / 发现活动'],
['02','活动举办方','创建活动 → 提交审核 → 管理活动\n名单与统计 → 容量调整 → 导出名单','05 / 举办方活动管理'],
['03','平台管理员','活动审核 → 发布 / 驳回\n角色权限 → 关键操作记录','08 / 平台活动审核'],
['04','现场检票人员','选择授权场次 → 扫码检票\n核验成功 / 重复签到 / 失效票提示','10 / 现场扫码检票']];
roles.forEach((v,i)=>{const x=56+(i%2)*676,y=461+Math.floor(i/2)*211;const card=panel(o,x,y,652,187,v[1]+' / 路径');pill(card,22,22,v[0],'green',50);text(card,90,21,v[1],21,C.ink,true);text(card,22,77,v[2],14,C.muted,false,580);actions.push({nodeId:card.id,target:v[3]});});
text(o,56,923,'另含：关键状态与确认、系统反馈与组件规范。所有页面均为可编辑图层，数据为示例。',12,C.muted);
const f=screen('13 / 组件与系统反馈',4800,2600,1440,1060);
heading(f,48,35,'DESIGN SYSTEM','统一的界面语言，清楚的系统反馈。','颜色、文字、表单与异常状态 · 为后续人工修改保留一致的基础');
const palette=panel(f,48,173,1344,132,'色彩与字体');text(palette,24,18,'视觉规范',17,C.ink,true);
[[C.green,'主色 / 深绿'],[C.lime,'强调 / 青柠'],[C.bg,'背景 / 米白'],[C.ink,'正文 / 墨绿'],[C.amber,'候补 / 琥珀'],[C.red,'异常 / 砖红']].forEach(([col,label],i)=>{rect(palette,24+i*175,59,35,35,col,8);text(palette,72+i*175,61,label,12,C.muted);});
const empty=panel(f,48,337,432,282,'空状态');
icon(empty,195,26,'calendar',C.green,42);text(empty,24,98,'还没有报名的活动',21,C.ink,true);text(empty,24,145,'去发现一场感兴趣的活动，\n让下一段校园故事开始。',13,C.muted,false,384);button(empty,24,213,384,'发现活动','primary','01 / 发现活动');
const load=panel(f,504,337,432,282,'加载状态');
text(load,24,25,'正在读取活动列表',20,C.ink,true);text(load,24,68,'请稍候，保留当前筛选条件。',13,C.muted);
rect(load,24,118,384,18,'#E6EBE4',5);rect(load,24,156,292,14,'#EEF1EB',5);rect(load,24,189,344,14,'#EEF1EB',5);rect(load,24,222,238,14,'#EEF1EB',5);
const fail=panel(f,960,337,432,282,'网络错误');
pill(fail,24,25,'连接失败','red',102);text(fail,24,83,'暂时无法读取活动',21,C.ink,true);text(fail,24,134,'网络连接中断，请检查网络后重试。\n已填写的内容将保留。',13,C.muted,false,384);button(fail,24,213,384,'重新加载','secondary');
const repeat=panel(f,48,651,432,295,'重复提交');
text(repeat,24,25,'你已报名成功',21,C.green,true);text(repeat,24,82,'无需重复提交。原有报名记录保持不变，\n可以前往“我的活动”查看电子票。',13,C.muted,false,384);button(repeat,24,218,384,'查看原报名记录','primary','04 / 我的活动');
const form=panel(f,504,651,432,295,'表单校验');text(form,24,25,'信息校验',21,C.ink,true);field(form,24,83,384,'联系方式 *','请输入手机号',{placeholder:true,error:true});text(form,24,168,'请填写有效的联系方式后再提交。',12,C.red);button(form,24,218,384,'确认提交报名','disabled');
const denied=panel(f,960,651,432,295,'资格限制');
pill(denied,24,25,'暂不符合报名条件','amber',172);text(denied,24,84,'本活动仅限在校学生',21,C.ink,true);text(denied,24,135,'当前账号未完成在校身份核验。\n核验完成后，可重新检查报名资格。',13,C.muted,false,384);button(denied,24,218,384,'查看资格说明','secondary');
text(f,48,1009,'正文：Noto Sans SC · 数字：Inter · 间距：8 / 16 / 24 / 32 · 主操作高 44 px · 不以颜色单独传达状态',12,C.muted);
return done();


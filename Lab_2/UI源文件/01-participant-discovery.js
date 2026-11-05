
pixso.currentPage.name='01 · 校园活动系统 UI';
const s=screen('01 / 发现活动',0,0);
topbar(s);
const hero=frame(s,56,112,1328,282,C.deep,22,'校园活动主视觉');
pill(hero,28,25,'CAMPUS LIFE · 2026','green',188);
text(hero,30,70,'在校园，遇见你的热爱。',34,C.white,true);
text(hero,31,130,'讲座、音乐、运动与新朋友。\n每一次参与，都让生活多一种可能。',15,'#C8DBCD',false,650);
button(hero,31,214,158,'探索本周活动  →','lime','02 / 活动详情');
for(let i=0;i<4;i++){const a=rect(hero,880+i*74,-60,42,390,i%2?C.lime:'#729B75',21);a.rotation=-24;}
ellipse(hero,1095,70,116,116,C.deep);ellipse(hero,1113,88,80,80,C.lime);
text(hero,853,208,'GO OUT.\nBE PART OF IT.',18,C.white,true);
text(s,56,425,'发现活动',25,C.ink,true);
text(s,56,468,'找到下一件值得期待的事',13,C.muted);
const search=frame(s,922,427,462,46,C.white,8,'搜索活动');search.strokes=solid(C.line);icon(search,14,13,'search');text(search,46,12,'搜索活动名称、举办方或地点',13,C.muted);
tabs(s,56,515,['全部活动','学术讲座','文艺演出','运动健康','社团活动'],0,120);
pill(s,1140,514,'本周  ⌄','gray',104);pill(s,1256,514,'可报名  ⌄','gray',128);
const events=[
['秋日草坪音乐会','校园文化中心','11月14日 周六 · 18:30','仙林校区 · 炜华体育场','剩余 24 个名额','免费',0],
['当人工智能遇见科学','计算机学院','11月16日 周一 · 19:00','仙林校区 · 计算机楼报告厅','名额已满 · 可候补','免费',1],
['校园环湖晨跑计划','跑步协会','11月15日 周日 · 07:00','仙林校区 · 羊山湖','剩余 68 个名额','免费',2]];
events.forEach((e,i)=>{const x=56+i*450;const n=panel(s,x,576,428,327,e[0]);poster(n,1,1,426,130,e[6]);pill(n,18,147,i===0?'文艺演出':i===1?'学术讲座':'运动健康','gray',86);text(n,18,186,e[0],19,C.ink,true);text(n,18,220,e[2],12,C.muted);text(n,18,245,e[3],12,C.muted);line(n,18,275,392);text(n,18,292,e[4],12,i===1?C.amber:C.green,true);text(n,356,288,e[5],18,C.green,true);actions.push({nodeId:n.id,target:'02 / 活动详情'});});
footer(s,'公开活动 12 场 · 按活动时间排序');
const d=screen('02 / 活动详情',1600,0);
topbar(d);
text(d,56,108,'发现活动  /  文艺演出  /  活动详情',12,C.muted);
poster(d,56,148,840,244,0);
pill(d,80,168,'报名进行中','green',108);
text(d,56,419,'秋日草坪音乐会',31,C.ink,true);
text(d,56,474,'把晚风、草坪与喜欢的音乐，装进同一个夜晚。',15,C.muted);
icon(d,56,523,'calendar');text(d,88,521,'2026年11月14日 18:30—21:00',14);
text(d,56,565,'地点',12,C.muted);text(d,120,561,'仙林校区 · 炜华体育场',14,C.ink,true);
text(d,56,606,'举办方',12,C.muted);text(d,120,602,'校园文化中心',14,C.ink,true);
line(d,56,649,840);tabs(d,56,671,['活动介绍','参与须知','举办方信息'],0,132);
text(d,56,736,'一场属于校园的秋日现场',21,C.ink,true);
text(d,56,781,'校园乐队、原创音乐人与热爱音乐的你，在草坪上相遇。\n现场设置自由观演区，请提前 20 分钟到场，凭专属电子票签到入场。',14,C.muted,false,812);
note(d,56,862,840,'参与须知','活动开始前可在“我的活动”中取消报名；释放的名额按候补顺序递补。');
const book=panel(d,928,148,456,764,'报名场次与名额');
text(book,24,24,'选择场次',21,C.ink,true);
text(book,24,66,'每人每场限报一次',12,C.muted);
const chosen=frame(book,24,108,408,110,C.soft,10,'已选场次');chosen.strokes=solid(C.green);
text(chosen,16,16,'11月14日 周六 · 晚场',15,C.green,true);
text(chosen,16,49,'18:30—21:00  /  炜华体育场',13,C.green);
icon(chosen,363,16,'check');
text(book,24,245,'普通入场名额',14,C.ink,true);text(book,347,242,'免费',18,C.green,true);
rect(book,24,291,408,7,'#EDF0E9',4);rect(book,24,291,359,7,C.green,4);
text(book,24,315,'176 / 200 人已报名',12,C.muted);text(book,320,315,'剩余 24',12,C.green,true);
line(book,24,359,408);
text(book,24,383,'报名截止',12,C.muted);text(book,24,413,'11月13日 18:00',16,C.ink,true);
text(book,24,465,'报名资格',12,C.muted);text(book,24,495,'南京大学在校学生',14,C.ink,true);
pill(book,24,534,'✓  你符合报名条件','green',202);
button(book,24,600,408,'填写报名信息  →','primary','03 / 确认报名');
text(book,24,661,'报名成功后，可在“我的活动”查看电子票。',12,C.muted,false,408);
text(book,24,704,'名额已满时可申请候补，按顺序自动递补。',12,C.muted,false,408);
footer(d,'活动信息由举办方发布，平台审核后展示');
return done();


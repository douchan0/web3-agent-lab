import {UNIT, units, format, quote, risk} from './math.mjs';

const $ = id => document.getElementById(id);
const labels = {trend:'趋势',event:'事件',contrarian:'逆向',background:'背景',arbitrage:'套利',
  decision:'决策',risk:'风控',news:'新闻',reference:'参考价',round_open:'开盘',round_close:'收盘',
  swap_receipt:'兑换回执',setup_receipt:'部署或准备回执',market_open:'市场准备就绪',participants:'钱包分配',
  chain_started:'启动本地链',run_complete:'实验完成'};
const riskNames = {accepted:'通过',hold:'观望',trade_limit:'超过单笔上限',balance:'钱包余额不足',
  execution_slippage:'报价恶化超过滑点上限',price_impact:'含费价格冲击超限',slippage_limit:'滑点设置超限'};
const operations = {deploy_token:'部署代币',deploy_pool:'部署池',approve_seed:'授权注资',
  approve_swap:'授权兑换',fund:'向钱包转入测试币',seed:'注资'};
const glossary = {Transfer:'代币转账',Approval:'授权额度',Swap:'池内兑换',Seed:'池初始化',Unknown:'未识别日志'};
const lessonTitles = ['账户、交易与区块链','ERC-20 和智能合约','AMM 和恒定乘积','流动性、价格冲击与套利',
  'Solidity、交易回执和事件','策略、风险与收益分析','LLM Agent 决策与公平评测','科学实验设计与综合报告'];
const map = [
  ['新闻','控制器只在发布时间和可见时间都到达后发放样例消息。','src/experiment.py','E000071',4,'lab-info'],
  ['Agent 决策','交易角色读取同一轮公开行情与自己的钱包，给出买卖或观望。','src/experiment.py','E000064',7,'lab-info'],
  ['风控','检查单笔上限、余额和报价。通过后才尝试提交。','src/experiment.py','E000065',6,'lab-risk'],
  ['链上执行','Anvil 运行合约，返回区块号、交易哈希、Gas 和合约事件。','contracts/Market.sol','E000067',5,'lab-amm'],
  ['事件记录','每条事件有顺序编号，钱包前后状态与回执可以串联。','src/events.py','E000067',1,'lab-amm'],
  ['K 线 / 资产 / 报告','只用成功兑换画 K 线。角色净值用单独的参考价计算。','src/analytics.py','E000070',8,'lab-depth'],
];
const colors = ['#00786f','#8060ae','#c45c31','#4676b2','#9b3659'];
const overviewCache = new Map();
const roundCache = new Map();
let data, run, turn = 0, shown = [], timer;
let fetchVersion = 0, runVersion = 0, compareVersion = 0;
const title = name => labels[name] ?? name;
const amount = raw => raw == null ? '—' : format(raw, 8);
const full = raw => raw == null ? '—' : format(raw);
const link = (caption, href) => Object.assign(document.createElement('a'), {textContent:caption,href});
const button = (caption, fn) => {
  const item = document.createElement('button');
  item.type = 'button';
  item.textContent = caption;
  item.addEventListener('click', fn);
  return item;
};
const node = (tag, caption) => Object.assign(document.createElement(tag), {textContent:caption});
const endpoint = (id, operation) => '/api/run/' + encodeURIComponent(id) + '/' + operation;
const chapter = i => '/project/docs/course/week-' + i + '.md';

async function json(path) {
  const response = await fetch(path);
  if (!response.ok) throw Error('找不到该档案或事件。');
  return response.json();
}
function options(element, values) {
  element.replaceChildren(...values.map(([value, label]) => new Option(label, value)));
}
async function overview(id) {
  if (overviewCache.has(id)) return overviewCache.get(id);
  const result = await json(endpoint(id, 'overview'));
  if (overviewCache.size >= 4) overviewCache.delete(overviewCache.keys().next().value);
  overviewCache.set(id, result);
  return result;
}
function fields(parent, pairs) {
  const list = document.createElement('dl');
  for (const [key, value] of pairs) list.append(node('dt', key), node('dd', value ?? '—'));
  parent.append(list);
}
function wallet(value) {
  return value ? 'RISK ' + full(value.RISK) + ' / sUSD ' + full(value.sUSD) : '—';
}
function describe(event) {
  let caption = title(event.kind);
  if (event.role) caption += ' · ' + title(event.role);
  if (event.kind === 'decision') caption += ' · ' + ({buy:'买入',sell:'卖出',hold:'观望'}[event.intent.action]);
  if (event.kind === 'risk') caption += ' · ' + (riskNames[event.result] ?? event.result);
  if (event.kind === 'news') caption += ' · ' + event.title;
  if (event.operation) caption += ' · ' + (operations[event.operation] ?? event.operation);
  if (event.receipt) caption += event.receipt.status === '0x1' ? ' · 成功' : ' · 回退';
  return event.id + ' · ' + caption;
}
function showEvidence(id) {
  const event = shown.find(row => row.id === id);
  if (!event) return;
  const body = $('event-body');
  $('event-name').textContent = describe(event);
  $('raw').textContent = JSON.stringify(event, null, 2);
  $('raw-details').open = false;
  body.replaceChildren();
  const pairs = [];
  if (event.role) pairs.push(['角色与模型', title(event.role) + ' / ' + event.model]);
  if (event.kind === 'decision') pairs.push(['公开理由',event.intent.public_rationale],
    ['拟投入代币', full(event.intent.amount_raw) + ' ' + (event.intent.token_in ?? '')],
    ['可见新闻',event.input_snapshot.visible_news_ids.join('、') || '当时没有可见新闻'],
    ['钱包余额',wallet(event.input_snapshot.wallet)]);
  if (event.kind === 'risk') pairs.push(['风险判定 Risk Gate',riskNames[event.result] ?? event.result],
    ['链上提交',event.result === 'accepted' ? '通过风控后检查回执' : '本事件没有广播交易']);
  if (event.kind === 'news') pairs.push(['发表 → 可见（UTC）',event.published_at + ' → ' + event.available_at],
    ['样例内容',event.content_excerpt],['来源',event.source_url]);
  if (event.receipt) {
    const r = event.receipt;
    pairs.push(['交易哈希 Transaction Hash',r.transactionHash],['区块 Block',String(Number(r.blockNumber))],
      ['发件人 → 收件人',r.from + ' → ' + (r.to ?? r.contractAddress)],
      ['状态 Status',r.status === '0x1' ? '成功' : '链上回退'],
      ['Gas Used × Effective Gas Price',BigInt(r.gasUsed) + ' × ' + BigInt(r.effectiveGasPrice) + ' = ' +
        (BigInt(r.gasUsed) * BigInt(r.effectiveGasPrice)) + ' wei']);
    if (event.wallet_before) pairs.push(['交易前钱包余额',wallet(event.wallet_before)],
      ['交易后钱包余额',wallet(event.wallet_after)],['交易前池储备',wallet(event.reserves_before)],
      ['交易后池储备',wallet(event.reserves_after)],
      ['池内手续费 Pool Fee',full(event.fee_in_raw) + ' ' + event.token_in]);
  }
  if (event.kind === 'market_open') {
    pairs.push(['池的初始储备',wallet(event.reserves)]);
    for (const [role,address] of Object.entries(data.participants.roles ?? {})) {
      pairs.push([title(role)+'钱包',wallet(event.balances[address])]);
    }
  }
  if (event.kind === 'round_close') {
    for (const [role, balance] of Object.entries(event.wallets)) pairs.push([title(role),wallet(balance)]);
  }
  fields(body, pairs);
  if (event.decoded_logs?.length) {
    body.append(node('h4','合约事件 Logs'));
    for (const entry of event.decoded_logs) {
      let note = entry.addresses.join(' → ');
      if (entry.token) note += ' · ' + (BigInt(entry.raw_values[0]) === 2n**256n-1n
        ? '最大授权' : full(entry.raw_values[0]) + ' ' + entry.token);
      if (entry.name === 'Swap') {
        const [direction, input, output] = entry.raw_values;
        note += ' · ' + full(input) + (direction === '1' ? ' RISK → ' : ' sUSD → ') +
          full(output) + (direction === '1' ? ' sUSD' : ' RISK');
      }
      body.append(node('p',entry.name + '（' + glossary[entry.name] + '） ' + note + ' · ' + entry.emitter));
    }
  }
  const related = new Set([event.order_id,event.risk_id]);
  for (const sibling of shown) {
    if (sibling.order_id === id && !sibling.kind.endsWith('broadcast')) related.add(sibling.id);
    if (sibling.risk_id === id && !sibling.kind.endsWith('broadcast')) related.add(sibling.id);
  }
  const buttons = [...related].filter(Boolean).map(target => button(target + ' · ' +
    title(shown.find(row => row.id === target)?.kind ?? '关联事件'), () => showEvidence(target)));
  const cites = event.intent?.cited_news_ids ?? event.news_ids ?? [];
  for (const [, , , , , , , news] of data?.rows ?? []) {
    for (const [newsId, caption, fixture] of news) {
      if (cites.includes(fixture)) buttons.push(button(caption, () => locate(newsId)));
    }
  }
  $('related').replaceChildren(...buttons);
}
function showList(preferred) {
  const kind = $('kind').value;
  const entries = shown.filter(event => !event.kind.endsWith('_broadcast') &&
    (!kind || (kind === 'receipt' ? !!event.receipt : event.kind === kind)));
  $('event-list').replaceChildren(...entries.map(event => {
    const row = document.createElement('li');
    const entry = button(describe(event), () => showEvidence(event.id));
    entry.dataset.eventId = event.id;
    row.append(entry);
    return row;
  }));
  const key = preferred ?? entries.find(e => e.kind === 'decision')?.id ?? entries[0]?.id;
  if (key) showEvidence(key);
  else {
    $('event-name').textContent = '本轮没有这类事件';
    for (const id of ['event-body','raw','related']) $(id).replaceChildren();
  }
}
async function evidence(round, preferred, automatic = false) {
  const version = ++fetchVersion;
  $('event-title').textContent = round ? '第 ' + round + ' 轮事件' : '部署、钱包与初始注资';
  const key = run + '/' + round;
  try {
    if (!roundCache.has(key)) {
      const events = await json(endpoint(run,'round?n=' + round));
      if (roundCache.size >= 32) roundCache.delete(roundCache.keys().next().value);
      roundCache.set(key, events);
    }
    if (version !== fetchVersion) return;
    shown = roundCache.get(key);
    $('lookup-status').textContent = '';
    showList(preferred);
  } catch (error) {
    if (version !== fetchVersion) return;
    shown = [];
    showList();
    if (!automatic) $('lookup-status').textContent = error.message;
  }
}
async function locate(key) {
  const id = run;
  const version = ++fetchVersion;
  try {
    const result = await json(endpoint(id, 'locate?key=' + encodeURIComponent(key)));
    if (version !== fetchVersion || run !== id) return;
    $('kind').value = '';
    stop();
    if (result.round > data.rows.length) {
      await evidence(result.round,result.id);
      return;
    }
    await setTurn(result.round, result.id);
  } catch (error) {
    if (version === fetchVersion) $('lookup-status').textContent = error.message;
  }
}
function svg(tag, attrs, target, label) {
  const item = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs)) item.setAttribute(key,value);
  if (label) {
    const tip = document.createElementNS(item.namespaceURI,'title');
    tip.textContent = label;
    item.append(tip);
  }
  target.append(item);
  return item;
}
function accessible(item, label, fn) {
  item.setAttribute('tabindex','0');
  item.setAttribute('role','button');
  item.setAttribute('aria-label',label);
  item.addEventListener('focus', () => $('hover').textContent = label);
  item.addEventListener('pointerenter', () => $('hover').textContent = label);
  item.addEventListener('click',fn);
  item.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); fn(); }
  });
}
function draw() {
  const svgChart = $('chart'), navChart = $('nav-chart');
  svgChart.replaceChildren(); navChart.replaceChildren();
  const window = Number($('window').value);
  const start = Math.max(0,turn-window);
  const rows = data.rows.slice(start,turn);
  const range = rows.flatMap(([, , h, l, , ref]) => h === null ? [Number(ref)] : [Number(l),Number(h),Number(ref)]);
  const low = Math.min(...range), high = Math.max(...range);
  const pad = Math.max(.0005,(high-low)*.08);
  const y = price => 219 - (Number(price)-low+pad)*186/(high-low+pad*2);
  const step = 908/Math.max(rows.length,1);
  const x = index => 70 + (index+.5)*step;
  const volumeMax = Math.max(1,...rows.map(row => Number(row[6])/1e18));
  for (const i of [0,1,2,3,4]) {
    if (!rows.length) break;
    const p = low-pad+i*(high-low+2*pad)/4;
    svg('line',{x1:70,x2:978,y1:y(p),y2:y(p),stroke:'#d6e3e9'},svgChart);
    svg('text',{x:64,y:y(p)+4,'text-anchor':'end','font-size':12},svgChart).textContent = p.toFixed(4);
  }
  svg('polyline',{points:rows.map((row,i) => x(i)+','+y(row[5])).join(' '),
    fill:'none',stroke:'#6d83a1','stroke-dasharray':'5 4'},svgChart);
  const role = $('role').value;
  rows.forEach(([n,o,h,l,c,ref,vol,news,fills],i) => {
    const px = x(i), width = Math.min(20,step*.65);
    const layer = svg('g',{'data-round':n},svgChart);
    const prices = o === null ? '无成交' : '开/高/低/收 ' + [o,h,l,c].map(p=>Number(p).toFixed(6)).join(' / ');
    const caption = '第 ' + n + ' 轮 · ' + prices + ' · ' + fills.length + ' 笔 · ' +
      amount(vol) + ' RISK · 参考价 ' + Number(ref).toFixed(6);
    svg('rect',{x:px-step/2,y:15,width:step,height:301,fill:'transparent'},layer,caption);
    if (o !== null) {
      const color = Number(c)>=Number(o) ? '#00786f' : '#b94e46';
      svg('line',{x1:px,x2:px,y1:y(h),y2:y(l),stroke:color},layer);
      svg('rect',{x:px-width/2,y:Math.min(y(o),y(c)),width,height:Math.max(2,Math.abs(y(o)-y(c))),fill:color},layer);
      const height = Number(vol)/1e18/volumeMax*42;
      svg('rect',{x:px-width/2,y:309-height,width,height,fill:'#7e9eb6'},layer);
    }
    accessible(layer, caption, () => { stop(); $('kind').value = ''; setTurn(n); $('evidence').scrollIntoView(); });
    if (i % Math.max(1,Math.ceil(rows.length/9)) === 0 || i === rows.length-1) {
      svg('text',{x:px,y:331,'text-anchor':'middle','font-size':11},svgChart).textContent = n;
    }
    const matches = fills.filter(fill => !role || fill[1] === role);
    matches.forEach(([key, actor, direction, price], offset) => {
      const size = Math.min(5,step*.36);
      const cx = px + (offset-(matches.length-1)/2)*Math.min(4,step/4);
      const cy = direction === 'buy' ? y(price)+8 : y(price)-8;
      const sign = direction === 'buy' ? 1 : -1;
      const note = key+' · '+title(actor)+' · '+(sign === 1?'买入':'卖出')+' · '+Number(price).toFixed(6);
      const point = svg('polygon',{points:[cx+','+(cy-size*sign),(cx-size)+','+(cy+size*sign),(cx+size)+','+(cy+size*sign)].join(' '),
        fill:sign===1?'#00786f':'#a44929','data-role':actor,'data-event':key},svgChart,note);
      accessible(point,note,() => { locate(key); $('evidence').scrollIntoView(); });
    });
    for (const [key, caption] of news) {
      const mark = svg('text',{x:px,y:242,'text-anchor':'middle',fill:'#8060ae','data-news':key},svgChart,caption);
      mark.append(document.createTextNode('◆'));
      accessible(mark,key+' · '+caption,() => { locate(key); $('evidence').scrollIntoView(); });
    }
  });
  drawNav(navChart,start,turn,step);
}
function drawNav(target,start,end,step) {
  const tracks = Object.entries(data.roles).map(([role, positions],i) =>
    ({role,values:positions.slice(start,end).map(row => Number(row[2])),color:colors[i]}));
  const all = tracks.flatMap(track => track.values);
  if (!all.length) return;
  const low = Math.min(...all)-.1, high = Math.max(...all)+.1;
  const y = v => 120-(v-low)*95/(high-low);
  for (const p of [low,(high+low)/2,high]) {
    svg('line',{x1:70,x2:978,y1:y(p),y2:y(p),stroke:'#d6e3e9'},target);
    svg('text',{x:64,y:y(p)+4,'text-anchor':'end','font-size':11},target).textContent = p.toFixed(2);
  }
  tracks.forEach(({role,values,color},i) => {
    svg('polyline',{points:values.map((value,j) => (70+(j+.5)*step)+','+y(value)).join(' '),
      fill:'none',stroke:color,'stroke-width':1.8,'data-nav-role':role},target,title(role));
    svg('text',{x:74+i*90,y:145,fill:color,'font-size':12},target).textContent = title(role);
  });
}
function drawPositions() {
  $('positions').replaceChildren(...Object.entries(data.roles).map(([role, values]) => {
    const [risk,susd,nav,drawdown] = values[turn-1] ?? [];
    const address = data.participants.roles?.[role];
    const initial = data.contracts.balances?.[address];
    const cells = [title(role),amount(risk ?? initial?.RISK),amount(susd ?? initial?.sUSD),
      nav == null ? '—' : Number(nav).toFixed(4),drawdown == null ? '—' : (100*Number(drawdown)).toFixed(2)+'%'];
    const row = document.createElement('tr');
    for (const value of cells) row.insertCell().textContent = value;
    return row;
  }));
}
async function setTurn(n, preferred) {
  if (!data) return;
  turn = Math.max(0,Math.min(n,data.rows.length));
  $('clock').value = turn;
  $('clock-label').textContent = turn + ' / ' + data.rows.length;
  $('back').disabled = turn === 0;
  $('next').disabled = turn === data.rows.length;
  draw();
  drawPositions();
  await evidence(turn,preferred,true);
}
function stop() {
  clearInterval(timer);
  timer = undefined;
  $('play').textContent = '播放';
}
function play() {
  if (!data?.rows.length) return;
  if (turn >= data.rows.length) setTurn(0);
  $('play').textContent = '暂停';
  timer = setInterval(() => {
    setTurn(turn+1);
    if (turn >= data.rows.length) stop();
  },Number($('speed').value));
}
async function switchRun(id, event) {
  const version = ++runVersion;
  ++fetchVersion;
  stop();
  $('market-status').textContent = '正在读取紧凑市场索引…';
  try {
    const result = await overview(id);
    if (version !== runVersion) return;
    run = id;
    data = result;
    $('run').value = run;
    options($('role'),[['','全部角色'],...Object.keys(data.roles).map(role => [role,title(role)])]);
    $('clock').max = data.rows.length;
    const states = {archived:'已归档',complete:'已完成',running:'运行中',exporting:'导出中',stopped:'已停止',failed:'异常终止'};
    $('market-status').textContent = run + ' · 本地 Anvil · ' + data.rows.length + ' 轮已收盘 · ' + states[data.status];
    if (data.incomplete_round) {
      $('market-status').append(document.createTextNode(' · '),button('查看未收盘轮证据', () => {
        stop(); evidence(data.incomplete_round); $('evidence').scrollIntoView();
      }));
    }
    const addresses = $('addresses');
    addresses.replaceChildren();
    fields(addresses,[['交易池 Pool',data.contracts.pool],...Object.entries(data.contracts.tokens ?? {}),
      ...Object.entries(data.participants.roles ?? {}).map(([role,address]) =>
        [title(role)+'钱包（'+data.participants.models[role]+'）',address+' · '+wallet(data.contracts.balances?.[address])])]);
    const files = $('run-files');
    files.replaceChildren(link('配置快照','/artifact/'+run+'/config.json'),document.createTextNode(' · '),
      link('原始事件 JSONL','/artifact/'+run+'/events.jsonl'),document.createTextNode(' · '),
      link('新手故事','/artifact/'+run+'/story.md'),document.createTextNode(' · '),
      link('研究报告','/artifact/'+run+'/research.md'));
    await setTurn(data.rows.length);
    if (event) await locate(event);
    if ($('compare').value) await compare();
  } catch (error) {
    if (version === runVersion) $('market-status').textContent = error.message;
  }
}
async function compare() {
  const version = ++compareVersion;
  const target = $('compare').value;
  $('comparison').replaceChildren();
  if (!target || !data) return;
  try {
    const other = await overview(target);
    if (version !== compareVersion) return;
    for (const [id, item] of [[run,data],[target,other]]) {
      const panel = node('div','');
      panel.className = 'inset';
      panel.append(node('h3',id),node('p',item.rows.length+' 轮，'+item.rows.reduce((sum,row)=>sum+row[8].length,0)+' 笔成交'));
      for (const [role, values] of Object.entries(item.roles)) {
        const last = values.at(-1);
        if (last) panel.append(node('p',title(role)+' · 期末净值 '+Number(last[2]).toFixed(4)+' · 最大回撤 '+(100*Number(last[3])).toFixed(2)+'%'));
      }
      $('comparison').append(panel);
    }
  } catch (error) {
    if (version === compareVersion) $('comparison').textContent = error.message;
  }
}
function setupMap() {
  lessonTitles.forEach((name,i) => {
    const item = document.createElement('li');
    item.append(link(name,chapter(i+1)));
    $('lessons').append(item);
  });
  const controls = map.map(([caption],i) => button(caption,()=>render(i)));
  function render(i) {
    const [caption, explanation, code, event, lesson, experiment] = map[i];
    controls.forEach((control,j) => control.setAttribute('aria-pressed',String(i===j)));
    $('map-detail').replaceChildren(node('h3',caption),node('p',explanation),
      link('查看真实事件 '+event,'/?run=first-100&event='+event+'#evidence'),document.createTextNode(' · '),
      link('代码位置','/project/'+code),document.createTextNode(' · '),
      link('第 '+lesson+' 周课程',chapter(lesson)),document.createTextNode(' · '),link('做个实验','#'+experiment));
  }
  $('map').append(...controls);
  render(0);
}
function setupLabs() {
  const x=10000n*UNIT, shallow=3000n*UNIT;
  const labs = {
    'lab-amm': fields => {
      const a=units(fields.get('amount'));
      const input=units(fields.get('reserve-in')), output=units(fields.get('reserve-out'));
      const result=quote(input,output,a);
      if (result.out===0n) {
        return ['less','报价向下取整为零，链上调用会回退。两项储备与 k 保持原值 '+result.before+'。'];
      }
      const actual=result.out*input, ideal=a*output;
      const observed=actual<ideal?'less':actual===ideal?'equal':'more';
      return [observed,'到账 '+full(result.out)+'。交易后输入储备 '+full(input+a)+'，输出储备 '+full(output-result.out)+'。k 原始单位平方从 '+result.before+' 增至 '+result.after+
        '。计算按 18 位整数向下取整。费率 30 bps，全部输入进池。'];
    },
    'lab-depth': fields => {
      const a=units(fields.get('amount')), deep=quote(x,x,a), short=quote(shallow,shallow,a);
      const observed=deep.out>short.out?'deep':deep.out===short.out?'equal':'shallow';
      return [observed,'深池 '+full(deep.out)+'，含费冲击 '+deep.impact+' bps。浅池 '+full(short.out)+
        '，冲击 '+short.impact+' bps。两池的名义输入留费相同，约 '+full(deep.fee)+'。输入量占浅池储备比例更高。'];
    },
    'lab-info': fields => {
      const visible=Number(fields.get('turn'))>=2;
      return [visible?'buy':'hold',visible
        ? 'N01 可见，样例参考价 1 × 1.016 = 1.016。固定池价 1 下偏差 160 bps，超过套利角色的 70 bps 阈值，产生买入意图。'
        : 'N01 尚未释放，参考价仍为 1，偏差 0 bps，角色观望。'];
    },
    'lab-risk': fields => {
      const decision=risk(units(fields.get('amount')),x,x,250n*UNIT);
      return [decision==='accepted'?'accepted':'rejected','风控结果为 '+riskNames[decision]+'。交易上限是 10,000 × 60 ÷ 10,000 = 60 RISK；通过还需满足余额、冲击和报价限制。'];
    },
  };
  for (const [id, evaluate] of Object.entries(labs)) {
    const form=$(id);
    form.addEventListener('submit',event=>{
      event.preventDefault();
      const input=new FormData(form);
      const out=form.querySelector('output');
      try {
        const [prediction, explanation]=evaluate(input);
        out.textContent=(prediction===input.get('prediction')?'预测吻合。':'预测和计算不同。')+' '+explanation;
      } catch(error) {out.textContent=error.message;}
    });
  }
}
$('run').addEventListener('change', e => switchRun(e.target.value));
$('compare').addEventListener('change', compare);
$('role').addEventListener('change', () => { if (data) draw(); });
$('window').addEventListener('change', () => { if (data) draw(); });
$('clock').addEventListener('input', e => { stop(); setTurn(Number(e.target.value)); });
$('back').addEventListener('click', () => { stop(); setTurn(turn-1); });
$('next').addEventListener('click', () => { stop(); setTurn(turn+1); });
$('play').addEventListener('click', () => timer ? stop() : play());
$('speed').addEventListener('change', () => { if (timer) { stop(); play(); } });
$('kind').addEventListener('change', () => showList());
$('setup').addEventListener('click', () => { stop(); setTurn(0); });
$('find').addEventListener('submit', e => { e.preventDefault(); locate($('key').value); });
$('revert-example').addEventListener('click', async () => {
  if (!data) return;
  stop();
  const version = ++fetchVersion;
  try {
    const events = await json('/api/revert-example');
    if (version !== fetchVersion) return;
    shown = events;
    $('event-title').textContent = '独立链集成测试 · Revert';
    $('kind').value = 'receipt';
    showList(events.find(row => row.success === false).id);
  } catch (error) {
    if (version === fetchVersion) $('lookup-status').textContent = error.message;
  }
});
setupMap();
setupLabs();
const params = new URLSearchParams(location.search);
json('/api/runs').then(runs => {
  options($('run'),runs.map(id=>[id,id]));
  options($('compare'),[['','选择对照档案'],...runs.map(id=>[id,id])]);
  if (!runs.length) throw Error('档案目录还没有实验。');
  const fallback = runs.includes('first-100') ? 'first-100' : runs[0];
  const requested = params.get('run');
  if (requested && !runs.includes(requested)) throw Error('当前目录找不到请求的档案 '+requested+'，请选择可用档案。');
  return switchRun(requested ?? fallback,params.get('event'));
}).catch(error => $('market-status').textContent = error.message);

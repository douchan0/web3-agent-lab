import {format} from './math.mjs';

const $ = id => document.getElementById(id);
const count = new Intl.NumberFormat('zh-CN');
const displayAmount = new Intl.NumberFormat('zh-CN',{maximumFractionDigits:6});
const runUrl = (run, hash = 'market') => '/lab?run=' + encodeURIComponent(run) + '#' + hash;

function render({featured, sample, runs}) {
  $('dashboard-status').textContent = featured ? '' : '当前目录暂无已完成的实验归档。';
  if (!featured) return;
  $('results-title').textContent = featured.label;
  $('results-link').href = runUrl(featured.id);
  $('metric-rounds').textContent = count.format(featured.rounds);
  $('metric-fills').textContent = count.format(featured.fills);
  $('metric-rejects').textContent = count.format(featured.rejected);
  $('metric-cost').textContent = '$' + featured.cost_usd;
  const mode = {mock:'规则模拟角色（mock）',fixture:'离线模型替身',live:'模型中继'}[featured.mode] ?? featured.mode;
  $('results-context').textContent = 'Anvil 本地执行 · ' + mode + ' · 样例新闻';
  $('results').hidden = false;

  for (const run of runs) {
    const item = document.createElement('li');
    const anchor = document.createElement('a');
    const numbers = document.createElement('span');
    anchor.href = runUrl(run.id);
    anchor.textContent = run.label;
    numbers.textContent = count.format(run.fills) + ' 笔成交';
    anchor.append(numbers);
    item.append(anchor);
    $('runs-list').append(item);
  }
  $('runs-card').hidden = !runs.length;
  if (!sample) return;
  $('receipt-amount').textContent = format(sample.amount_in_raw) + ' ' + sample.token_in + ' → 约 ' +
    displayAmount.format(Number(format(sample.amount_out_raw))) + ' ' + (sample.token_in === 'RISK' ? 'sUSD' : 'RISK');
  $('receipt-context').textContent = sample.label + ' · 第 ' + sample.round + ' 轮 · 区块 ' +
    Number(sample.block) + ' · ' + sample.event;
  $('receipt-link').href = '/lab?run=' + encodeURIComponent(sample.run) + '&event=' +
    encodeURIComponent(sample.event) + '#evidence';
  $('receipt-card').hidden = false;
}

if (/^#(?:welcome|market|evidence|labs|lab-(?:amm|depth|info|risk)|course)$/.test(location.hash)) {
  location.replace('/lab' + location.search + location.hash);
} else {
  fetch('/api/dashboard').then(response => {
    if (!response.ok) throw Error();
    return response.json();
  }).then(render).catch(() => {
    $('dashboard-status').textContent = '实验归档读取失败，刷新页面可重试。';
  });
}

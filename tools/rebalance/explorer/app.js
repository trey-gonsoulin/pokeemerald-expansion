// The explorer page (#151): knob controls, the level chart and the tables.
// The model runs in worker.js; each change posts the knobs and redraws.

const pct = v => `${Math.round(v * 100)}%`;
const UNITS = of => [['levels', 'levels'], ['percent', `% of ${of}`]];
const REFS = {
    bench: 'bench (lowest off the KO rotation, or lowest)',
    ko_mean: 'KO-takers\' mean',
    party_mean: 'party mean',
    ace: 'highest member',
};

// key -> control. type: range, optional (a range with an on/off box; off
// sends null), select, check. help is the line under the control. A knob
// with a unit (the key of a levels/percent select) takes its range from pct
// in percent, and fmt gets the unit's suffix.
const KNOBS = [
    { group: 'Play style' },
    { key: 'ko_takers', label: 'KO rotation', type: 'range', min: 1, max: 6, step: 1,
      fmt: v => (v === 1 ? '1 lead, 5 benched' : v === 6 ? 'all six take KOs' : `${v} take KOs, ${6 - v} benched`),
      help: 'How many members take turns landing the KOs; the rest get only the Exp. Share.' },
    { key: 'clear', label: 'Route trainers fought', type: 'range', min: 0.1, max: 1, step: 0.05, fmt: pct,
      help: 'Share of each stage\'s ordinary trainers beaten, evenly spread.' },
    { key: 'catches', label: 'Catches per stage', type: 'range', min: 0, max: 10, step: 1,
      help: 'Each catch gives a KO\'s exp (B_EXP_CATCH), at the stage\'s land average.' },
    { key: 'wild_battles', label: 'Wild KOs per stage', type: 'range', min: 0, max: 40, step: 1,
      help: 'Wild battles fought to the end, at the stage\'s land average.' },
    { key: 'walk_steps', label: 'Steps walked per stage', type: 'range', min: 0, max: 16384, step: 512,
      fmt: v => v.toLocaleString(), help: 'Only feeds friendship (the affection 1.2x).' },
    { key: 'affection', label: 'Affection 1.2x', type: 'select',
      options: [['none', 'never'], ['friendship', 'once friendship reaches 220'], ['always', 'from the start']] },
    { group: 'Exp formula' },
    { key: 'trainer_exp', label: 'Trainer battle exp', type: 'select',
      options: [['1.5x off', 'no bonus (Gen 7+, the fork)'], ['1.5x on', '1.5x (Gen 6 and earlier)']] },
    { key: 'scaled_exp', label: 'Level-scaled exp', type: 'check',
      help: 'B_SCALED_EXP: exp weighted by the getter\'s level against the foe\'s. Off is Gen 6\'s flat exp.' },
    { key: 'scaling_power', label: 'Scaling exponent', type: 'range', min: 1.5, max: 4, step: 0.1,
      fmt: v => v.toFixed(1),
      help: 'The game\'s table is level^2.5. Higher punishes an over-levelled getter harder. Not a game option yet.' },
    { key: 'overlevel_unit', label: 'Over-level cutoff in', type: 'select', options: UNITS('the foe\'s level') },
    { key: 'overlevel_cutoff', label: 'Over-level cutoff', type: 'optional', min: 0, max: 20, step: 1,
      unit: 'overlevel_unit', pct: [0, 60, 1], fmt: (v, u) => `past +${v}${u}`,
      help: 'Past this far above the foe, the getter gets 1 exp, or less and less with the falloff. Not a game option yet.' },
    { key: 'overlevel_halflife', label: 'Over-level falloff', type: 'optional', min: 1, max: 20, step: 1,
      unit: 'overlevel_unit', pct: [1, 50, 1], fmt: (v, u) => `halves every ${v}${u}`,
      help: 'Past the cutoff, the exp halves every this far further above the foe (at least 1). Off: straight to 1.' },
    { key: 'share_fraction', label: 'Exp. Share bench share', type: 'range', min: 0, max: 1, step: 0.05, fmt: pct,
      help: 'What a member that didn\'t take the KO gets. The Gen 6+ share gives 50%. Not a game option yet.' },
    { group: 'Targets' },
    { key: 'boss_ref', label: 'Measure against', type: 'select', options: Object.entries(REFS),
      help: 'The party level the boss margin and the trainer and wild gaps use.' },
    { key: 'gap_unit', label: 'Margin and gaps in', type: 'select', options: UNITS('the reference level') },
    { key: 'margin', label: 'Boss margin', type: 'optional', min: -3, max: 8, step: 1,
      unit: 'gap_unit', pct: [-5, 20, 1], fmt: (v, u) => `ace ${v >= 0 ? '+' : ''}${v}${u}`,
      help: 'Raise each boss (never lower) so its ace sits this far above the reference. Off: today\'s levels.' },
    { key: 'league_steps', label: 'Elite Four spacing', type: 'check',
      help: 'With the margin: each Elite Four member at least 1 above the last, Wallace 3 above Drake.' },
    { key: 'trainer_gap', label: 'Route trainer gap', type: 'optional', min: 0, max: 15, step: 1,
      unit: 'gap_unit', pct: [0, 40, 1], fmt: (v, u) => `${v}${u} below`,
      help: 'Raise each stage\'s ordinary trainers until their aces average this far below the reference when fought.' },
    { key: 'wild_gap', label: 'Wild gap', type: 'optional', min: 0, max: 25, step: 1,
      unit: 'gap_unit', pct: [0, 50, 1], fmt: (v, u) => `${v}${u} below`,
      help: 'Raise each stage\'s wild levels until the land average sits this far below the reference at its start.' },
    { key: 'rematch_step', label: 'Rematch step', type: 'optional', min: 1, max: 10, step: 1,
      unit: 'gap_unit', pct: [1, 20, 1], fmt: (v, u) => `+${v}${u} a rematch`,
      help: 'Raise each ordinary trainer\'s rematches this far per rematch over a base: the route trainer gap at the earliest stage they can be fought, or the first fight. The gym leaders\' and Wally\'s rematch rounds and Steven follow the boss margin.' },
    { key: 'evolve', label: 'Evolve raised Pokémon', type: 'check',
      help: 'A raised trainer or wild Pokémon evolves 3 levels past a level evolution.' },
];

const $ = sel => document.querySelector(sel);
const worker = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });
let defaults = null;
let today = null;  // the defaults' result, for the dashed lines
let busy = false;
let pending = false;
let timer = 0;
let chart = null;
let bossStages = [];  // the drawn bosses' stages, for the tooltip titles

function buildControls() {
    const panel = $('#knobs');
    for (const k of KNOBS) {
        if (k.group) {
            panel.insertAdjacentHTML('beforeend', `<h2>${k.group}</h2>`);
            continue;
        }
        const row = document.createElement('div');
        row.className = 'knob';
        row.dataset.key = k.key;
        let control = '';
        // An optional knob starts its slider at the middle (the margin at +1), where it stays while off.
        if (k.type === 'range' || k.type === 'optional')
            control = `<input type="range" min="${k.min}" max="${k.max}" step="${k.step}"
                value="${k.key === 'margin' ? 1 : Math.round((k.min + k.max) / 2)}">`;
        if (k.type === 'optional')
            control = `<input type="checkbox" class="on">` + control;
        if (k.type === 'check')
            control = `<input type="checkbox">`;
        if (k.type === 'select')
            control = `<select>${k.options.map(([v, t]) => `<option value="${v}">${t}</option>`).join('')}</select>`;
        row.innerHTML = `<label>${k.label} <output></output></label><div class="control">${control}</div>`
            + (k.help ? `<p class="help">${k.help}</p>` : '');
        row.addEventListener('input', () => {
            showValue(k, row);
            for (const d of KNOBS.filter(d => d.unit === k.key))
                applyUnit(d);
            changed();
        });
        panel.append(row);
    }
}

const inPercent = k => k.unit && $(`.knob[data-key="${k.unit}"] select`).value === 'percent';

// Puts the knob's range in its unit's bounds (the value clamps to them).
function applyUnit(k) {
    const row = $(`.knob[data-key="${k.key}"]`);
    const range = row.querySelector('input[type=range]');
    const [min, max, step] = inPercent(k) ? k.pct : [k.min, k.max, k.step];
    Object.assign(range, { min, max, step });
    showValue(k, row);
}

function readKnobs() {
    const out = {};
    for (const k of KNOBS.filter(k => k.key)) {
        const row = $(`.knob[data-key="${k.key}"]`);
        if (k.type === 'check')
            out[k.key] = row.querySelector('input').checked;
        else if (k.type === 'select')
            out[k.key] = row.querySelector('select').value;
        else if (k.type === 'optional' && !row.querySelector('.on').checked)
            out[k.key] = null;
        else
            out[k.key] = Number(row.querySelector('input[type=range]').value);
    }
    return out;
}

function setKnobs(knobs) {
    // The selects first, so the ranges get their unit's bounds before their values.
    const keyed = KNOBS.filter(k => k.key);
    for (const k of keyed.filter(k => k.type === 'select'))
        $(`.knob[data-key="${k.key}"] select`).value = knobs[k.key];
    for (const k of keyed.filter(k => k.unit))
        applyUnit(k);
    for (const k of keyed) {
        const row = $(`.knob[data-key="${k.key}"]`);
        const v = knobs[k.key];
        if (k.type === 'check')
            row.querySelector('input').checked = v;
        else if (k.type === 'select')
            row.querySelector('select').value = v;
        else {
            if (k.type === 'optional')
                row.querySelector('.on').checked = v !== null;
            if (v !== null)
                row.querySelector('input[type=range]').value = v;
        }
        showValue(k, row);
    }
}

function showValue(k, row) {
    const out = row.querySelector('output');
    if (k.type === 'select' || k.type === 'check') {
        out.textContent = '';
        return;
    }
    const range = row.querySelector('input[type=range]');
    const off = k.type === 'optional' && !row.querySelector('.on').checked;
    range.disabled = off;
    const v = Number(range.value);
    out.textContent = off ? 'off' : (k.fmt ? k.fmt(v, inPercent(k) ? '%' : '') : String(v));
}

// The knobs that differ from the defaults: the settings box and the URL hash.
function changedKnobs(knobs) {
    return Object.fromEntries(Object.entries(knobs).filter(([key, v]) => v !== defaults[key]));
}

function changed() {
    const diff = changedKnobs(readKnobs());
    const json = JSON.stringify(diff);
    history.replaceState(null, '', Object.keys(diff).length ? '#' + encodeURIComponent(json) : location.pathname);
    $('#settings').value = JSON.stringify(diff, null, 1);
    $('#cli').textContent = `python3 tools/rebalance/rebalance.py curve '${json}'`;
    clearTimeout(timer);
    timer = setTimeout(request, 120);
}

function request() {
    if (busy) {
        pending = true;
        return;
    }
    busy = true;
    pending = false;
    $('#status').textContent = 'running…';
    worker.postMessage({ id: 'run', knobs: readKnobs() });
}

worker.onmessage = ({ data }) => {
    if (data.type === 'ready') {
        defaults = data.defaults;
        let start = defaults;
        try {
            if (location.hash.length > 1)
                start = { ...defaults, ...JSON.parse(decodeURIComponent(location.hash.slice(1))) };
        } catch (err) {
            console.warn('ignoring the URL hash:', err);
        }
        setKnobs(start);
        $('#knobs').classList.remove('loading');
        document.querySelectorAll('button').forEach(b => { b.disabled = false; });
        busy = true;
        worker.postMessage({ id: 'today', knobs: {} });
        return;
    }
    if (data.type === 'error') {
        busy = false;
        $('#status').textContent = 'error: ' + data.message;
        if (data.id === 'today')
            changed();  // the dashed lines need today's run; draw without them
        else if (pending)
            request();
        return;
    }
    if (data.id === 'today') {
        today = data.result;
        busy = false;
        changed();
        return;
    }
    busy = false;
    $('#status').textContent = `${data.ms.toFixed(0)} ms`;
    draw(data.result);
    if (pending)
        request();
};

function stageValue(res, key) {
    const byStage = Object.fromEntries(res.stages.map(s => [s.stage, s[key]]));
    return res.bosses.map(b => byStage[b.stage]);
}

function draw(res) {
    const labels = res.bosses.map(b => b.name);
    const refName = REFS[res.knobs.boss_ref];
    const sets = [
        { label: 'Boss ace', data: res.bosses.map(b => b.boss_ace), borderColor: '#c0392b', borderWidth: 3 },
        { label: 'Boss ace today', data: res.bosses.map(b => b.base_ace), borderColor: '#c0392b', borderDash: [6, 4],
          borderWidth: 1.5 },
        { label: `Party: ${refName}`, data: res.bosses.map(b => b.ref), borderColor: '#2471a3', borderWidth: 2.5 },
        { label: `Party: ${refName}, default knobs`, data: today ? today.bosses.map(b => b.refs[res.knobs.boss_ref]) : [],
          borderColor: '#2471a3', borderDash: [6, 4], borderWidth: 1.5 },
        { label: 'Party: highest', data: res.bosses.map(b => Math.max(...b.levels)), borderColor: '#85c1e9',
          borderWidth: 1, pointRadius: 0 },
        { label: 'Party: lowest', data: res.bosses.map(b => Math.min(...b.levels)), borderColor: '#85c1e9',
          borderWidth: 1, pointRadius: 0, fill: '-1', backgroundColor: 'rgba(133, 193, 233, 0.25)' },
        { label: 'Route trainers: mean ace', data: stageValue(res, 'trainer_ace_mean'), borderColor: '#e67e22',
          stepped: 'middle', borderWidth: 2 },
        { label: 'Wild: land mean', data: stageValue(res, 'wild_land_mean'), borderColor: '#27ae60',
          stepped: 'middle', borderWidth: 2 },
    ];
    bossStages = res.bosses.map(b => b.stage);
    for (const s of sets) {
        s.pointRadius ??= 2;
        s.fill ??= false;
        s.tension = 0;
    }
    if (!chart) {
        chart = new Chart($('#chart'), {
            type: 'line',
            data: { labels, datasets: sets },
            options: {
                animation: false,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: { y: { suggestedMin: 0, suggestedMax: 100, title: { display: true, text: 'level' } },
                          x: { ticks: { autoSkip: false, maxRotation: 70, minRotation: 50 } } },
                plugins: {
                    tooltip: { callbacks: { title: items => `${items[0].label} (${bossStages[items[0].dataIndex]})` } },
                    legend: { position: 'bottom' },
                },
            },
        });
    } else {
        chart.data.labels = labels;
        sets.forEach((s, i) => Object.assign(chart.data.datasets[i], s));
        chart.update();
    }
    drawTables(res);
}

function drawTables(res) {
    const last = res.bosses[res.bosses.length - 1];
    const peak = Math.max(...res.bosses.map(b => Math.max(...b.levels)));
    $('#headline').innerHTML = `<b>${last.name}</b> ace ${last.boss_ace} (today ${last.base_ace}) · party at the
        last boss ${Math.min(...last.levels)}–${Math.max(...last.levels)} · highest member's peak ${peak}`
        + (res.lv100 ? ` · <b class="warn">Lv 100 by ${res.lv100}</b>` : '');
    $('#bosses tbody').innerHTML = res.bosses.map(b => `<tr><td>${b.name}</td><td>${b.stage}</td><td>${b.base_ace}</td>
        <td>${b.raise ? '+' + b.raise : ''}</td><td><b>${b.boss_ace}</b></td>
        <td>${Math.min(...b.levels)}–${Math.max(...b.levels)}</td><td>${b.ref}</td></tr>`).join('');
    $('#stages tbody').innerHTML = res.stages.map(s => `<tr><td>${s.stage}</td><td>${+s.start_ref.toFixed(1)}</td>
        <td>${s.trainers}</td><td>${s.raise ? '+' + s.raise : ''}</td><td>${s.trainer_ace_mean ?? ''}</td>
        <td>${s.gap ?? ''}${s.gap !== null && res.knobs.gap_unit === 'percent' ? '%' : ''}</td><td>${s.wild_offset ? '+' + s.wild_offset : ''}</td>
        <td>${s.wild_land_mean ?? ''}</td></tr>`).join('');
    const ladders = new Map();
    for (const r of res.rematches) {
        if (!ladders.has(r.ladder))
            ladders.set(r.ladder, []);
        ladders.get(r.ladder).push(r);
    }
    $('#rematches tbody').innerHTML = [...ladders.values()].map(rs => `<tr><td>${rs[0].name}</td>
        <td>${rs[0].stage}</td><td>${rs[0].base}</td><td>${rs.map(r => r.ace).join(' ')}</td></tr>`).join('');
}

buildControls();
$('#reset').addEventListener('click', () => { setKnobs(defaults); changed(); });
$('#load').addEventListener('click', () => {
    try {
        setKnobs({ ...defaults, ...JSON.parse($('#settings').value || '{}') });
        changed();
    } catch (err) {
        $('#status').textContent = 'settings: ' + err.message;
    }
});
$('#copy').addEventListener('click', () => navigator.clipboard.writeText($('#settings').value));

const $ = (id) => document.getElementById(id);
const COLORS = { SOFT: "#ff4d4d", MEDIUM: "#ffd23f", HARD: "#e8ecf1" };

let reqId = 0;
let chartState = null;

async function getJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error("Request failed: " + res.status);
  return res.json();
}

function fill(select, items) {
  select.innerHTML = "";
  for (const it of items) {
    const o = document.createElement("option");
    o.value = it.value;
    o.textContent = it.label;
    select.appendChild(o);
  }
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

/* ---------- stint explorer ---------- */

async function onRace() {
  const drivers = await getJSON(`/api/races/${encodeURIComponent($("race").value)}/drivers`);
  fill($("driver"), drivers.map((d) => ({ value: d.code, label: d.team ? `${d.code} | ${d.team}` : d.code })));
  await onDriver();
}

async function onDriver() {
  const url = `/api/races/${encodeURIComponent($("race").value)}/drivers/${encodeURIComponent($("driver").value)}/stints`;
  const stints = await getJSON(url);
  fill($("stint"), stints.map((s) => ({ value: s.stint, label: `Stint ${s.stint} | ${s.compound} | ${s.laps} laps` })));
  await refresh();
}

async function refresh() {
  const id = ++reqId;
  try {
    const q = new URLSearchParams({
      race: $("race").value, driver: $("driver").value,
      stint: $("stint").value, threshold: $("threshold").value,
    });
    const d = await getJSON("/api/predict?" + q);
    if (id !== reqId) return;
    render(d);
  } catch (err) {
    $("verdict").className = "verdict warn";
    $("verdict").textContent = "Could not load this stint. " + err.message;
  }
}

function render(d) {
  $("cCompound").textContent = d.compound;
  $("cCompound").style.color = COLORS[d.compound] || "inherit";
  $("cLaps").textContent = d.laps.length;
  $("cAlert").textContent = d.alert_age != null ? d.alert_age : "none";
  $("cCliff").textContent = d.cliff_age != null ? d.cliff_age : "not reached";
  $("cLead").textContent = d.lead_laps != null ? d.lead_laps + " laps" : "n/a";

  let msg, cls = "verdict";
  if (d.alert_age != null && d.cliff_age != null) {
    msg = `First alert at tyre age ${d.alert_age}, ${d.lead_laps} laps before the cliff at age ${d.cliff_age}.`;
    cls += " good";
  } else if (d.alert_age != null) {
    msg = "The model raised an alert, but this stint never reached a cliff by our definition.";
    cls += " warn";
  } else if (d.cliff_age != null) {
    msg = "The cliff arrived but the model never crossed the threshold. Try a lower one.";
    cls += " warn";
  } else {
    msg = "No alert and no cliff in this stint.";
  }
  $("verdict").className = cls;
  $("verdict").textContent = msg;

  $("chartTitle").textContent =
    `${$("race").selectedOptions[0].textContent} | ${d.driver} | stint ${d.stint}`;
  drawChart(d);
  drawTable(d);
}

function drawChart(d) {
  const W = 920, H = 380, m = { l: 50, r: 18, t: 16, b: 42 };
  const ages = d.laps.map((l) => l.age);
  const xMin = Math.min(...ages) - 1;
  const xMax = Math.max(Math.max(...ages), d.cliff_age != null ? d.cliff_age : 0) + 2;
  const x = (v) => m.l + ((v - xMin) / (xMax - xMin)) * (W - m.l - m.r);
  const y = (v) => H - m.b - v * (H - m.t - m.b);

  let s = "";
  for (const t of [0, 0.25, 0.5, 0.75, 1]) {
    s += `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}"/>`;
    s += `<text class="tick" x="${m.l - 8}" y="${y(t) + 4}" text-anchor="end">${Math.round(t * 100)}%</text>`;
  }
  const step = xMax - xMin > 40 ? 10 : 5;
  for (let t = Math.ceil(xMin / step) * step; t <= xMax; t += step) {
    s += `<text class="tick" x="${x(t)}" y="${H - m.b + 18}" text-anchor="middle">${t}</text>`;
  }
  s += `<text class="axis" x="${(m.l + W - m.r) / 2}" y="${H - 6}" text-anchor="middle">Tyre age (laps)</text>`;

  if (d.alert_age != null && d.cliff_age != null) {
    s += `<rect class="window" x="${x(d.alert_age)}" y="${m.t}" width="${x(d.cliff_age) - x(d.alert_age)}" height="${H - m.t - m.b}"/>`;
    s += `<text class="tag" x="${x(d.alert_age) + 6}" y="${m.t + 14}">pit window</text>`;
  }

  const line = d.laps.map((l, i) => `${i ? "L" : "M"}${x(l.age)},${y(l.risk)}`).join(" ");
  const first = d.laps[0], last = d.laps[d.laps.length - 1];
  s += `<path class="area" d="${line} L${x(last.age)},${y(0)} L${x(first.age)},${y(0)} Z"/>`;
  s += `<line class="th" x1="${m.l}" x2="${W - m.r}" y1="${y(d.threshold)}" y2="${y(d.threshold)}"/>`;
  if (d.alert_age != null) {
    s += `<line class="alert" x1="${x(d.alert_age)}" x2="${x(d.alert_age)}" y1="${m.t}" y2="${H - m.b}"/>`;
  }
  if (d.cliff_age != null) {
    s += `<line class="cliff" x1="${x(d.cliff_age)}" x2="${x(d.cliff_age)}" y1="${m.t}" y2="${H - m.b}"/>`;
  }
  s += `<path class="risk" d="${line}"/>`;
  s += `<circle id="dot" class="dot" r="5" cx="-20" cy="-20"/>`;

  $("chart").setAttribute("viewBox", `0 0 ${W} ${H}`);
  $("chart").innerHTML = s;
  chartState = { d, x, y, W, H };
}

function drawTable(d) {
  const th = Number($("threshold").value);
  $("rows").innerHTML = d.laps.map((l) => {
    const pct = (l.risk * 100).toFixed(0);
    return `<tr><td>${l.lap}</td><td>${l.age}</td><td>${l.delta == null ? "-" : l.delta}</td>` +
      `<td>${l.delta3 == null ? "-" : l.delta3}</td>` +
      `<td><div class="bar"><i class="${l.risk >= th ? "hot" : ""}" style="width:${pct}%"></i></div></td>` +
      `<td>${pct}%</td></tr>`;
  }).join("");
}

function setupHover() {
  const svg = $("chart");
  svg.addEventListener("mousemove", (ev) => {
    if (!chartState) return;
    const { d, x, y, W, H } = chartState;
    const box = svg.getBoundingClientRect();
    const px = ((ev.clientX - box.left) / box.width) * W;
    let best = d.laps[0];
    for (const l of d.laps) {
      if (Math.abs(x(l.age) - px) < Math.abs(x(best.age) - px)) best = l;
    }
    const dot = $("dot");
    if (dot) { dot.setAttribute("cx", x(best.age)); dot.setAttribute("cy", y(best.risk)); }
    const tip = $("tip");
    tip.style.display = "block";
    tip.style.left = (x(best.age) / W) * box.width + "px";
    tip.style.top = (y(best.risk) / H) * box.height + "px";
    tip.innerHTML = `Lap ${best.lap}, tyre age ${best.age}<br>Risk ${(best.risk * 100).toFixed(0)}%` +
      `<br>Pace loss ${best.delta == null ? "n/a" : best.delta} s`;
  });
  svg.addEventListener("mouseleave", () => { $("tip").style.display = "none"; });
}

/* ---------- what-if ---------- */

const WHATIF = [
  ["wAge", "oAge", "TyreLife", 0],
  ["wDelta", "oDelta", "DeltaSoFar", 2],
  ["wDelta3", "oDelta3", "Delta3", 2],
  ["wSlope", "oSlope", "Slope3", 2],
  ["wProg", "oProg", "RaceProgress", 2],
];

function setupWhatIf() {
  const run = debounce(async () => {
    const body = { Compound: $("wComp").value };
    for (const [inp, , key] of WHATIF) body[key] = Number($(inp).value);
    try {
      const r = await getJSON("/api/whatif", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const pct = r.risk * 100;
      $("gNum").textContent = pct.toFixed(0) + "%";
      $("gFill").style.width = pct + "%";
      $("gFill").style.background = r.risk < 0.3 ? "#3ddc84" : r.risk < 0.6 ? "#f5a524" : "#e10600";
    } catch (err) {
      $("gNum").textContent = "error";
    }
  }, 120);

  for (const [inp, out, , nd] of WHATIF) {
    $(inp).addEventListener("input", () => {
      $(out).textContent = Number($(inp).value).toFixed(nd);
      run();
    });
  }
  $("wComp").addEventListener("change", run);
  run();
}

/* ---------- model card ---------- */

async function loadModelCard() {
  const c = await getJSON("/api/model-card");
  $("mcMeta").textContent =
    `${c.rows.toLocaleString()} laps from ${c.races} dry races. ` +
    `${(c.positive_rate * 100).toFixed(1)}% of laps have a cliff within ${c.horizon_laps} laps.`;
  $("mcBars").innerHTML = c.scores.map((s) =>
    `<div class="mrow"><span>${s.name}</span>` +
    `<div class="mbar"><i style="width:${((s.pr_auc / 0.5) * 100).toFixed(0)}%"></i></div>` +
    `<b>${s.pr_auc.toFixed(3)}</b></div>`).join("");
}

/* ---------- start ---------- */

async function init() {
  const races = await getJSON("/api/races");
  fill($("race"), races.map((r) => ({ value: r.id, label: `${r.year} ${r.name}` })));
  $("race").addEventListener("change", onRace);
  $("driver").addEventListener("change", onDriver);
  $("stint").addEventListener("change", refresh);
  $("threshold").addEventListener("input", () => {
    $("thVal").textContent = Number($("threshold").value).toFixed(2);
    refresh();
  });
  setupHover();
  setupWhatIf();
  loadModelCard();
  await onRace();
}

init().catch((err) => {
  $("verdict").className = "verdict warn";
  $("verdict").textContent = "Could not start. " + err.message;
});

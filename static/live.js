(function () {
  const $ = (id) => document.getElementById(id);
  const get = async (u) => { const r = await fetch(u); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.status); return r.json(); };
  const fill = (el, items, label, value) => { el.innerHTML = items.map((x) => `<option value="${value(x)}">${label(x)}</option>`).join(""); };
  const msg = (t, bad) => { $("lv-msg").textContent = t || ""; $("lv-msg").style.color = bad ? "#ff6b6b" : "#9aa4b2"; };

  async function loadSessions() {
    try {
      msg("Loading races from OpenF1...");
      const s = await get(`/api/v1/live/sessions?year=${$("lv-year").value}`);
      fill($("lv-session"), s, (x) => `${x.country} (${x.date})`, (x) => x.session_key);
      msg(s.length ? "" : "No races found for that year.");
      if (s.length) await loadDrivers();
    } catch (e) { msg("Could not load races: " + e.message, true); }
  }
  async function loadDrivers() {
    try {
      const d = await get(`/api/v1/live/sessions/${$("lv-session").value}/drivers`);
      fill($("lv-driver"), d, (x) => `${x.code || x.number} ${x.name || ""}`, (x) => x.number);
      await loadStints();
    } catch (e) { msg("Could not load drivers: " + e.message, true); }
  }
  async function loadStints() {
    try {
      const s = await get(`/api/v1/live/sessions/${$("lv-session").value}/drivers/${$("lv-driver").value}/stints`);
      fill($("lv-stint"), s, (x) => `Stint ${x.stint}: ${x.compound} (laps ${x.lap_start}-${x.lap_end})`, (x) => x.stint);
    } catch (e) { msg("Could not load stints: " + e.message, true); }
  }
  async function score() {
    try {
      msg("Fetching laps and scoring...");
      const q = `session_key=${$("lv-session").value}&driver_number=${$("lv-driver").value}&stint=${$("lv-stint").value}&threshold=${$("lv-th").value}`;
      const r = await get(`/api/v1/live/score?${q}`);
      const warn = (r.warnings || []).join(" ");
      msg(`${r.compound}, ${r.scored_laps} laps scored, ${r.dropped.length} dropped. ` +
          (r.alert_lap ? `First alert on lap ${r.alert_lap}. ` : "No alert at this threshold. ") + warn, !!warn);
      $("lv-rows").innerHTML = r.laps.map((l) =>
        `<tr><td>${l.lap}</td><td>${l.tyre_life}</td><td>${l.lap_time.toFixed(3)}</td><td>+${l.delta.toFixed(2)}</td>` +
        `<td><div class="lv-bar"><span style="width:${Math.round(l.risk * 100)}%"></span></div> ${(l.risk * 100).toFixed(0)}%</td></tr>`).join("");
      $("lv-drop").textContent = r.dropped.map((d) => `L${d.lap} ${d.reason}`).join(", ") || "none";
    } catch (e) { msg("Scoring failed: " + e.message, true); }
  }
  $("lv-year").addEventListener("change", loadSessions);
  $("lv-session").addEventListener("change", loadDrivers);
  $("lv-driver").addEventListener("change", loadStints);
  $("lv-go").addEventListener("click", score);
  $("lv-th").addEventListener("input", () => { $("lv-thv").textContent = $("lv-th").value; });
  loadSessions();
})();

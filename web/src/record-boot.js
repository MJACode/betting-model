async function fetchRows(path, select) {
  const endpoint = new URL(path, CONFIG.supabaseUrl);
  endpoint.searchParams.set("select", select);
  const response = await fetch(endpoint, {
    headers: {
      apikey: CONFIG.supabaseAnonKey,
      Authorization: "Bearer " + CONFIG.supabaseAnonKey,
      Accept: "application/json",
    },
    credentials: "omit",
    cache: "no-store",
  });
  if (response.status === 404) return null;
  if (!response.ok) return false;
  const rows = await response.json();
  if (!Array.isArray(rows)) return false;
  return rows;
}

async function loadRecord() {
  const section = document.getElementById("record");
  if (!section) return;
  try {
    // site_public_record is applied before the website deploy when the
    // runbook is followed. A merge can still ship this file first. A 404
    // falls back to the view the site reads today, with the same retired
    // filter. Any other failure leaves the row hidden.
    let rows = await fetchRows(
      "/rest/v1/site_public_record",
      "sport,picks,wins,losses,pushes,units,risked",
    );
    let retired = [];
    if (rows == null) {
      rows = await fetchRows(
        "/rest/v1/v_public_track_record",
        "sport,model_id,picks,wins,losses,pushes,units,risked",
      );
      retired = CONFIG.retired || [];
    }
    if (!rows || rows.length === 0) return;
    const summary = summarizeRecord(rows, retired);
    if (!summary) return;
    const picks = document.getElementById("record-picks");
    const units = document.getElementById("record-units");
    const sports = document.getElementById("record-sports");
    const sportsWord = document.getElementById("record-sports-word");
    if (!picks || !units || !sports || !sportsWord) return;
    picks.textContent = summary.picks.toLocaleString("en-US");
    units.textContent = summary.unitsText;
    sports.textContent = String(summary.sports);
    sportsWord.textContent = summary.sports === 1 ? "sport" : "sports";
    section.hidden = false;
  } catch (_err) {
    // Fetch failed or the payload was unusable. The row stays hidden.
  }
}

loadRecord();

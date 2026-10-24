async function loadRecord() {
  const section = document.getElementById("record");
  if (!section) return;
  try {
    const endpoint = new URL("/rest/v1/v_public_track_record", CONFIG.supabaseUrl);
    endpoint.searchParams.set(
      "select",
      "sport,model_id,picks,wins,losses,pushes,units,risked",
    );
    const response = await fetch(endpoint, {
      headers: {
        apikey: CONFIG.supabaseAnonKey,
        Authorization: "Bearer " + CONFIG.supabaseAnonKey,
        Accept: "application/json",
      },
      credentials: "omit",
      cache: "no-store",
    });
    if (!response.ok) return;
    const rows = await response.json();
    if (!Array.isArray(rows) || rows.length === 0) return;
    const summary = summarizeRecord(rows, CONFIG.retired);
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

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function get(path) {
  const r = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export const getFlood = (mode = "cached") => get(`/api/results/flood?mode=${mode}`);
export const getFire = (mode = "cached") => get(`/api/results/fire?mode=${mode}`);
export const getDemoNepal = (mode = "cached") => get(`/api/demo/nepal-cascade?mode=${mode}`);
export const getDemoNepalGeo = () => get(`/api/demo/nepal-cascade/geo`);
export const getFloodAssets = () => get(`/api/results/flood/assets`);
export const getFloodNames = () => get(`/api/results/flood/names`);
export const getDemoFire = (mode = "cached") => get(`/api/demo/fire-study?mode=${mode}`);
export const getDemoFireGeo = () => get(`/api/demo/fire-study/geo`);
export const getDemo2Fire = () => get(`/api/demo2/fire-study`);
export const getDemo2Nepal = () => get(`/api/demo2/nepal-cascade`);
export const getDemo2Chain = () => get(`/api/demo2/nepal-chain`);
export const getDemo2CrossRegion = () => get(`/api/demo2/cross-region`);
export const runMorning = (source = "fixture") =>
  fetch(`${API}/api/demo2/morning-run?source=${source}`, { method: "POST" }).then(async (r) => {
    if (!r.ok) throw new Error(`run failed: ${r.status}`);
    return r.json();
  });

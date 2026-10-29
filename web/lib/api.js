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

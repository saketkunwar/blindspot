"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";

const STYLES = [
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  "https://demotiles.maplibre.org/style.json",
];

// Satellite context: Esri World Imagery raster (no key) with the reference
// boundaries-and-places overlay for labels. Imagery is one current vintage —
// context for the eye, never evidence for the ledger.
const SAT_STYLE = {
  version: 8,
  sources: {
    esri: {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics",
    },
    ref: {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      maxzoom: 19,
    },
  },
  layers: [
    { id: "esri", type: "raster", source: "esri" },
    { id: "ref", type: "raster", source: "ref" },
  ],
};

const BASEMAPS = {
  dark: () => STYLES[0],
  light: () => STYLES[1],
  satellite: () => SAT_STYLE,
};

// Flat palette per feature kind, lifted for dark basemaps.
const KIND_COLORS = {
  "target reach": "#d65445",
  "observed flood outline": "#2f6fb2",
  "pre-cutoff damage": "#3f8fd1",
  may_be: "#9cc6e8",
  must_be: "#1f6f9f",
  "fire cell": "#e05a1a",
  selected: "#d65445",
  "flood-extent": "#999999",
  "ground truth (after)": "#ff3b5c",
};
const FALLBACK_COLOR = "#888888";

const colorFor = (f) =>
  KIND_COLORS[f?.properties?.kind ?? f?.properties?.name] ?? FALLBACK_COLOR;

export function featureBounds(features) {
  return boundsOf(features);
}

function boundsOf(features) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  const walk = (c) => {
    if (typeof c[0] === "number") {
      x0 = Math.min(x0, c[0]); y0 = Math.min(y0, c[1]);
      x1 = Math.max(x1, c[0]); y1 = Math.max(y1, c[1]);
    } else c.forEach(walk);
  };
  features.forEach((f) => { try { walk(f.geometry.coordinates); } catch { /* skip */ } });
  return x0 === Infinity ? null : [[x0, y0], [x1, y1]];
}

export function legendOf(layers) {
  const seen = new Map();
  layers.forEach((f) => {
    const kind = f?.properties?.kind ?? f?.properties?.name ?? "feature";
    if (!seen.has(kind)) seen.set(kind, colorFor(f));
  });
  return [...seen.entries()];
}

export default function MapPane({ layers, onStatus, focusId, maxZoom, basemap, lockView, flyTo }) {
  // flyTo: {bounds: [[x0,y0],[x1,y1]], nonce: n} — eased guided flight;
  // the viewport stays where the flight leaves it (no refit while flying).
  const ref = useRef(null);
  const mapRef = useRef(null);
  const drawRef = useRef(() => {});
  const layersRef = useRef(layers);
  layersRef.current = layers;
  const lockRef = useRef(lockView);
  lockRef.current = lockView;
  const flyingRef = useRef(false);
  const lastFly = useRef(flyTo?.nonce);
  // Guided flight: ease to the requested bounds, honoring reduced-motion
  // by jumping instead. draw() holds its refit while flying.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !flyTo?.bounds || flyTo.nonce === lastFly.current) return;
    lastFly.current = flyTo.nonce;
    try {
      const calm = typeof window !== "undefined" && window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      flyingRef.current = true;
      map.fitBounds(flyTo.bounds, { padding: 60, maxZoom: 13,
        duration: calm ? 0 : 8000 });
      map.once("moveend", () => { flyingRef.current = false; });
      setStatus("flying to target");
    } catch { flyingRef.current = false; }
  }, [flyTo]);
  const focusRef = useRef(focusId);
  focusRef.current = focusId;
  const lastFocus = useRef(undefined);
  const [failed, setFailed] = useState(false);
  const [ctxLost, setCtxLost] = useState(false);
  const [epoch, setEpoch] = useState(0); // bump to remount the map (retry)
  const [status, setStatus] = useState("starting");
  const [base, setBase] = useState(BASEMAPS[basemap] ? basemap : "dark");
  const baseRef = useRef(base);
  const fallbackCount = useRef(0);
  const switchedOnce = useRef(false);
  useEffect(() => { if (onStatus) onStatus(status); }, [status, onStatus]);
  // Basemap switch: restyle, then redraw data layers once idle. Baseline
  // fallback counting restarts so a choice is honored, not overridden.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !switchedOnce.current) return;
    baseRef.current = base;
    try {
      fallbackCount.current = 0;
      map.setStyle(BASEMAPS[base]());
      map.once("idle", () => { try { drawRef.current(); } catch { /* redraw later */ } });
      setStatus("basemap: " + base);
    } catch { /* keep current style */ }
  }, [base]);

  useEffect(() => {
    setCtxLost(false);
    const startBase = BASEMAPS[basemap] ? basemap : "dark";
    baseRef.current = startBase;
    const map = new maplibregl.Map({
      container: ref.current,
      style: BASEMAPS[startBase](),
      center: [85.3, 27.9],
      zoom: 7,
      failIfMajorPerformanceCaveat: false,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    map.addControl(new maplibregl.FullscreenControl(), "top-right");
    mapRef.current = map;
    switchedOnce.current = true;
    const canvas = map.getCanvas();
    const onLost = (e) => {
      // Let the browser restore the context; show retry meanwhile.
      e.preventDefault();
      setCtxLost(true);
    };
    const onRestored = () => {
      setCtxLost(false);
      try { map.resize(); drawRef.current(); } catch { /* redraw on next change */ }
    };
    canvas.addEventListener("webglcontextlost", onLost, false);
    canvas.addEventListener("webglcontextrestored", onRestored, false);

    const draw = () => {
      const feats = layersRef.current;
      try {
      ["bs-fill", "bs-casing", "bs-line", "bs-point", "bs-heat", "bs-label"].forEach((id) => {
        if (map.getLayer(id)) map.removeLayer(id);
      });
      if (map.getSource("bs")) map.removeSource("bs");
      if (!feats.length) return;
      map.addSource("bs", {
        type: "geojson",
        data: { type: "FeatureCollection", features: feats },
      });
      map.addLayer({
        id: "bs-fill", type: "fill", source: "bs",
        filter: ["in", ["geometry-type"], ["literal", ["Polygon", "MultiPolygon"]]],
        paint: {
          "fill-color": ["match", ["coalesce", ["get", "kind"], ["get", "name"], ["literal", "?"]],
            "target reach", KIND_COLORS["target reach"],
            "observed flood outline", KIND_COLORS["observed flood outline"],
            "may_be", KIND_COLORS.may_be, "must_be", KIND_COLORS.must_be,
            "fire cell", KIND_COLORS["fire cell"],
            "flood-extent", KIND_COLORS["flood-extent"],
            "ground truth (after)", KIND_COLORS["ground truth (after)"],
            FALLBACK_COLOR],
          "fill-opacity": 0.14,
        },
      });
      // White casing under the selected line so it reads on any base map.
      map.addLayer({
        id: "bs-casing", type: "line", source: "bs",
        filter: ["all",
          ["in", ["geometry-type"], ["literal", ["LineString", "MultiLineString"]]],
          ["==", ["coalesce", ["get", "kind"], ["get", "name"]], "selected"]],
        paint: { "line-color": "#ffffff", "line-width": 7, "line-opacity": 0.9 },
      });
      map.addLayer({
        id: "bs-line", type: "line", source: "bs",
        filter: ["in", ["geometry-type"], ["literal", ["LineString", "MultiLineString"]]],
        paint: {
          "line-color": ["match", ["coalesce", ["get", "kind"], ["get", "name"], ["literal", "?"]],
            "target reach", KIND_COLORS["target reach"],
            "observed flood outline", KIND_COLORS["observed flood outline"],
            "selected", KIND_COLORS.selected,
            "ground truth (after)", KIND_COLORS["ground truth (after)"],
            FALLBACK_COLOR],
          "line-width": ["match", ["coalesce", ["get", "kind"], ["get", "name"], ["literal", "?"]],
            "selected", 4, 2],
        },
      });
      // Density glow under the points (fire detections, damage clusters):
      // reads as heat on dark basemaps, idle elsewhere. Added before the
      // circles so points stay crisp on top of it.
      map.addLayer({
        id: "bs-heat", type: "heatmap", source: "bs",
        filter: ["in", ["geometry-type"], ["literal", ["Point", "MultiPoint"]]],
        paint: {
          "heatmap-weight": ["match", ["coalesce", ["get", "kind"], ["get", "name"], ["literal", "?"]],
            "fire cell", 1.2, "pre-cutoff damage", 0.8, 0.5],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 5, 0.6, 12, 1.4],
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 5, 28, 12, 12],
          "heatmap-opacity": 0.5,
          "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"],
            0, "rgba(0,0,0,0)",
            0.3, "rgba(200,110,20,0.5)",
            0.6, "rgba(224,90,26,0.8)",
            0.85, "rgba(200,40,20,0.9)",
            1, "rgba(255,120,40,0.95)"],
        },
      });
      map.addLayer({
        id: "bs-point", type: "circle", source: "bs",
        filter: ["in", ["geometry-type"], ["literal", ["Point", "MultiPoint"]]],
        paint: {
          "circle-color": ["match", ["coalesce", ["get", "kind"], ["get", "name"], ["literal", "?"]],
            "must_be", KIND_COLORS.must_be, "may_be", KIND_COLORS.may_be,
            "selected", KIND_COLORS.selected,
            "fire cell", KIND_COLORS["fire cell"],
            "ground truth (after)", KIND_COLORS["ground truth (after)"],
            KIND_COLORS["pre-cutoff damage"]],
          "circle-radius": ["match", ["coalesce", ["get", "kind"], ["get", "name"], ["literal", "?"]],
            "selected", 7, 3.5],
          "circle-opacity": 0.85,
          "circle-stroke-width": ["match", ["coalesce", ["get", "kind"], ["get", "name"], ["literal", "?"]],
            "selected", 2, 0],
          "circle-stroke-color": "#ffffff",
        },
      });
      // Names where the data carries them: selected assets and named reaches.
      map.addLayer({
        id: "bs-label", type: "symbol", source: "bs",
        filter: ["all", ["has", "name"],
          ["any", ["==", ["coalesce", ["get", "kind"], ["literal", "?"]], "selected"],
            ["==", ["coalesce", ["get", "kind"], ["literal", "?"]], "target reach"]]],
        layout: {
          "text-field": ["coalesce", ["get", "label"], ["get", "name"]],
          "text-size": 12,
          "text-offset": [0, 1.2],
          "symbol-placement": ["match", ["geometry-type"], ["LineString", "MultiLineString"], "line", "point"],
        },
        paint: {
          "text-color": "#f2ede4",
          "text-halo-color": "rgba(10,12,16,0.9)",
          "text-halo-width": 1.5,
        },
      });
      // Fit the focused feature (e.g. the selected asset); the rest
      // stays as context. Without a focus, fit everything — unless the
      // view is locked (scenario switch flips layers in place, no refit).
      if (lockRef.current || flyingRef.current) {
        setStatus(feats.length + " drawn");
        return;
      }
      const fid = focusRef.current;
      const focus = fid == null ? feats
        : feats.filter((f) => f?.properties?.id === fid);
      const b = boundsOf(focus.length ? focus : feats);
      if (b) {
        try {
          const changed = fid !== lastFocus.current;
          lastFocus.current = fid;
          const calm = typeof window !== "undefined" && window.matchMedia &&
            window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          map.fitBounds(b, { padding: 48, maxZoom: maxZoom ?? 10,
            duration: changed && !calm ? 900 : 0 });
          const c = map.getCenter();
          setStatus(feats.length + " drawn · z" + map.getZoom().toFixed(1)
            + " (" + c.lng.toFixed(2) + "," + c.lat.toFixed(2) + ")");
          return;
        } catch { /* keep view */ }
      }
        setStatus(feats.length + " drawn");
      } catch (err) {
        setStatus("draw failed: " + String((err && err.message) || err));
      }
    };

    let styleLoaded = false;
    map.on("load", () => { styleLoaded = true; setStatus("style loaded"); draw(); });
    drawRef.current = draw;
    // Clickable features: popup in human fields only — present properties
    // become rows, absent ones are skipped, never faked.
    const popup = new maplibregl.Popup({ closeButton: true, maxWidth: "260px" });
    const humanRows = (p) => [
      ["Name", p.label],
      ["ID", p.id],
      ["Kind", p.kind ?? p.name],
      ["Day", p.day],
      ["Detections", p.total],
      ["Band", p.band],
      ["Status", p.status],
      ["Place", p.place],
    ].filter(([, v]) => v !== undefined && v !== null && v !== "");
    const onClick = (e) => {
      const f = e?.features?.[0];
      if (!f) return;
      const rows = humanRows(f.properties || {});
      if (!rows.length) return;
      const html = "<div class='bs-pop'>" + rows.map(([k, v]) =>
        "<p><span>" + k + "</span> " + String(v).replace(/</g, "&lt;") + "</p>").join("") + "</div>";
      popup.setLngLat(e.lngLat).setHTML(html).addTo(map);
    };
    const onEnter = () => { try { map.getCanvas().style.cursor = "pointer"; } catch { /* noop */ } };
    const onLeave = () => { try { map.getCanvas().style.cursor = ""; } catch { /* noop */ } };
    ["bs-point", "bs-line", "bs-fill"].forEach((id) => {
      map.on("click", id, onClick);
      map.on("mouseenter", id, onEnter);
      map.on("mouseleave", id, onLeave);
    });
    fallbackCount.current = 0;
    map.on("error", (e) => {
      // Style-load failure only: tile errors (e.tile) must not switch styles.
      if (e?.tile || styleLoaded) return;
      fallbackCount.current += 1;
      if (fallbackCount.current < STYLES.length) {
        setStatus("style failed, trying fallback");
        map.setStyle(STYLES[fallbackCount.current]);
      } else {
        setFailed(true);
        setStatus("all base styles failed");
      }
    });
    return () => {
      canvas.removeEventListener("webglcontextlost", onLost, false);
      canvas.removeEventListener("webglcontextrestored", onRestored, false);
      try { map.remove(); } catch { /* already gone */ }
      mapRef.current = null;
    };
  }, [epoch]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    try { map.resize(); } catch { /* not ready */ }
    try {
      if (map.isStyleLoaded()) drawRef.current();
      else map.once("load", () => drawRef.current());
    } catch { /* load handler draws */ }
  }, [layers]);

  const BASE_LABEL = { satellite: "Sat", dark: "Dark", light: "Light" };
  return (
    <div ref={ref} className="mapbox">
      <div className="maplibregl-ctrl maplibregl-ctrl-group bs-base">
        {Object.keys(BASE_LABEL).map((k) => (
          <button key={k} type="button" title={k + " basemap"}
            data-base={k} className={base === k ? "active" : ""}
            onClick={() => setBase(k)}>{BASE_LABEL[k]}</button>
        ))}
      </div>
      <p className="meta map-status">{status}</p>
      {failed && <p className="meta map-error">Base map unreachable — check network. Data layers listed below.</p>}
      {ctxLost && (
        <div className="meta map-error">
          <p>Map paused: the browser lost its GPU (WebGL) context.</p>
          <button className="item" onClick={() => setEpoch((n) => n + 1)}>Retry map</button>
        </div>
      )}
    </div>
  );
}

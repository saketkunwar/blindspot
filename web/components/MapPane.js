"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";

const STYLES = [
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  "https://demotiles.maplibre.org/style.json",
];

// Flat palette per feature kind (kinds come from the API payloads).
const KIND_COLORS = {
  "target reach": "#a33327",
  "observed flood outline": "#0b5cad",
  "pre-cutoff damage": "#b26a00",
  may_be: "#0b5cad",
  must_be: "#5c5c5c",
  "fire cell": "#c2410c",
  selected: "#a33327",
};
const FALLBACK_COLOR = "#666666";

const colorFor = (f) =>
  KIND_COLORS[f?.properties?.kind ?? f?.properties?.name] ?? FALLBACK_COLOR;

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

export default function MapPane({ layers, onStatus }) {
  const ref = useRef(null);
  const mapRef = useRef(null);
  const drawRef = useRef(() => {});
  const layersRef = useRef(layers);
  layersRef.current = layers;
  const [failed, setFailed] = useState(false);
  const [ctxLost, setCtxLost] = useState(false);
  const [epoch, setEpoch] = useState(0); // bump to remount the map (retry)
  const [status, setStatus] = useState("starting");
  useEffect(() => { if (onStatus) onStatus(status); }, [status, onStatus]);

  useEffect(() => {
    setCtxLost(false);
    const map = new maplibregl.Map({
      container: ref.current,
      style: STYLES[0],
      center: [85.3, 27.9],
      zoom: 7,
      failIfMajorPerformanceCaveat: false,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;
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
      ["bs-fill", "bs-line", "bs-point"].forEach((id) => {
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
            FALLBACK_COLOR],
          "fill-opacity": 0.25,
        },
      });
      map.addLayer({
        id: "bs-line", type: "line", source: "bs",
        filter: ["in", ["geometry-type"], ["literal", ["LineString", "MultiLineString"]]],
        paint: {
          "line-color": ["match", ["coalesce", ["get", "kind"], ["get", "name"], ["literal", "?"]],
            "target reach", KIND_COLORS["target reach"],
            "observed flood outline", KIND_COLORS["observed flood outline"],
            "selected", KIND_COLORS.selected,
            FALLBACK_COLOR],
          "line-width": ["match", ["coalesce", ["get", "kind"], ["get", "name"], ["literal", "?"]],
            "selected", 4, 2],
        },
      });
      map.addLayer({
        id: "bs-point", type: "circle", source: "bs",
        filter: ["in", ["geometry-type"], ["literal", ["Point", "MultiPoint"]]],
        paint: {
          "circle-color": ["match", ["coalesce", ["get", "kind"], ["get", "name"], ["literal", "?"]],
            "must_be", KIND_COLORS.must_be, "may_be", KIND_COLORS.may_be,
            "selected", KIND_COLORS.selected,
            KIND_COLORS["pre-cutoff damage"]],
          "circle-radius": ["match", ["coalesce", ["get", "kind"], ["get", "name"], ["literal", "?"]],
            "selected", 6, 3],
          "circle-opacity": 0.8,
        },
      });
      const b = boundsOf(feats);
        if (b) { try { map.fitBounds(b, { padding: 40 }); } catch { /* keep view */ } }
        setStatus(feats.length + " drawn");
      } catch (err) {
        setStatus("draw failed: " + String((err && err.message) || err));
      }
    };

    let styleLoaded = false;
    map.on("load", () => { styleLoaded = true; setStatus("style loaded"); draw(); });
    drawRef.current = draw;
    let fallback = 0;
    map.on("error", (e) => {
      // Style-load failure only: tile errors (e.tile) must not switch styles.
      if (e?.tile || styleLoaded) return;
      fallback += 1;
      if (fallback < STYLES.length) {
        setStatus("style failed, trying fallback");
        map.setStyle(STYLES[fallback]);
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

  return (
    <div ref={ref} className="mapbox">
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

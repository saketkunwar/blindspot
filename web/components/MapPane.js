"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";

function bboxOf(fc) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  const walk = (c) => {
    if (typeof c[0] === "number") {
      x0 = Math.min(x0, c[0]); y0 = Math.min(y0, c[1]);
      x1 = Math.max(x1, c[0]); y1 = Math.max(y1, c[1]);
    } else c.forEach(walk);
  };
  walk(fc.geometry.coordinates);
  return [[x0, y0], [x1, y1]];
}

export default function MapPane({ layers }) {
  const ref = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    mapRef.current = new maplibregl.Map({
      container: ref.current,
      style: "https://demotiles.maplibre.org/style.json",
      center: [0, 0],
      zoom: 1,
    });
    return () => mapRef.current.remove();
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const draw = () => {
      ["bs-fill", "bs-line"].forEach((id) => {
        if (map.getLayer(id)) map.removeLayer(id);
      });
      if (map.getSource("bs")) map.removeSource("bs");
      if (!layers.length) return;
      map.addSource("bs", { type: "geojson", data: { type: "FeatureCollection", features: layers } });
      map.addLayer({ id: "bs-fill", type: "fill", source: "bs",
        paint: { "fill-color": "#0b5cad", "fill-opacity": 0.15 } });
      map.addLayer({ id: "bs-line", type: "line", source: "bs",
        paint: { "line-color": "#0b5cad", "line-width": 1.5 } });
      try {
        const b = bboxOf({ type: "Feature", geometry: layers[0].geometry });
        map.fitBounds(b, { padding: 40 });
      } catch { /* keep current view */ }
    };
    if (map.loaded()) draw();
    else map.once("load", draw);
  }, [layers]);

  return <div ref={ref} className="mapbox" />;
}

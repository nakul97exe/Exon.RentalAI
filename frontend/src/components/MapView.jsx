import { useEffect, useRef } from "react";
import Map from "@arcgis/core/Map.js";
import EsriMapView from "@arcgis/core/views/MapView.js";
import Home from "@arcgis/core/widgets/Home.js";
import ScaleBar from "@arcgis/core/widgets/ScaleBar.js";

import { detectIdField } from "../lib/shapefile.js";

export default function MapView({ onViewReady, onParcelSelect }) {
  const containerRef = useRef(null);

  // Kept in refs so a changing callback identity doesn't tear down the map.
  const onViewReadyRef = useRef(onViewReady);
  onViewReadyRef.current = onViewReady;
  const onParcelSelectRef = useRef(onParcelSelect);
  onParcelSelectRef.current = onParcelSelect;

  useEffect(() => {
    const map = new Map({
      basemap: "dark-gray-vector",
    });

    const view = new EsriMapView({
      container: containerRef.current,
      map,
      center: [-119.4179, 36.7783], // California
      zoom: 6,
    });

    // Map corners hold spatial controls only — everything else lives in the app shell.
    view.ui.add(new Home({ view }), "top-left");

    view.ui.add(new ScaleBar({ view, unit: "dual" }), "bottom-right");

    // Clicking a feature selects it as the chat's context. Esri's own popup shows
    // the attributes; we only need to capture them for /query.
    view.on("click", async (event) => {
      const { results } = await view.hitTest(event);
      const hit = results.find((result) => result.type === "graphic");

      // Clicking empty space clears the selection.
      if (!hit) {
        onParcelSelectRef.current?.(null);
        return;
      }

      const attributes = { ...hit.graphic.attributes };
      const idField = detectIdField(attributes);

      // Fall back to the object id so the backend always has a key, even for a
      // shapefile with no recognizable identifier column.
      const apn = idField
        ? String(attributes[idField])
        : String(attributes.OBJECTID ?? attributes.FID ?? "unknown");

      onParcelSelectRef.current?.({ apn, attributes });
    });

    onViewReadyRef.current?.(view);

    // StrictMode mounts effects twice in dev — without destroy() you leak a second view.
    return () => {
      onViewReadyRef.current?.(null);
      view.destroy();
    };
  }, []);

  return <div ref={containerRef} className="map-container" />;
}

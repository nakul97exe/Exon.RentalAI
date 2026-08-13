import { useState } from "react";
import { layersFromShapefileZip } from "../../lib/shapefile.js";

export default function AddDataPanel({ view, onParcelCount }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleFile(event) {
    const file = event.target.files?.[0];
    event.target.value = ""; // lets you re-pick the same file
    if (!file || !view) return;

    setBusy(true);
    setStatus(`Reading ${file.name}…`);

    try {
      const { layer, featureCount } = await layersFromShapefileZip(file);

      view.map.add(layer);
      await layer.when();

      if (layer.fullExtent) {
        await view.goTo(layer.fullExtent.clone().expand(1.1));
      }

      onParcelCount?.(featureCount);
      setStatus(`Added ${featureCount.toLocaleString()} features.`);
    } catch (err) {
      setStatus(`Failed: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  if (!view) {
    return <p className="drawer-pad placeholder">Waiting for the map to initialize…</p>;
  }

  return (
    <div className="drawer-pad">
      <label className={`file-btn${busy ? " disabled" : ""}`}>
        {busy && <span className="spinner" aria-hidden="true" />}
        {busy ? "Loading…" : "Choose shapefile (.zip)"}
        <input type="file" accept=".zip" onChange={handleFile} disabled={busy} hidden />
      </label>

      <p className="placeholder">
        Zip must contain the <code>.shp</code>, <code>.dbf</code>, and <code>.prj</code>{" "}
        files together. Polygons draw with a purple outline and no fill; points draw as
        blue dots.
      </p>

      {status && <p className="placeholder">{status}</p>}
    </div>
  );
}
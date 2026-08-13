import { useEffect, useRef } from "react";
import LayerList from "@arcgis/core/widgets/LayerList.js";

export default function LayersPanel({ view }) {
  const hostRef = useRef(null);

  useEffect(() => {
    if (!view || !hostRef.current) return;

    // Esri widgets accept any DOM node as `container` — that's what lets the real
    // LayerList live in our sidebar instead of floating over the map.
    // destroy() removes that container from the DOM, so hand over a throwaway inner
    // node and keep React's div intact.
    const node = document.createElement("div");
    hostRef.current.appendChild(node);

    const layerList = new LayerList({ view, container: node });
    return () => layerList.destroy();
  }, [view]);

  if (!view) {
    return <p className="drawer-pad placeholder">Waiting for the map to initialize…</p>;
  }

  return (
    <>
      <div ref={hostRef} />
      <p className="drawer-pad placeholder">
        Layers appear here once parcel data is added.
      </p>
    </>
  );
}

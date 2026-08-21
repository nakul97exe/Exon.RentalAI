import { useEffect, useRef } from "react";
import Search from "@arcgis/core/widgets/Search.js";

// Palo Alto's parcel identifier column. Detection across cities comes later —
// detectIdField() in lib/shapefile.js already does it for the map click path.
const APN_FIELD = "APN";

const parcelSourceFrom = (layer) => ({
  layer,
  searchFields: [APN_FIELD],
  displayField: APN_FIELD,
  name: "Parcel APN",
  placeholder: "e.g. 127-53-008",
  exactMatch: true,
  outFields: ["*"], // the popup and the chat context both need every attribute
});

export default function FindParcelPanel({ view, onParcelSelect }) {
  const hostRef = useRef(null);

  // Held in a ref so a changing callback identity doesn't rebuild the widget.
  const onParcelSelectRef = useRef(onParcelSelect);
  useEffect(() => {
    onParcelSelectRef.current = onParcelSelect;
  });

  useEffect(() => {
    if (!view || !hostRef.current) return;

    // Esri's destroy() removes its container from the DOM. Give it a throwaway inner
    // node so React's own div survives and can be reused.
    const node = document.createElement("div");
    hostRef.current.appendChild(node);

    const search = new Search({
      view,
      container: node,
      // The default source is an address geocoder — it cannot find an APN.
      includeDefaultSources: false,
      sources: [],
      suggestionsEnabled: true,
      minSuggestCharacters: 1,
    });
    // popupEnabled and resultGraphicEnabled are on by default: the widget opens the
    // layer's own popup and highlights the result, then clears both when the popup
    // closes or another feature is clicked. That lifecycle is why we use the widget
    // instead of calling openPopup ourselves.

    let cancelled = false;

    // The parcel layer arrives when the user uploads a shapefile, which can be after
    // this panel mounts — so track the map's layers rather than reading them once.
    const syncSources = async () => {
      // A layer's fields aren't populated until it loads, and "change" fires on add.
      await Promise.all(
        view.map.layers.toArray().map((l) => l.when().catch(() => null)),
      );
      if (cancelled) return;

      const layer = view.map.layers.find((l) =>
        l.fields?.some((f) => f.name === APN_FIELD),
      );
      search.sources = layer ? [parcelSourceFrom(layer)] : [];
    };

    syncSources();
    const layersHandle = view.map.layers.on("change", syncSources);

    // Feeds the searched parcel to the chat in the same shape MapView's click sends.
    const selectHandle = search.on("select-result", (event) => {
      const attributes = { ...(event.result?.feature?.attributes ?? {}) };
      const apn = attributes[APN_FIELD];
      onParcelSelectRef.current?.(apn ? { apn: String(apn), attributes } : null);
    });

    return () => {
      cancelled = true;
      layersHandle.remove();
      selectHandle.remove();
      search.destroy();
    };
  }, [view]);

  if (!view) {
    return <p className="drawer-pad placeholder">Waiting for the map to initialize…</p>;
  }

  return (
    <>
      <div ref={hostRef} />
      <div className="drawer-pad">
        <p className="placeholder">
          Search by APN (exact match) to highlight and select a parcel. You can also
          click a parcel directly on the map.
        </p>
      </div>
    </>
  );
}

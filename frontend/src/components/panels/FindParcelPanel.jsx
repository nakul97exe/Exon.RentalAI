import {useEffect, useRef} from "react";
import Search from "@arcgis/core/widgets/Search.js";


export default function FindParcelPanel({view}) {

  const searchRef = useRef(null);

  useEffect(() => {
    if(!searchRef.current || !view) return;

    // Esri's destroy() removes its container from the DOM. Give it a throwaway inner
    // node so React's own div survives and can be reused.
    const node = document.createElement("div");
    searchRef.current.appendChild(node);

    const search = new Search({view, container: node});

    return () => search.destroy();

  }, [view]);


  return (
    <>
      <div ref={searchRef} />
      <div className="drawer-pad">
        <p className="placeholder">
          Search by APN (exact match) to highlight and select a parcel. You can also click
          a parcel directly on the map.
        </p>
        <p className="placeholder">
          <strong>Slot reserved</strong> — wired up in week 2 (ApnSearch).
        </p>
      </div>
    </>
  );
}

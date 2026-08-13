import { useEffect, useRef } from "react";
import Legend from "@arcgis/core/widgets/Legend.js";

export default function Footer({ view }) {
  const legendRef = useRef(null);

  useEffect(() => {
    if (!view || !legendRef.current) return;

    // Same trick as LayerList: mount the real Esri widget into our own DOM node, via a
    // throwaway inner div since destroy() deletes whatever container it was given.
    const node = document.createElement("div");
    legendRef.current.appendChild(node);

    const legend = new Legend({ view, container: node });
    return () => legend.destroy();
  }, [view]);

  return (
    <footer className="footer">
      <div className="footer-legend">
        <span className="footer-label">Legend</span>
        <div className="footer-legend-host" ref={legendRef} />
      </div>
      <div className="footer-copy">© 2026 Exon. All rights reserved.</div>
    </footer>
  );
}

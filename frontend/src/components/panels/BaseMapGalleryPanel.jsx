import {useEffect, useRef} from 'react';
import BasemapGallery from '@arcgis/core/widgets/BasemapGallery.js';

export default function BaseMapGalleryPanel({view}){
    const baseMapRef = useRef(null);

    useEffect(() => {
        if (!view || !baseMapRef.current) return;

        // Esri's destroy() removes its container from the DOM. Give it a throwaway inner
        // node so React's own div survives and can be reused.
        const node = document.createElement("div");
        baseMapRef.current.appendChild(node);

        const baseMapGallery = new BasemapGallery({view, container: node});
        return () => baseMapGallery.destroy();
    }, [view]);

    if (!view) {
        return <p className="drawer-pad placeholder">Waiting for the map to initialize…</p>;
    }

  return (
    <>
      <div ref={baseMapRef} />
    </>
  );
}
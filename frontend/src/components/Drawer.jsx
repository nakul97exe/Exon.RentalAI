import { RAIL_ITEMS } from "./railItems.js";
import LayersPanel from "./panels/LayersPanel.jsx";
import AddDataPanel from "./panels/AddDataPanel.jsx";
import DocumentsPanel from "./panels/DocumentsPanel.jsx";
import FindParcelPanel from "./panels/FindParcelPanel.jsx";
import BaseMapGalleryPanel from "./panels/BaseMapGalleryPanel.jsx";

export default function Drawer({ panel, view, onClose, onParcelCount }) {
  if (!panel) return null;

  const title = RAIL_ITEMS.find((i) => i.key === panel)?.label ?? panel;

  return (
    <aside className="drawer">
      <div className="drawer-head">
        {title}
        <button className="drawer-close" onClick={onClose} aria-label="Close panel">
          ×
        </button>
      </div>
      <div className="drawer-body">
        {panel === "layers" && <LayersPanel view={view} />}
        {panel === "addData" && (
          <AddDataPanel view={view} onParcelCount={onParcelCount} />
        )}
        {panel === "documents" && <DocumentsPanel />}
        {panel === "findParcel" && <FindParcelPanel view={view} />}
        {panel === "baseMapGallery" && <BaseMapGalleryPanel view={view} />  }
      </div>
    </aside>
  );
}

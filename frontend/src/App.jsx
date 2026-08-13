import { useState } from "react";
import TopBar from "./components/TopBar.jsx";
import IconRail from "./components/IconRail.jsx";
import Drawer from "./components/Drawer.jsx";
import MapView from "./components/MapView.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import Footer from "./components/Footer.jsx";

export default function App() {
  const [activePanel, setActivePanel] = useState(null);
  const [view, setView] = useState(null);
  // { apn, attributes } — attributes travel with each /query request, so nothing
  // parcel-related is stored on the backend.
  const [selectedParcel, setSelectedParcel] = useState(null);
  const [layerCount, setLayerCount] = useState(0);

  return (
    <div className="app">
      <TopBar city={null} docCount={0} parcelCount={layerCount} />

      <div className="app-body">
        <IconRail active={activePanel} onSelect={setActivePanel} />
        <Drawer
          panel={activePanel}
          view={view}
          onParcelCount={setLayerCount}
          onClose={() => setActivePanel(null)}
        />

        <div className="map-wrap">
          <MapView onViewReady={setView} onParcelSelect={setSelectedParcel} />
        </div>

        <ChatPanel selectedParcel={selectedParcel} />
      </div>

      <Footer view={view} />
    </div>
  );
}

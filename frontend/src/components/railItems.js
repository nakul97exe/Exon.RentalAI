// Single source of truth for the rail buttons and drawer titles.
// Lives in its own file because a .jsx file that exports both a component and a
// constant breaks Vite's fast refresh (react-refresh/only-export-components).
export const RAIL_ITEMS = [
  { key: "layers", icon: "layers", label: "Layers" },
  { key: "addData", icon: "upload", label: "Add data" },
  { key: "documents", icon: "document", label: "Documents" },
  { key: "findParcel", icon: "search", label: "Find parcel" },
  { key: "baseMapGallery", icon: "basemap", label: "Basemap gallery" },
];

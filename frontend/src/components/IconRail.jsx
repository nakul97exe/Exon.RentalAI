import Icon from "./Icon.jsx";

export const RAIL_ITEMS = [
  { key: "layers", icon: "layers", label: "Layers" },
  { key: "addData", icon: "upload", label: "Add data" },
  { key: "documents", icon: "document", label: "Documents" },
  { key: "findParcel", icon: "search", label: "Find parcel" },
  { key: "baseMapGallery", icon: "basemap", label: "Basemap gallery" }
];

export default function IconRail({ active, onSelect }) {
  return (
    <nav className="rail">
      {RAIL_ITEMS.map((item) => (
        <button
          key={item.key}
          className={`rail-btn${active === item.key ? " active" : ""}`}
          title={item.label}
          aria-label={item.label}
          aria-pressed={active === item.key}
          // Clicking the active icon collapses the drawer.
          onClick={() => onSelect(active === item.key ? null : item.key)}
        >
          <Icon name={item.icon} />
        </button>
      ))}
    </nav>
  );
}

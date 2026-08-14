import Icon from "./Icon.jsx";
import { RAIL_ITEMS } from "./railItems.js";

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

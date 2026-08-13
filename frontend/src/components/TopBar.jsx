export default function TopBar({ city, docCount, parcelCount }) {
  return (
    <header className="topbar">
      <span className="topbar-title">Rental Housing Compliance Assistant</span>
      <div className="topbar-meta">
        <span>City: {city ?? "—"}</span>
        <span>{parcelCount ?? 0} parcels loaded</span>
        <span>{docCount ?? 0} documents indexed</span>
      </div>
    </header>
  );
}

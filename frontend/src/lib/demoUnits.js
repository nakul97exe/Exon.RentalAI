/**
 * Synthetic unit counts for demo parcel layers.
 *
 * Public parcel datasets often ship without a unit count, but the ordinance
 * section that applies depends on how many units a building has. Without the
 * field there is nothing to show in the popup and nothing for the parcel tool
 * to reason about.
 *
 * This fabricates one. It is NOT real data — it exists so the demo layer can
 * exercise the ordinance's unit thresholds. Delete this module and its call in
 * shapefile.js once the layer carries real unit counts.
 *
 * The value comes from a hash of the parcel ID, not Math.random(), so a parcel
 * reports the same count every time. A random value would change on each
 * reload and the "same question, different parcel, different answer"
 * comparison would not be reproducible.
 */

// The field name the backend already looks for in USEFUL_FIELDS.
const UNITS_FIELD = "UNITS";

// Weights out of 100, sized so a demo lands on both sides of the ordinance's
// 10-unit threshold often enough to show the difference.
const BUCKETS = [
  { weight: 40, low: 1, high: 1 },    // single-family -> one month's rent
  { weight: 25, low: 2, high: 9 },    // small multi-family, still under 10
  { weight: 35, low: 10, high: 60 },  // 10+ units -> the dollar table
];

// FNV-1a. Any stable string hash works; this one is short and has no deps.
const hashString = (value) => {
  let hash = 0x811c9dc5;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
};

export const demoUnitCount = (parcelId) => {
  const seed = hashString(String(parcelId));
  const pick = seed % 100;

  let cursor = 0;
  for (const { weight, low, high } of BUCKETS) {
    cursor += weight;
    if (pick < cursor) {
      if (low === high) return low;
      // A different slice of the hash, so the bucket and the value inside it
      // are not correlated.
      return low + (Math.floor(seed / 100) % (high - low + 1));
    }
  }
  return 1; // unreachable while the weights sum to 100
};

const isBlank = (value) =>
  value === null || value === undefined || value === "" || value === "null";

/**
 * Add a UNITS property to every feature that lacks one.
 *
 * Mutates in place — these features were just parsed from the upload and are
 * not shared with anything yet. Returns the same array for convenience.
 *
 * Only ever fills a gap: a layer that really carries UNITS is left untouched,
 * and a layer with no detectable parcel ID is skipped entirely.
 */
export const applyDemoUnits = (features, idField) => {
  if (!idField) return features;

  for (const feature of features) {
    const properties = feature.properties;
    if (!properties || isBlank(properties[idField])) continue;
    if (!isBlank(properties[UNITS_FIELD])) continue;

    properties[UNITS_FIELD] = demoUnitCount(properties[idField]);
  }

  return features;
};

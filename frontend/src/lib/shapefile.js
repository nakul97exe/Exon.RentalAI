import shp from "shpjs";
import GeoJSONLayer from "@arcgis/core/layers/GeoJSONLayer.js";

const PURPLE = [128, 0, 128, 0.5];
const BLUE = [0, 0, 255, 0.5];

const RENDERERS = {
    polygon: {
        type: "simple",
        symbol:{
            type: "simple-fill",
            color: [0, 0, 0, 0], // transparent fill
            outline: {color: PURPLE, width: 2}
        }
    },
    point: {
        type: "simple",
        symbol: {
            type: "simple-marker",
            color: BLUE,
            size: 6,
            style: "circle",
            outline: { color: [255, 255, 255, 0.9], width: 0.8 },
        }
    },
    polyline: {
        type: "simple",
        symbol: {
            type: "simple-line",
            color: PURPLE,
            width: 2,
        }
    }
}

// GeoJSON geometry type -> Esri geometryType
const GEOM_MAP ={
    Point: "point",
    MultiPoint: "point",
    LineString: "polyline",
    MultiLineString: "polyline",
    Polygon: "polygon",
    MultiPolygon: "polygon"
}

const rendererFor = (esriType) => {
    const renderer = RENDERERS[esriType];
    if(!renderer) throw new Error(`No renderer for geometry type ${esriType}`);
    return renderer;
}

// Which attribute holds the parcel identifier varies by city, so detect it rather
// than hardcoding "APN". Shared with the map click handler.
const ID_FIELD_PATTERN = /^(apn|apn_?\d*|parcel|parcelid|parcel_?id|pin|ain)$/i;

export const detectIdField = (attributes) =>
    Object.keys(attributes ?? {}).find((key) => ID_FIELD_PATTERN.test(key)) ?? null;


const fieldInfosFrom = (features) => {
    const keys = new Set();
    // Sample a few features — shapefiles are homogeneous, but nulls can hide a key.
    for (const feature of features.slice(0, 20)) {
        for (const key of Object.keys(feature.properties ?? {})) keys.add(key);
    }
    return [...keys].map((name) => ({ fieldName: name, label: name }));
}

const makeLayer = (title, esriType, features) => {
    // GeoJSONLayer loads from a URL, so we wrap the parsed features in a Blob URL.
    const blob = new Blob([JSON.stringify({type: "FeatureCollection", features})], {
        type: "application/json"
    });

      const url = URL.createObjectURL(blob);

      const fieldInfos = fieldInfosFrom(features);

      // Use the parcel identifier as the popup heading when the data has one.
      const idField = detectIdField(
        Object.fromEntries(fieldInfos.map((f) => [f.fieldName, true])),
      );

      const layer = new GeoJSONLayer({
        url,
        title,
        geometryType: esriType,
        renderer: rendererFor(esriType),
        outFields: ["*"],
        popupTemplate: {
            title: idField ? `${title} — {${idField}}` : title,
            // Explicit fieldInfos — auto-detection is unreliable on GeoJSONLayer.
            content: [{type: "fields", fieldInfos}]
        }
      });

    // Free the blob once the layer has read it. (Means layer.refresh() won't work — fine here.)
    layer.when(
        () => URL.revokeObjectURL(url),
        () => URL.revokeObjectURL(url),
    );

    return layer;
}

/**
 * Parse a zipped shapefile into a single GeoJSONLayer.
 * The shapefile format allows only one geometry type per .shp file, so no
 * grouping is needed — read the type off the first feature.
 */
export async function layersFromShapefileZip(file) {
  const parsed = await shp(await file.arrayBuffer());

  // A zip can technically hold several shapefiles; we support one.
  if (Array.isArray(parsed) && parsed.length > 1) {
    console.warn(`Zip contains ${parsed.length} shapefiles; loading only the first.`);
  }
  const fc = Array.isArray(parsed) ? parsed[0] : parsed;

  const features = (fc.features ?? []).filter((f) => GEOM_MAP[f.geometry?.type]);
  if (!features.length) {
    throw new Error("No point, line, or polygon features found.");
  }

  const esriType = GEOM_MAP[features[0].geometry.type];

  // shpjs reports the path inside the zip — keep just the file name.
  const baseName = file.name.replace(/\.zip$/i, "");
  const name = (fc.fileName || baseName).split(/[\\/]/).pop();

  return {
    layer: makeLayer(name, esriType, features),
    featureCount: features.length,
  };
}
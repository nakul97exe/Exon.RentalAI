# Sample files

The demo data used to produce the walkthroughs in the project documentation. Download
these to try the app without sourcing your own data.

| File | Size | What it is | Where it is used |
|---|---|---|---|
| [`palo-alto-municipal-code-9-68.pdf`](palo-alto-municipal-code-9-68.pdf) | 56 KB | Palo Alto Municipal Code, Chapter 9.68 — the rental-housing ordinance | Documents drawer → upload |
| [`AssessorParcels.zip`](AssessorParcels.zip) | 5.1 MB | Palo Alto parcel layer, zipped shapefile (`.shp`, `.dbf`, `.shx`, `.prj`) | Add data drawer → upload |

## How to use them

1. Open the app: **https://red-beach-0bbb9cb1e.7.azurestaticapps.net/**
2. **Add data** drawer → upload the parcel `.zip`
3. **Documents** drawer → upload the ordinance PDF
4. Click a parcel on the map, then ask a question in the chat panel

Upload the shapefile before the document if you want parcel-specific answers on your
first question — the map selection is what makes the answer depend on the property.

## Notes

The shapefile must be a **zip** containing at least `.shp`, `.dbf`, `.shx` and `.prj`.
The `.prj` matters: it is how the projection is read and reprojected to WGS84. A zip
without it will not display in the correct place.

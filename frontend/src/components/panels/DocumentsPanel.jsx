import { useState } from "react";
import { uploadDocument } from "../../api/client.js";

export default function DocumentsPanel({onDocCount}) {
  const [documentStatus, setDocumentStatus] = useState(null);
  const [documentBusy, setDocumentBusy] = useState(false);

  const handleDocumentFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = ""; // lets you re-pick the same file

    if (!file) return;

    setDocumentBusy(true);
    setDocumentStatus(`Reading ${file.name}…`);

    try {
      const data = await uploadDocument(file);
      setDocumentStatus(
        `Indexed ${data.chunks} chunks from ${data.sections.length} sections.`,
      );
      setDocumentBusy(false);
      onDocCount?.((n) => n + 1);
    } catch (err) {
      setDocumentBusy(false);
      setDocumentStatus(`Failed: ${err.message}`);
    } finally {
      setDocumentBusy(false);
    }
  };

  return (
    <div className="drawer-pad">
      <label className={`file-btn${documentBusy ? " disabled" : ""}`}>
        {documentBusy && <span className="spinner" aria-hidden="true" />}
        {documentBusy ? "Indexing…" : "Choose document"}
        <input
          type="file"
          accept=".pdf,.txt,.md,.csv,.xlsx,.xls"
          onChange={handleDocumentFile}
          disabled={documentBusy}
          hidden
        />
      </label>

      <p className="placeholder">
        Upload ordinance documents (PDF, TXT, CSV, Excel). Each is chunked by section
        and embedded into the vector store.
      </p>

      {documentStatus && <p className="placeholder">{documentStatus}</p>}
    </div>
  );
}

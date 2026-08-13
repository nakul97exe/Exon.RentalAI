import { useEffect, useRef, useState } from "react";
import { askQuestion } from "../api/client.js";

export default function ChatPanel({ selectedParcel }) {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  // Keep the newest message in view as the conversation grows.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const handleSubmit = async (event) => {
    event.preventDefault();

    const question = draft.trim();
    if (!question || busy) return;

    setDraft("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setBusy(true);

    try {
      const data = await askQuestion({
        question,
        apn: selectedParcel?.apn ?? null,
        parcelAttributes: selectedParcel?.attributes ?? null,
      });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.answer,
          sources: data.sources,
          validation: data.validation,
          trace: data.trace,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `Failed: ${err.message}`, error: true },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="chat">
      <div className="chat-head">
        Assistant
        <span className="chat-context">
          {selectedParcel ? `APN ${selectedParcel.apn}` : "no parcel selected"}
        </span>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <p className="placeholder">
            Ask a question about the uploaded ordinance. Select a parcel on the map to
            include its attributes as context.
          </p>
        )}

        {messages.map((message, index) => (
          <Message key={index} message={message} />
        ))}

        {busy && (
          <div className="msg msg-assistant">
            <span className="spinner spinner-dark" aria-hidden="true" />
            Thinking…
          </div>
        )}

        <div ref={endRef} />
      </div>

      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask a question…"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !draft.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}

function Message({ message }) {
  const { role, text, sources, validation, trace, error } = message;

  return (
    <div className={`msg msg-${role}${error ? " msg-error" : ""}`}>
      <div className="msg-text">{text}</div>

      {(sources?.length > 0 || validation?.checked) && (
        <div className="sources">
          {sources?.map((source) => (
            <span
              key={source.section}
              className="source-chip"
              title={`${source.title ?? ""} — ${source.source_file ?? ""}`}
            >
              {source.section} · {source.score}
            </span>
          ))}

          {/* Only shown when the validator actually ran — never claim a verdict
              we don't have. */}
          {validation?.checked && <ValidationBadge validation={validation} />}
        </div>
      )}

      {validation?.unsupported_claims?.length > 0 && (
        <ul className="unsupported">
          {validation.unsupported_claims.map((claim, i) => (
            <li key={i}>{claim}</li>
          ))}
        </ul>
      )}

      {/* The reasoning trace is the visible evidence of agentic behavior. */}
      {trace && (
        <details className="trace">
          <summary>
            {trace.attempts} search{trace.attempts > 1 ? "es" : ""}
            {trace.sufficient ? "" : " · insufficient"}
          </summary>
          <div className="trace-body">
            <div>
              <strong>Plan:</strong> {trace.plan?.reasoning}
            </div>
            <div>
              <strong>Tools:</strong>{" "}
              {[
                trace.plan?.needs_documents && "documents",
                trace.plan?.needs_parcel && "parcel",
              ]
                .filter(Boolean)
                .join(" + ") || "none"}
            </div>
            <div>
              <strong>Queries:</strong> {trace.queries?.join(" → ")}
            </div>
            {trace.notes?.length > 0 && (
              <div>
                <strong>Missing:</strong> {trace.notes.join("; ")}
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

function ValidationBadge({ validation }) {
  const { supported, unsupported_claims: claims = [] } = validation;

  if (supported) {
    return (
      <span className="source-chip badge-ok" title="Every claim traced to a source">
        ✓ verified
      </span>
    );
  }

  return (
    <span
      className="source-chip badge-warn"
      title={claims.join(" · ") || "Unsupported claims found"}
    >
      ⚠ {claims.length || "unverified"} unsupported
    </span>
  );
}

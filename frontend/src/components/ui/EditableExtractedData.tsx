"use client";
import { useState, useEffect } from "react";
import { Edit2, Save, X, Plus, Trash2 } from "lucide-react";
import { documentService } from "@/services/documentService";
import type { DocumentResponse } from "@/types";

interface EditableExtractedDataProps {
  document: DocumentResponse;
  onUpdate: (doc: DocumentResponse) => void;
  onError: (error: string) => void;
}

export function EditableExtractedData({ document, onUpdate, onError }: EditableExtractedDataProps) {
  const normalize = (data: Record<string, unknown>) =>
    Object.fromEntries(
      Object.entries(data).map(([k, v]) => [
        k,
        typeof v === "object" && v !== null
          ? String((v as Record<string, unknown>).text ?? JSON.stringify(v))
          : String(v ?? ""),
      ])
    );

  const [isEditing, setIsEditing] = useState(false);
  const [editedFields, setEditedFields] = useState<Record<string, string>>(
    normalize((document.extracted_data as Record<string, unknown>) || {})
  );
  const [newKey, setNewKey] = useState("");
  const [newVal, setNewVal] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // Re-sync local fields whenever the parent document's extracted_data changes
  // (e.g. after background Gemini extraction completes and polling refreshes the doc).
  useEffect(() => {
    if (!isEditing) {
      setEditedFields(normalize((document.extracted_data as Record<string, unknown>) || {}));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [document.extracted_data]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const updated = await documentService.updateExtractedData(
        document.id.toString(),
        editedFields
      );
      onUpdate(updated);
      setIsEditing(false);
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setEditedFields(normalize((document.extracted_data as Record<string, unknown>) || {}));
    setNewKey("");
    setNewVal("");
    setIsEditing(false);
  };

  const addField = () => {
    const k = newKey.trim().toLowerCase().replace(/\s+/g, "_");
    if (!k) return;
    setEditedFields((prev) => ({ ...prev, [k]: newVal.trim() }));
    setNewKey("");
    setNewVal("");
  };

  const removeField = (key: string) => {
    setEditedFields((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const hasFields = Object.keys(editedFields).length > 0;

  if (!isEditing) {
    return (
      <div>
        {hasFields ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: "4px 12px", marginBottom: 8 }}>
            {Object.entries(editedFields).map(([k, v]) => (
              <div key={k} style={{ fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                <span style={{ textTransform: "capitalize" }}>{k.replace(/_/g, " ")}</span>:{" "}
                <span style={{ color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                  {String(v).slice(0, 50)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ fontSize: "0.6875rem", color: "var(--text-muted)", marginBottom: 8 }}>
            No data extracted — add fields manually.
          </p>
        )}
        <button
          className="btn btn-ghost"
          onClick={() => setIsEditing(true)}
          style={{ fontSize: "0.6875rem", padding: "4px 10px", display: "flex", alignItems: "center", gap: 5 }}
        >
          <Edit2 size={12} />
          {hasFields ? "Edit extracted data" : "Add data manually"}
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {Object.entries(editedFields).map(([key, value]) => (
        <div key={key} style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "capitalize", width: 130, flexShrink: 0 }}>
            {key.replace(/_/g, " ")}
          </span>
          <input
            className="input"
            type="text"
            value={value}
            onChange={(e) => setEditedFields((prev) => ({ ...prev, [key]: e.target.value }))}
            style={{ flex: 1, fontSize: "0.75rem", padding: "5px 8px" }}
          />
          <button
            type="button"
            onClick={() => removeField(key)}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 2 }}
          >
            <Trash2 size={13} />
          </button>
        </div>
      ))}

      {/* Add new field row */}
      <div style={{ display: "flex", gap: 6, alignItems: "center", borderTop: "1px dashed var(--border)", paddingTop: 8, marginTop: 4 }}>
        <input
          className="input"
          type="text"
          placeholder="Field name"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          style={{ width: 120, fontSize: "0.75rem", padding: "5px 8px" }}
        />
        <input
          className="input"
          type="text"
          placeholder="Value"
          value={newVal}
          onChange={(e) => setNewVal(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addField()}
          style={{ flex: 1, fontSize: "0.75rem", padding: "5px 8px" }}
        />
        <button
          type="button"
          className="btn btn-ghost"
          onClick={addField}
          disabled={!newKey.trim()}
          style={{ padding: "5px 8px" }}
        >
          <Plus size={13} />
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        <button className="btn btn-primary" onClick={handleSave} disabled={isSaving} style={{ flex: 1 }}>
          <Save size={13} />
          {isSaving ? "Saving…" : "Save"}
        </button>
        <button className="btn btn-ghost" onClick={handleCancel} disabled={isSaving}>
          <X size={13} />
          Cancel
        </button>
      </div>
    </div>
  );
}

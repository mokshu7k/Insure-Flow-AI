"use client";
import { useState, useEffect } from "react";
import { Edit2, Save, X, Plus, Trash2, Lock } from "lucide-react";
import { documentService } from "@/services/documentService";
import type { ClaimDocumentResponse } from "@/types";

interface EditableExtractedDataProps {
  document: ClaimDocumentResponse;
  onUpdate: (doc: ClaimDocumentResponse) => void;
  onError: (error: string) => void;
}

/**
 * Field keys that must NEVER be editable post-OCR.
 * These are critical for claim processing / fraud prevention.
 * Matching is done on the normalised lowercase key (underscored).
 */
const LOCKED_FIELD_PATTERNS: RegExp[] = [
  /total.*(claim|amount|amt)/,
  /amount.*(claim|total)/,
  /claim.*(amount|amt)/,
  /date.*(admit|admission|hospitali)/,
  /admit.*(date|on)/,
  /admission.*(date|on)/,
  /date.*(discharge|exit)/,
  /discharge.*(date|on)/,
  /vehicle.*(reg|registration|number|no)/,
  /reg(istration)?.*(vehicle|no|number)/,
  /^policy.*(no|number|id)$/,
  /^pan.*(no|number|card)?$/,
  /pan_number/,
  /aadhaar|aadhar/,
];

/** Returns true when the extracted-data key should be read-only. */
function isLocked(key: string): boolean {
  const k = key.toLowerCase();
  return LOCKED_FIELD_PATTERNS.some((re) => re.test(k));
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

  /** Splits normalised fields into locked (read-only) and editable buckets. */
  const partition = (fields: Record<string, string>) => {
    const locked: Record<string, string> = {};
    const editable: Record<string, string> = {};
    for (const [k, v] of Object.entries(fields)) {
      if (isLocked(k)) locked[k] = v;
      else editable[k] = v;
    }
    return { locked, editable };
  };

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

  const { locked: lockedFields, editable: editableFields } = partition(editedFields);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Merge edited editable fields back with the unchanged locked fields before saving
      const merged = { ...lockedFields, ...editableFields };
      const updated = await documentService.updateClaimDocData(
        document.id.toString(),
        merged
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
    if (!k || isLocked(k)) return;
    setEditedFields((prev) => ({ ...prev, [k]: newVal.trim() }));
    setNewKey("");
    setNewVal("");
  };

  const removeField = (key: string) => {
    if (isLocked(key)) return;
    setEditedFields((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const hasFields = Object.keys(editedFields).length > 0;
  const newKeyNorm = newKey.trim().toLowerCase().replace(/\s+/g, "_");

  // ── styles shared between modes ───────────────────────────────────────────
  const labelStyle: React.CSSProperties = {
    fontSize: "0.6875rem", color: "var(--text-muted)",
    textTransform: "capitalize", width: 130, flexShrink: 0,
  };
  const lockBadge: React.CSSProperties = {
    display: "inline-flex", alignItems: "center", gap: 3,
    fontSize: "0.5625rem", color: "var(--text-muted)",
    background: "var(--bg-muted, rgba(100,116,139,0.08))",
    border: "1px solid var(--border)",
    borderRadius: 4, padding: "1px 5px", flexShrink: 0,
  };

  // ── VIEW MODE ─────────────────────────────────────────────────────────────
  if (!isEditing) {
    return (
      <div>
        {hasFields ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: "4px 12px", marginBottom: 8 }}>
            {Object.entries(editedFields).map(([k, v]) => (
              <div key={k} style={{ fontSize: "0.6875rem", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
                <span style={{ textTransform: "capitalize" }}>{k.replace(/_/g, " ")}</span>:{" "}
                <span style={{ color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                  {String(v).slice(0, 50)}
                </span>
                {isLocked(k) && (
                  <span style={lockBadge} title="This field is locked and cannot be changed">
                    <Lock size={8} /> locked
                  </span>
                )}
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

  // ── EDIT MODE ─────────────────────────────────────────────────────────────
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>

      {/* Locked fields — always read-only */}
      {Object.keys(lockedFields).length > 0 && (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
            <Lock size={10} color="var(--text-muted)" />
            <span style={{ fontSize: "0.625rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Locked fields (fraud-sensitive — cannot be changed)
            </span>
          </div>
          {Object.entries(lockedFields).map(([key, value]) => (
            <div key={key} style={{ display: "flex", gap: 6, alignItems: "center", opacity: 0.7 }}>
              <span style={labelStyle}>{key.replace(/_/g, " ")}</span>
              <input
                className="input"
                type="text"
                value={value}
                readOnly
                disabled
                title="This field is locked and cannot be edited"
                style={{ flex: 1, fontSize: "0.75rem", padding: "5px 8px", cursor: "not-allowed", background: "var(--bg-muted, rgba(100,116,139,0.06))" }}
              />
              <span style={lockBadge}>
                <Lock size={9} /> locked
              </span>
            </div>
          ))}
          <div style={{ borderTop: "1px solid var(--border)", marginTop: 4 }} />
        </>
      )}

      {/* Editable fields */}
      {Object.entries(editableFields).map(([key, value]) => (
        <div key={key} style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={labelStyle}>{key.replace(/_/g, " ")}</span>
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

      {/* Add new field row — blocked if the name would be a locked key */}
      <div style={{ display: "flex", gap: 6, alignItems: "center", borderTop: "1px dashed var(--border)", paddingTop: 8, marginTop: 4 }}>
        <input
          className="input"
          type="text"
          placeholder="Field name"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          style={{
            width: 120, fontSize: "0.75rem", padding: "5px 8px",
            borderColor: newKeyNorm && isLocked(newKeyNorm) ? "var(--red, #ef4444)" : undefined,
          }}
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
          disabled={!newKey.trim() || isLocked(newKeyNorm)}
          title={isLocked(newKeyNorm) ? "This field name is locked and cannot be added" : undefined}
          style={{ padding: "5px 8px" }}
        >
          <Plus size={13} />
        </button>
      </div>
      {newKeyNorm && isLocked(newKeyNorm) && (
        <p style={{ fontSize: "0.625rem", color: "var(--red, #ef4444)", marginTop: -4 }}>
          <Lock size={9} style={{ display: "inline", marginRight: 3 }} />
          &quot;{newKey}&quot; is a locked field and cannot be added manually.
        </p>
      )}

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

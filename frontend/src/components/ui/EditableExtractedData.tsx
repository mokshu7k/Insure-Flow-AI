"use client";
import { useState } from "react";
import { Edit, Save, X } from "lucide-react";
import { documentService } from "@/services/documentService";
import type { DocumentResponse } from "@/types";

interface EditableExtractedDataProps {
  document: DocumentResponse;
  onUpdate: (doc: DocumentResponse) => void;
  onError: (error: string) => void;
}

export function EditableExtractedData({ document, onUpdate, onError }: EditableExtractedDataProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedData, setEditedData] = useState<Record<string, unknown>>(document.extracted_data || {});
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const updated = await documentService.updateExtractedData(
        document.id.toString(),
        editedData
      );
      onUpdate(updated);
      setIsEditing(false);
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Failed to save extracted data");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setEditedData(document.extracted_data || {});
    setIsEditing(false);
  };

  const handleFieldChange = (key: string, value: unknown) => {
    setEditedData((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  if (!editedData || Object.keys(editedData).length === 0) {
    return (
      <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)" }}>
        No structured data extracted
      </div>
    );
  }

  if (isEditing) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {Object.entries(editedData).map(([key, value]) => {
          const displayValue =
            typeof value === "object" && value !== null
              ? (value as Record<string, unknown>).text ?? JSON.stringify(value)
              : value;

          return (
            <div key={key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label style={{ fontSize: "0.6875rem", fontWeight: 500, textTransform: "capitalize" }}>
                {key.replace(/_/g, " ")}
              </label>
              <input
                type="text"
                className="input"
                value={String(displayValue)}
                onChange={(e) => handleFieldChange(key, e.target.value)}
                style={{ fontSize: "0.75rem", padding: "6px 8px" }}
              />
            </div>
          );
        })}
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={isSaving}
            style={{ flex: 1 }}
          >
            <Save size={13} />
            {isSaving ? "Saving…" : "Save"}
          </button>
          <button
            className="btn btn-ghost"
            onClick={handleCancel}
            disabled={isSaving}
            style={{ flex: 1 }}
          >
            <X size={13} />
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "2px 12px" }}>
        {Object.entries(editedData)
          .slice(0, 8)
          .map(([key, value]) => {
            const displayValue =
              typeof value === "object" && value !== null
                ? (value as Record<string, unknown>).text ?? JSON.stringify(value)
                : value;

            return (
              <div key={key} style={{ fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                <span style={{ textTransform: "capitalize" }}>{key.replace(/_/g, " ")}</span>:{" "}
                <span style={{ color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                  {String(displayValue).slice(0, 40)}
                </span>
              </div>
            );
          })}
      </div>
      <button
        className="btn btn-ghost"
        onClick={() => setIsEditing(true)}
        style={{ width: "fit-content", fontSize: "0.75rem" }}
      >
        <Edit size={13} />
        Edit Data
      </button>
    </div>
  );
}

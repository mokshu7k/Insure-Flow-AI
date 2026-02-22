"use client";
import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { useAuthStore } from "@/store/authStore";
import { claimService } from "@/services/claimService";
import { documentService } from "@/services/documentService";
import type { InlineOcrResult } from "@/services/documentService";
import { complianceService } from "@/services/complianceService";
import { policyService } from "@/services/policyService";
import api from "@/services/api";
import type { ClaimDocumentResponse, ClaimType, DocumentRequirement, DocumentType, Policy } from "@/types";
import {
    Heart, Car, ReceiptText, Upload, X, CheckCircle2,
    ChevronRight, ChevronLeft, ArrowRight, Loader2, FileText, Mic, MicOff, Loader, AlertTriangle,
    Shield, AlertCircle, Building2, Edit2,
} from "lucide-react";

// ── Document spec (one upload slot) ──────────────────────────────────────────
interface DocSpec {
    type: DocumentType;
    label: string;
    required: boolean;
    hint: string;
    requirement_id?: string;      // NEW — links to DocumentRequirement row
    document_type_code?: string;  // NEW — for template-aware upload
}

const DOC_CONFIG: Record<ClaimType, DocSpec[]> = {
    HEALTH: [
        { type: "DISCHARGE_SUMMARY", label: "Discharge Summary", required: true, hint: "Hospital discharge letter" },
        { type: "HOSPITAL_BILL",      label: "Hospital Bill",      required: true, hint: "Itemized hospital bill" },
        { type: "AADHAAR",            label: "ID Proof (Aadhaar)", required: true, hint: "Aadhaar card" },
        { type: "LAB_REPORT",         label: "Lab / Medical Report", required: false, hint: "Diagnostic reports" },
        { type: "PRESCRIPTION",       label: "Prescription",       required: false, hint: "Doctor prescriptions" },
    ],
    MOTOR: [
        { type: "OTHER",     label: "Policy Document",    required: true,  hint: "Vehicle insurance policy" },
        { type: "OTHER",     label: "Vehicle RC",         required: true,  hint: "Registration certificate" },
        { type: "OTHER",     label: "Driving Licence",    required: true,  hint: "Valid driving licence" },
        { type: "FIR_REPORT", label: "FIR / Police Report", required: false, hint: "If applicable" },
        { type: "OTHER",     label: "Repair Estimate",    required: false, hint: "Workshop estimate" },
    ],
    REIMBURSEMENT: [
        { type: "HOSPITAL_BILL",  label: "Original Bills",    required: true,  hint: "Hospital / pharmacy bills" },
        { type: "CLAIM_FORM",     label: "Signed Claim Form", required: true,  hint: "Insurance claim form" },
        { type: "AADHAAR",        label: "ID Proof",          required: true,  hint: "Aadhaar / PAN" },
        { type: "PRESCRIPTION",   label: "Prescription",      required: false, hint: "Doctor prescription" },
        { type: "OTHER",          label: "Payment Receipts",  required: false, hint: "Proof of payment" },
    ],
};

// ── Step indicator ────────────────────────────────────────────────────────────
function StepBar({ current }: { current: number }) {
    const steps = ["Consent", "Policy", "Documents", "Confirm"];
    return (
        <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 28 }}>
            {steps.map((label, i) => {
                const n = i + 1;
                const done = n < current;
                const active = n === current;
                return (
                    <div key={n} style={{ display: "flex", alignItems: "center", flex: i < steps.length - 1 ? 1 : undefined }}>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                            <div style={{
                                width: 26, height: 26, borderRadius: "50%",
                                display: "flex", alignItems: "center", justifyContent: "center",
                                fontSize: "0.6875rem", fontWeight: 600,
                                background: done ? "var(--green)" : active ? "var(--blue)" : "var(--bg-surface)",
                                border: done ? "none" : active ? "none" : "1px solid var(--border)",
                                color: (done || active) ? "#fff" : "var(--text-muted)",
                            }}>
                                {done ? <CheckCircle2 size={14} /> : n}
                            </div>
                            <span style={{ fontSize: "0.625rem", color: active ? "var(--text-primary)" : "var(--text-muted)", whiteSpace: "nowrap" }}>
                                {label}
                            </span>
                        </div>
                        {i < steps.length - 1 && (
                            <div style={{ flex: 1, height: 1, background: done ? "var(--green)" : "var(--border)", margin: "0 6px", marginBottom: 16 }} />
                        )}
                    </div>
                );
            })}
        </div>
    );
}

// ── Claim type card ───────────────────────────────────────────────────────────
const TYPE_META: Record<ClaimType, { icon: React.ReactNode; title: string; desc: string; color: string }> = {
    HEALTH: { icon: <Heart size={22} />, title: "Health", desc: "Hospitalisation, surgery, day-care treatment", color: "var(--green)" },
    MOTOR: { icon: <Car size={22} />, title: "Motor", desc: "Vehicle damage, accident, theft", color: "var(--blue)" },
    REIMBURSEMENT: { icon: <ReceiptText size={22} />, title: "Reimbursement", desc: "Out-of-pocket medical expenses", color: "var(--amber)" },
};

// ── File drop zone ────────────────────────────────────────────────────────────
function FileZone({
    spec, file, onChange, validationError, validationResult, onResubmit, checking,
}: {
    spec: DocSpec;
    file: File | undefined;
    onChange: (f: File | null) => void;
    validationError?: string | null;
    validationResult?: { valid: boolean; reason: string; detected_type?: string } | null;
    onResubmit?: () => void;
    checking?: boolean;
}) {
    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        const dropped = e.dataTransfer.files[0];
        if (dropped) onChange(dropped);
    }, [onChange]);

    const isInvalid = validationResult && !validationResult.valid;
    const isValid = validationResult && validationResult.valid;
    const borderColor = isInvalid
        ? "rgba(239,68,68,0.7)"
        : isValid
            ? "var(--green)"
            : file
                ? "var(--green)"
                : "var(--border)";
    const bgColor = isInvalid
        ? "rgba(239,68,68,0.05)"
        : isValid
            ? "var(--green-bg, rgba(34,197,94,0.06))"
            : file
                ? "var(--green-bg, rgba(34,197,94,0.06))"
                : "var(--bg-surface)";

    return (
        <div>
        <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            style={{
                border: `1px dashed ${borderColor}`,
                borderRadius: 6,
                padding: "12px 14px",
                background: bgColor,
                display: "flex", alignItems: "center", gap: 10,
                cursor: "pointer",
                transition: "border-color 150ms",
            }}
            onClick={() => {
                const input = document.createElement("input");
                input.type = "file";
                input.accept = ".pdf,.jpg,.jpeg,.png,.webp";
                input.onchange = (ev) => {
                    const f = (ev.target as HTMLInputElement).files?.[0];
                    if (f) onChange(f);
                };
                input.click();
            }}
        >
            {file ? (
                <>
                    {checking ? (
                        <Loader2 size={15} color="var(--blue)" style={{ animation: "spin 1s linear infinite", flexShrink: 0 }} />
                    ) : isInvalid ? (
                        <AlertCircle size={15} color="var(--red, #ef4444)" style={{ flexShrink: 0 }} />
                    ) : (
                        <CheckCircle2 size={15} color="var(--green)" />
                    )}
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: "0.75rem", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</div>
                        <div style={{ fontSize: "0.625rem", color: "var(--text-muted)" }}>
                            {(file.size / 1024).toFixed(0)} KB
                            {checking && <span style={{ color: "var(--blue)", marginLeft: 6 }}>Checking relevance…</span>}
                            {isValid && <span style={{ color: "var(--green)", marginLeft: 6 }}>✓ Verified</span>}
                            {isInvalid && <span style={{ color: "var(--red, #ef4444)", fontWeight: 600, marginLeft: 6 }}>Invalid document</span>}
                        </div>
                    </div>
                    <button
                        onClick={(e) => { e.stopPropagation(); onChange(null); }}
                        style={{ background: "none", border: "none", cursor: "pointer", padding: 2, color: "var(--text-muted)" }}
                    >
                        <X size={13} />
                    </button>
                </>
            ) : (
                <>
                    <Upload size={15} color="var(--text-muted)" />
                    <div style={{ flex: 1 }}>
                        <div style={{ fontSize: "0.75rem", fontWeight: 500 }}>
                            {spec.label}
                            {spec.required && <span style={{ color: "var(--red, #ef4444)", marginLeft: 3 }}>*</span>}
                        </div>
                        <div style={{ fontSize: "0.625rem", color: "var(--text-muted)" }}>{spec.hint}</div>
                    </div>
                </>
            )}
        </div>

        {/* Invalid document banner with resubmit */}
        {isInvalid && validationResult && (
            <div style={{
                display: "flex", gap: 8, alignItems: "flex-start",
                marginTop: 6, padding: "10px 12px",
                background: "rgba(239,68,68,0.07)",
                border: "1px solid rgba(239,68,68,0.35)",
                borderRadius: 6,
            }}>
                <AlertCircle size={14} color="var(--red, #ef4444)" style={{ flexShrink: 0, marginTop: 1 }} />
                <div style={{ flex: 1, fontSize: "0.6875rem", lineHeight: 1.5 }}>
                    <div style={{ fontWeight: 700, color: "var(--red, #ef4444)", marginBottom: 2 }}>Invalid document — not accepted</div>
                    <div style={{ color: "var(--text-primary)", marginBottom: 4 }}>{validationResult.reason}</div>
                    {validationResult.detected_type && validationResult.detected_type !== spec.type && (
                        <div style={{ color: "var(--text-muted)", marginBottom: 6 }}>
                            Detected: <span style={{ fontWeight: 500 }}>{validationResult.detected_type}</span> —
                            expected an insurance document for <span style={{ fontWeight: 500 }}>{spec.label}</span>.
                        </div>
                    )}
                    <button
                        onClick={(e) => { e.stopPropagation(); onResubmit?.(); }}
                        style={{
                            display: "inline-flex", alignItems: "center", gap: 5,
                            padding: "4px 12px", borderRadius: 5, cursor: "pointer",
                            border: "1px solid rgba(239,68,68,0.5)",
                            background: "rgba(239,68,68,0.08)",
                            color: "var(--red, #ef4444)", fontSize: "0.6875rem", fontWeight: 600,
                        }}
                    >
                        <X size={11} /> Remove &amp; Resubmit
                    </button>
                </div>
            </div>
        )}

        {/* Backend OCR validation error (existing logic) */}
        {validationError && !isInvalid && (
            <div style={{
                display: "flex", gap: 8, alignItems: "flex-start",
                marginTop: 6, padding: "8px 10px",
                background: "rgba(245,158,11,0.08)",
                border: "1px solid rgba(245,158,11,0.35)",
                borderRadius: 6,
            }}>
                <AlertTriangle size={13} color="#f59e0b" style={{ flexShrink: 0, marginTop: 1 }} />
                <div style={{ fontSize: "0.6875rem", lineHeight: 1.45 }}>
                    <span style={{ fontWeight: 600, color: "#f59e0b" }}>{spec.label} — document rejected: </span>
                    <span style={{ color: "var(--text-primary)" }}>{validationError}</span>
                    <div style={{ color: "var(--text-muted)", marginTop: 2 }}>Please remove this file and upload the correct document.</div>
                </div>
            </div>
        )}
        </div>
    );
}

// ── Inline OCR result card (shown below FileZone after extraction) ─────────────
function InlineOcrCard({
    result,
    edits,
    onFieldChange,
}: {
    result: InlineOcrResult;
    edits: Record<string, unknown>;
    onFieldChange: (key: string, value: string) => void;
}) {
    const [isEditing, setIsEditing] = useState(false);

    if (!result.is_relevant) return null; // FileZone already shows the invalid banner

    const entries = Object.entries(edits).filter(([, v]) => v !== null && v !== undefined && v !== "");
    const hasMissing = result.missing_fields.length > 0;

    if (entries.length === 0 && !hasMissing) {
        return (
            <div style={{
                marginTop: 4, padding: "8px 12px",
                border: "1px solid rgba(34,197,94,0.2)", borderTop: "none",
                borderRadius: "0 0 6px 6px", background: "var(--bg-surface)",
                fontSize: "0.6875rem", color: "var(--text-muted)",
            }}>
                No fields extracted — you can add them manually after upload.
            </div>
        );
    }

    return (
        <div style={{
            marginTop: 4, padding: "10px 12px",
            border: "1px solid rgba(34,197,94,0.25)", borderTop: "none",
            borderRadius: "0 0 6px 6px", background: "var(--bg-surface)",
        }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontSize: "0.6875rem", color: "var(--green)", fontWeight: 600, display: "flex", gap: 5, alignItems: "center" }}>
                    <CheckCircle2 size={11} />
                    {entries.length} field{entries.length !== 1 ? "s" : ""} extracted
                    {result.completeness > 0 && (
                        <span style={{ color: result.completeness >= 0.7 ? "var(--green)" : "#f59e0b", fontFamily: "var(--font-mono)", marginLeft: 2 }}>
                            · {Math.round(result.completeness * 100)}% complete
                        </span>
                    )}
                </span>
                {entries.length > 0 && (
                    <button
                        type="button"
                        onClick={() => setIsEditing(!isEditing)}
                        style={{
                            display: "flex", gap: 4, alignItems: "center",
                            padding: "2px 8px", borderRadius: 4,
                            border: "1px solid var(--border)", background: "none",
                            cursor: "pointer", fontSize: "0.625rem", color: "var(--text-muted)",
                        }}
                    >
                        {isEditing ? <><X size={10} /> Done</> : <><Edit2 size={10} /> Edit</>}
                    </button>
                )}
            </div>

            {/* Extracted fields */}
            {entries.length > 0 && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 12px" }}>
                    {entries.map(([k, v]) => (
                        <div key={k} style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
                            <span style={{
                                fontSize: "0.625rem", color: "var(--text-muted)", textTransform: "capitalize",
                                flexShrink: 0, width: 90, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                            }}>
                                {k.replace(/_/g, " ")}
                            </span>
                            {isEditing ? (
                                <input
                                    className="input"
                                    value={String(v ?? "")}
                                    onChange={e => onFieldChange(k, e.target.value)}
                                    style={{ flex: 1, fontSize: "0.6875rem", padding: "2px 6px", minWidth: 0 }}
                                />
                            ) : (
                                <span style={{
                                    fontSize: "0.6875rem", color: "var(--text-primary)",
                                    fontFamily: "var(--font-mono)",
                                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                                }}>
                                    {String(v ?? "").slice(0, 40)}
                                </span>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* Missing required fields — always editable inputs */}
            {hasMissing && (
                <div style={{ marginTop: entries.length > 0 ? 10 : 0 }}>
                    <div style={{
                        fontSize: "0.625rem", color: "#f59e0b", fontWeight: 600,
                        display: "flex", gap: 4, alignItems: "center", marginBottom: 6,
                    }}>
                        <AlertTriangle size={10} />
                        Missing required fields — fill in manually:
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 12px" }}>
                        {result.missing_fields.map((k) => (
                            <div key={k} style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
                                <span style={{
                                    fontSize: "0.625rem", color: "#f59e0b", textTransform: "capitalize",
                                    flexShrink: 0, width: 90, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                                }}>
                                    {k.replace(/_/g, " ")}
                                </span>
                                <input
                                    className="input"
                                    placeholder="enter value…"
                                    value={String(edits[k] ?? "")}
                                    onChange={e => onFieldChange(k, e.target.value)}
                                    style={{
                                        flex: 1, fontSize: "0.6875rem", padding: "2px 6px", minWidth: 0,
                                        borderColor: "rgba(245,158,11,0.5)",
                                    }}
                                />
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function NewClaimPage() {
    return (
        <AuthGuard>
            <WizardContent />
        </AuthGuard>
    );
}

function WizardContent() {
    const router = useRouter();
    const [step, setStep] = useState(1);
    const authUser = useAuthStore((s) => s.user);
    const hasHydrated = useAuthStore((s) => s._hasHydrated);
    const userRole = authUser?.role ?? null;

    // Redirect non-customers after hydration
    useEffect(() => {
        if (!hasHydrated) return;
        if (userRole !== null && userRole !== "CUSTOMER") {
            router.push("/claims");
        }
    }, [hasHydrated, userRole, router]);

    // Step 1 — Consent
    const [consentData, setConsentData] = useState(false);       // data processing
    const [consentTerms, setConsentTerms] = useState(false);     // T&C
    const [consentLoading, setConsentLoading] = useState(false);
    const [consentError, setConsentError] = useState<string | null>(null);
    const [consentChecking, setConsentChecking] = useState(false); // always show consent step (not checking)

    // Removed: Auto-skip consent. Now shown every time user files a claim.

    // Policies loaded from DB
    const [myPolicies, setMyPolicies] = useState<Policy[]>([]);
    useEffect(() => {
        policyService.listMine().then((r) => setMyPolicies(r.items)).catch(() => {});
    }, []);

    // Step 2 — policy selection (replaces type picker)
    const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);
    const [docRequirements, setDocRequirements] = useState<DocumentRequirement[]>([]);
    const [reqLoading, setReqLoading] = useState(false);

    // claimType is DERIVED from the selected policy (no longer separately chosen)
    const claimType: ClaimType | null = selectedPolicy
        ? (selectedPolicy.policy_type as ClaimType)
        : null;

    // When a policy is selected, fetch its document requirements
    useEffect(() => {
        if (!selectedPolicy) { setDocRequirements([]); return; }
        setReqLoading(true);
        policyService.getDocumentRequirements(selectedPolicy.id)
            .then((r) => setDocRequirements(r.items))
            .catch(() => setDocRequirements([]))
            .finally(() => setReqLoading(false));
    }, [selectedPolicy?.id]);

    // Step 2
    const [files, setFiles] = useState<Map<number, File>>(new Map()); // keyed by docSpec index
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [docErrors, setDocErrors] = useState<Map<number, string>>(new Map());

    // Step 3 — inline OCR (runs per-doc on file select)
    const [docOcrResults, setDocOcrResults] = useState<Map<number, InlineOcrResult>>(new Map());
    const [processingDocs, setProcessingDocs] = useState<Set<number>>(new Set());
    // User-editable extracted field overrides (keyed by doc-slot index)
    const [docFieldEdits, setDocFieldEdits] = useState<Map<number, Record<string, unknown>>>(new Map());

    // Step 3
    const [claimAmount, setClaimAmount] = useState("");
    const [description, setDescription] = useState("");

    // Speech-to-text
    const [isRecording, setIsRecording] = useState(false);
    const [isTranscribing, setIsTranscribing] = useState(false);
    const [sttError, setSttError] = useState<string | null>(null);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);

    const startRecording = async () => {
        setSttError(null);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mr = new MediaRecorder(stream);
            chunksRef.current = [];
            mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
            mr.onstop = async () => {
                stream.getTracks().forEach((t) => t.stop());
                const blob = new Blob(chunksRef.current, { type: mr.mimeType || "audio/webm" });
                setIsTranscribing(true);
                try {
                    const form = new FormData();
                    form.append("file", blob, "recording.webm");
                    const { data } = await api.post<{ text: string }>("/speech/transcribe", form, {
                        headers: { "Content-Type": "multipart/form-data" },
                    });
                    if (data.text) {
                        setDescription((prev) => prev ? prev + " " + data.text : data.text);
                    }
                } catch {
                    setSttError("Transcription failed — try again");
                } finally {
                    setIsTranscribing(false);
                }
            };
            mediaRecorderRef.current = mr;
            mr.start();
            setIsRecording(true);
        } catch {
            setSttError("Microphone access denied");
        }
    };

    const stopRecording = () => {
        mediaRecorderRef.current?.stop();
        setIsRecording(false);
    };
    const [claimId, setClaimId] = useState<string | null>(null);
    const [resolvedPolicyNumber, setResolvedPolicyNumber] = useState<string | null>(null);
    const [uploadedDocs, setUploadedDocs] = useState<ClaimDocumentResponse[]>([]);

    // Step 4 (Confirm + Submit)
    const [submitting, setSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);
    const [done, setDone] = useState(false);

    // Specs: prefer API-driven requirements; fall back to static DOC_CONFIG
    const specs: DocSpec[] = docRequirements.length > 0
        ? docRequirements.map((req) => ({
            type: req.document_type_code as DocumentType,
            label: req.display_name,
            required: req.is_compulsory,
            hint: req.instructions ?? (req.field_keys.length > 0 ? `Fields: ${req.field_keys.slice(0, 3).join(", ")}` : req.display_name),
            requirement_id: req.id,
            document_type_code: req.document_type_code,
          }))
        : (claimType && DOC_CONFIG[claimType as keyof typeof DOC_CONFIG] ? DOC_CONFIG[claimType as keyof typeof DOC_CONFIG] : []);

    // ── Helpers ───────────────────────────────────────────────────────────────
    function getExtractedAmount(docs: ClaimDocumentResponse[]): string {
        for (const doc of docs) {
            // Try promoted column first
            if (doc.total_amount && doc.total_amount > 0) return String(doc.total_amount);
            if (!doc.extracted_data) continue;
            const d = doc.extracted_data as Record<string, unknown>;
            const candidates = ["total_amount", "claim_amount", "amount", "net_amount", "bill_amount"];
            for (const key of candidates) {
                if (d[key] !== undefined && d[key] !== null) {
                    const raw = d[key];
                    const textVal =
                        typeof raw === "object" && raw !== null
                            ? (raw as Record<string, unknown>).value ?? (raw as Record<string, unknown>).text
                            : raw;
                    const val = parseFloat(String(textVal).replace(/[^0-9.]/g, ""));
                    if (!isNaN(val) && val > 0) return String(val);
                }
            }
        }
        return "";
    }

    // ── Step 1: record consent ────────────────────────────────────────────────
    async function handleGiveConsent() {
        setConsentError(null);
        setConsentLoading(true);
        try {
            await complianceService.giveConsent();
            setStep(2);
        } catch {
            setConsentError("Failed to record consent — please try again.");
        } finally {
            setConsentLoading(false);
        }
    }

    // ── Run inline OCR per doc immediately on file select ────────────────────
    const runInlineOcr = useCallback(async (idx: number, file: File, ct: ClaimType, specList: DocSpec[]) => {
        const spec = specList[idx];
        if (!spec) return;
        setProcessingDocs((prev) => new Set(prev).add(idx));
        try {
            const result = await documentService.inlineOcr(
                file,
                spec.document_type_code ?? spec.type,
                ct,
                spec.requirement_id,
            );
            setDocOcrResults((prev) => new Map(prev).set(idx, result));
            // Seed editable fields from OCR result
            setDocFieldEdits((prev) => new Map(prev).set(idx, { ...result.extracted_fields }));
            // Auto-prefill amount from first document that has a total_amount
            const rawAmt = result.extracted_fields.total_amount;
            if (rawAmt) {
                const val = parseFloat(String(rawAmt).replace(/[^0-9.]/g, ""));
                if (!isNaN(val) && val > 0) setClaimAmount((prev) => prev || String(val));
            }
        } catch {
            // Network error — be lenient, accept for manual review
            const fallback: InlineOcrResult = {
                is_relevant: true,
                reason: "Could not verify automatically — accepted for manual review.",
                detected_type: spec.document_type_code ?? spec.type,
                extracted_fields: {},
                completeness: 0,
                missing_fields: [],
            };
            setDocOcrResults((prev) => new Map(prev).set(idx, fallback));
            setDocFieldEdits((prev) => new Map(prev).set(idx, {}));
        } finally {
            setProcessingDocs((prev) => { const next = new Set(prev); next.delete(idx); return next; });
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    async function handleUpload() {
        if (!claimType) return;
        const missingRequired = specs
            .map((spec, i) => ({ spec, idx: i }))
            .filter(({ spec, idx }) => spec.required && !files.get(idx));
        if (missingRequired.length > 0) {
            setUploadError(`Please upload: ${missingRequired.map(({ spec }) => spec.label).join(", ")}`);
            return;
        }
        setUploadError(null);
        setDocErrors(new Map());
        setUploading(true);
        try {
            // Create claim first
            const claim = await claimService.create({
                claim_type: claimType,
                claim_amount: 1.0,
            });
            setClaimId(claim.id);
            setResolvedPolicyNumber(claim.policy_number);

            // Upload each doc with its pre-extracted data (or raw if OCR failed/skipped)
            const results: ClaimDocumentResponse[] = [];
            const newDocErrors = new Map<number, string>();
            for (const [idx, file] of files.entries()) {
                const spec = specs[idx];
                const precomputed = docFieldEdits.get(idx) ?? docOcrResults.get(idx)?.extracted_fields;
                try {
                    const doc = await documentService.uploadClaimDoc(
                        claim.id,
                        file,
                        spec.document_type_code ?? spec.type,
                        spec.requirement_id,
                        precomputed && Object.keys(precomputed).length > 0 ? precomputed : undefined,
                    );
                    results.push(doc);
                } catch (err) {
                    const axErr = err as { response?: { status?: number; data?: { detail?: string; error_code?: string } } };
                    if (axErr.response?.status === 400) {
                        const reason = axErr.response?.data?.detail ?? "This document appears to be incorrect.";
                        newDocErrors.set(idx, reason);
                    } else {
                        throw err;
                    }
                }
            }

            if (newDocErrors.size > 0) {
                setDocErrors(newDocErrors);
                return;
            }

            setUploadedDocs(results);

            // Pre-fill amount if not already set from inline OCR
            if (!claimAmount) {
                const extracted = getExtractedAmount(results);
                if (extracted) setClaimAmount(extracted);
            }

            setStep(4);
        } catch (err: unknown) {
            const axErr = err as { response?: { data?: { detail?: string } } };
            const msg = axErr.response?.data?.detail ?? (err instanceof Error ? err.message : "Upload failed");
            setUploadError(msg);
        } finally {
            setUploading(false);
        }
    }

    // ── Step 4: patch claim + done ────────────────────────────────────────────
    async function handleSubmit() {
        if (!claimId) return;
        const amount = parseFloat(claimAmount);
        if (isNaN(amount) || amount <= 0) {
            setSubmitError("Enter a valid claim amount");
            return;
        }
        setSubmitError(null);
        setSubmitting(true);
        try {
            await claimService.update(claimId, {
                claim_amount: amount,
                description: description.trim() || undefined,
            });
            setDone(true);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Submission failed";
            setSubmitError(msg);
        } finally {
            setSubmitting(false);
        }
    }

    // ── Success state ─────────────────────────────────────────────────────────
    if (done) {
        return (
            <CommandLayout header={
                <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>New Claim</span>
            }>
                <div style={{ maxWidth: 520, margin: "40px auto", textAlign: "center" }}>
                    <CheckCircle2 size={48} color="var(--green)" style={{ margin: "0 auto 16px" }} />
                    <h2 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: 8 }}>Claim submitted</h2>
                    <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", marginBottom: 24 }}>
                        Your claim has been received and is under review.
                    </p>
                    <button className="btn btn-primary" onClick={() => router.push("/claims")}>
                        View my claims <ArrowRight size={14} />
                    </button>
                </div>
            </CommandLayout>
        );
    }

    // ── Role verification ─────────────────────────────────────────────────────
    if (!hasHydrated) {
        // Store not yet hydrated — show skeleton
        return (
            <CommandLayout header={
                <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>New Claim</span>
            }>
                <div style={{ maxWidth: 520, margin: "40px auto", textAlign: "center", padding: "40px 0" }}>
                    <div className="skeleton" style={{ height: 80, marginBottom: 20 }} />
                </div>
            </CommandLayout>
        );
    }

    if (userRole !== "CUSTOMER") {
        // Non-customers cannot file claims — useEffect above also redirects
        return (
            <CommandLayout header={
                <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>New Claim</span>
            }>
                <div style={{ maxWidth: 520, margin: "40px auto", textAlign: "center" }}>
                    <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                        Only customers can file new claims. Admins manage existing claims through the dashboard.
                    </p>
                    <button className="btn btn-primary" onClick={() => router.push("/claims")} style={{ marginTop: 20 }}>
                        Back to claims <ArrowRight size={14} />
                    </button>
                </div>
            </CommandLayout>
        );
    }

    // ── Wizard layout ─────────────────────────────────────────────────────────
    return (
        <CommandLayout header={
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <FileText size={15} color="var(--text-muted)" />
                <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>New Claim</span>
                <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>Step {step} of 4</span>
            </div>
        }>
            <div style={{ maxWidth: 600, margin: "0 auto", padding: "24px 0" }}>
                <StepBar current={step} />

                {/* ── Step 1: Consent ─────────────────────────────────────── */}
                {step === 1 && !consentChecking && (
                    <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                            <Shield size={20} color="var(--blue)" />
                            <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Data consent &amp; conditions</h2>
                        </div>
                        <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", lineHeight: 1.6, marginBottom: 20 }}>
                            Before filing a claim, please read and accept how InsureFlow&nbsp;AI handles your personal
                            and medical information.
                        </p>

                        {/* Info box */}
                        <div style={{
                            border: "1px solid var(--border)", borderRadius: 8,
                            padding: "14px 16px", background: "var(--bg-surface)", marginBottom: 20,
                            fontSize: "0.8125rem", lineHeight: 1.7,
                        }}>
                            <p style={{ fontWeight: 600, marginBottom: 8 }}>What data we collect &amp; why</p>
                            <ul style={{ paddingLeft: 18, color: "var(--text-muted)", margin: 0 }}>
                                <li>Personal identifiers (name, ID proof) — to verify your identity</li>
                                <li>Medical &amp; vehicle documents — to assess and process your claim</li>
                                <li>Policy details — to validate coverage eligibility</li>
                                <li>Device / IP information — for fraud prevention</li>
                            </ul>
                            <p style={{ marginTop: 10, color: "var(--text-muted)" }}>
                                Data is retained for the duration required by insurance regulations and deleted upon
                                a valid account-deletion request. We never sell your data to third parties.
                            </p>
                        </div>

                        {/* Checkboxes */}
                        <label style={{
                            display: "flex", alignItems: "flex-start", gap: 10,
                            marginBottom: 14, cursor: "pointer", fontSize: "0.8125rem",
                        }}>
                            <input
                                type="checkbox"
                                checked={consentData}
                                onChange={(e) => setConsentData(e.target.checked)}
                                style={{ marginTop: 2, accentColor: "var(--blue)", width: 15, height: 15, flexShrink: 0 }}
                            />
                            <span>
                                I consent to InsureFlow&nbsp;AI collecting, storing, and processing my personal,
                                medical, and vehicle data solely for the purpose of evaluating and settling this
                                insurance claim.
                            </span>
                        </label>

                        <label style={{
                            display: "flex", alignItems: "flex-start", gap: 10,
                            marginBottom: 24, cursor: "pointer", fontSize: "0.8125rem",
                        }}>
                            <input
                                type="checkbox"
                                checked={consentTerms}
                                onChange={(e) => setConsentTerms(e.target.checked)}
                                style={{ marginTop: 2, accentColor: "var(--blue)", width: 15, height: 15, flexShrink: 0 }}
                            />
                            <span>
                                I have read and agree to the{" "}
                                <a
                                    href="/terms"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ color: "var(--blue)", textDecoration: "underline" }}
                                >
                                    Terms &amp; Conditions
                                </a>
                                {" "}and{" "}
                                <a
                                    href="/privacy"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ color: "var(--blue)", textDecoration: "underline" }}
                                >
                                    Privacy Policy
                                </a>
                                , including collection and processing of my health and financial data for claim evaluation.
                            </span>
                        </label>

                        {consentError && (
                            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--red, #ef4444)", fontSize: "0.75rem", marginBottom: 12 }}>
                                <AlertCircle size={13} />
                                {consentError}
                            </div>
                        )}

                        <button
                            className="btn btn-primary"
                            disabled={!consentData || !consentTerms || consentLoading}
                            onClick={handleGiveConsent}
                            style={{ width: "100%" }}
                        >
                            {consentLoading ? (
                                <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Recording consent…</>
                            ) : (
                                <>Accept &amp; Continue <ChevronRight size={14} /></>
                            )}
                        </button>
                    </div>
                )}

                {/* ── Step 2: Select policy ────────────────────────────────── */}
                {step === 2 && (
                    <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                            <Building2 size={18} color="var(--blue)" />
                            <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Choose a policy to claim</h2>
                        </div>
                        <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", marginBottom: 20 }}>
                            Select the policy you&apos;d like to file a claim against. Required documents will be shown automatically.
                        </p>

                        {myPolicies.length === 0 ? (
                            <div style={{
                                border: "1px solid var(--border)", borderRadius: 8, padding: "24px",
                                textAlign: "center", color: "var(--text-muted)", fontSize: "0.875rem",
                                background: "var(--bg-surface)",
                            }}>
                                No policies found. Please contact your insurer.
                            </div>
                        ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 20 }}>
                                {myPolicies.filter(p => p.status === "ACTIVE").map((pol) => {
                                    const selected = selectedPolicy?.id === pol.id;
                                    const typeColor = pol.policy_type === "HEALTH" ? "var(--green)"
                                        : pol.policy_type === "MOTOR" ? "var(--blue)"
                                        : "var(--amber)";
                                    return (
                                        <button
                                            key={pol.id}
                                            onClick={() => setSelectedPolicy(selected ? null : pol)}
                                            style={{
                                                border: `1px solid ${selected ? typeColor : "var(--border)"}`,
                                                borderRadius: 8,
                                                padding: "14px 16px",
                                                background: selected ? `${typeColor}12` : "var(--bg-surface)",
                                                cursor: "pointer",
                                                textAlign: "left",
                                                transition: "all 150ms",
                                                width: "100%",
                                            }}
                                        >
                                            <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: "space-between" }}>
                                                <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
                                                    {selected && <CheckCircle2 size={15} color={typeColor} style={{ flexShrink: 0 }} />}
                                                    <div style={{ minWidth: 0 }}>
                                                        <div style={{ fontWeight: 600, fontSize: "0.875rem", display: "flex", alignItems: "center", gap: 8 }}>
                                                            {pol.policy_number}
                                                            <span style={{
                                                                fontSize: "0.625rem", fontWeight: 600, padding: "2px 7px",
                                                                borderRadius: 99, background: `${typeColor}22`, color: typeColor,
                                                            }}>
                                                                {pol.policy_type}
                                                            </span>
                                                        </div>
                                                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                                                            {pol.insured_name ?? "—"} · Sum insured: ₹{Number(pol.sum_insured).toLocaleString("en-IN")}
                                                        </div>
                                                        <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", marginTop: 1 }}>
                                                            Valid: {pol.start_date} → {pol.end_date}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        )}

                        {/* Requirement loading */}
                        {reqLoading && selectedPolicy && (
                            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 12 }}>
                                <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />
                                Loading document requirements…
                            </div>
                        )}

                        {/* Show required docs preview when policy selected */}
                        {selectedPolicy && !reqLoading && docRequirements.length > 0 && (
                            <div style={{
                                border: "1px solid var(--border)", borderRadius: 8, padding: "12px 14px",
                                background: "var(--bg-surface)", marginBottom: 16,
                            }}>
                                <div style={{ fontSize: "0.75rem", fontWeight: 600, marginBottom: 8, color: "var(--text-muted)" }}>
                                    Required documents ({docRequirements.filter(r => r.is_compulsory).length} mandatory)
                                </div>
                                <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                                    {docRequirements.map((req) => (
                                        <div key={req.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.75rem" }}>
                                            <span style={{
                                                width: 6, height: 6, borderRadius: "50%", flexShrink: 0,
                                                background: req.is_compulsory ? "var(--red, #ef4444)" : "var(--text-muted)",
                                            }} />
                                            <span style={{ color: req.is_compulsory ? "var(--text-primary)" : "var(--text-muted)" }}>
                                                {req.display_name}
                                                {req.is_compulsory && <span style={{ color: "var(--red, #ef4444)", marginLeft: 3 }}>*</span>}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {selectedPolicy && !reqLoading && docRequirements.length === 0 && (
                            <div style={{
                                border: "1px solid rgba(245,158,11,0.35)", borderRadius: 6, padding: "10px 12px",
                                background: "rgba(245,158,11,0.06)", fontSize: "0.75rem", color: "#f59e0b",
                                marginBottom: 14,
                            }}>
                                No template-driven requirements found for this policy type. You&apos;ll be able to upload any relevant documents in the next step.
                            </div>
                        )}

                        <button
                            className="btn btn-primary"
                            disabled={!selectedPolicy || reqLoading}
                            onClick={() => setStep(3)}
                            style={{ width: "100%" }}
                        >
                            {reqLoading ? (
                                <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Loading requirements…</>
                            ) : (
                                <>Continue to Documents <ChevronRight size={14} /></>
                            )}
                        </button>
                    </div>
                )}

                {/* ── Step 3: Documents + inline OCR ──────────────────────── */}
                {step === 3 && claimType && (() => {
                    const allRequiredHaveFiles = specs.every((spec, idx) => !spec.required || files.has(idx));
                    const anyProcessing = processingDocs.size > 0;
                    const hasInvalidDocs = [...docOcrResults.values()].some(r => !r.is_relevant);
                    const canUpload = allRequiredHaveFiles && !anyProcessing && !hasInvalidDocs;
                    return (
                        <div>
                            <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 6 }}>
                                {TYPE_META[claimType as keyof typeof TYPE_META]?.title ?? claimType} — Documents
                            </h2>
                            <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", marginBottom: 20 }}>
                                Upload supporting documents. Each file is immediately extracted and verified by AI — you can review and edit the data before saving.
                            </p>

                            <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 20 }}>
                                {specs.map((spec, idx) => {
                                    const ocrResult = docOcrResults.get(idx) ?? null;
                                    const isProcessing = processingDocs.has(idx);
                                    const validationResult = ocrResult
                                        ? { valid: ocrResult.is_relevant, reason: ocrResult.reason, detected_type: ocrResult.detected_type }
                                        : null;
                                    return (
                                        <div key={idx} style={{ marginBottom: 8 }}>
                                            <FileZone
                                                spec={spec}
                                                file={files.get(idx)}
                                                validationError={docErrors.get(idx) ?? null}
                                                validationResult={validationResult}
                                                checking={isProcessing}
                                                onResubmit={() => {
                                                    setFiles(prev => { const n = new Map(prev); n.delete(idx); return n; });
                                                    setDocOcrResults(prev => { const n = new Map(prev); n.delete(idx); return n; });
                                                    setDocFieldEdits(prev => { const n = new Map(prev); n.delete(idx); return n; });
                                                    setDocErrors(prev => { const n = new Map(prev); n.delete(idx); return n; });
                                                }}
                                                onChange={(f) => {
                                                    setFiles(prev => { const n = new Map(prev); if (f) n.set(idx, f); else n.delete(idx); return n; });
                                                    setDocErrors(prev => { const n = new Map(prev); n.delete(idx); return n; });
                                                    setDocOcrResults(prev => { const n = new Map(prev); n.delete(idx); return n; });
                                                    setDocFieldEdits(prev => { const n = new Map(prev); n.delete(idx); return n; });
                                                    if (f && claimType) runInlineOcr(idx, f, claimType, specs);
                                                }}
                                            />
                                            {/* Spinner while OCR runs */}
                                            {isProcessing && (
                                                <div style={{
                                                    marginTop: 4, padding: "10px 12px",
                                                    border: "1px solid var(--border)", borderTop: "none",
                                                    borderRadius: "0 0 6px 6px", background: "var(--bg-surface)",
                                                }}>
                                                    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.6875rem", color: "var(--blue)", marginBottom: 8 }}>
                                                        <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />
                                                        Extracting fields with AI…
                                                    </div>
                                                    {[70, 50, 80].map((w, i) => (
                                                        <div key={i} className="skeleton" style={{ height: 9, width: `${w}%`, marginBottom: 5 }} />
                                                    ))}
                                                </div>
                                            )}
                                            {/* Inline OCR result card — editable */}
                                            {!isProcessing && ocrResult && (
                                                <InlineOcrCard
                                                    result={ocrResult}
                                                    edits={docFieldEdits.get(idx) ?? ocrResult.extracted_fields}
                                                    onFieldChange={(k, v) => setDocFieldEdits(prev =>
                                                        new Map(prev).set(idx, { ...(prev.get(idx) ?? ocrResult.extracted_fields), [k]: v })
                                                    )}
                                                />
                                            )}
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Summary banners */}
                            {hasInvalidDocs && (
                                <div style={{
                                    display: "flex", gap: 8, alignItems: "center",
                                    padding: "10px 12px", borderRadius: 6, marginBottom: 12,
                                    background: "rgba(239,68,68,0.07)", border: "1px solid rgba(239,68,68,0.4)",
                                    fontSize: "0.75rem", color: "var(--red, #ef4444)", fontWeight: 500,
                                }}>
                                    <AlertCircle size={14} />
                                    {[...docOcrResults.values()].filter(r => !r.is_relevant).length === 1
                                        ? "1 document is invalid"
                                        : `${[...docOcrResults.values()].filter(r => !r.is_relevant).length} documents are invalid`
                                    } — remove the flagged files and upload the correct insurance documents.
                                </div>
                            )}
                            {anyProcessing && (
                                <div style={{
                                    display: "flex", gap: 8, alignItems: "center",
                                    padding: "10px 12px", borderRadius: 6, marginBottom: 12,
                                    background: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.3)",
                                    fontSize: "0.75rem", color: "var(--blue)", fontWeight: 500,
                                }}>
                                    <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />
                                    AI is extracting data from your documents…
                                </div>
                            )}
                            {!anyProcessing && canUpload && files.size > 0 && (
                                <div style={{
                                    display: "flex", gap: 8, alignItems: "center",
                                    padding: "10px 12px", borderRadius: 6, marginBottom: 12,
                                    background: "rgba(34,197,94,0.07)", border: "1px solid rgba(34,197,94,0.35)",
                                    fontSize: "0.75rem", color: "var(--green)", fontWeight: 500,
                                }}>
                                    <CheckCircle2 size={14} />
                                    All documents ready — review the extracted data above, then click Save &amp; Continue.
                                </div>
                            )}
                            {docErrors.size > 0 && (
                                <div style={{
                                    display: "flex", gap: 8, alignItems: "center",
                                    padding: "8px 12px", borderRadius: 6, marginBottom: 12,
                                    background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.35)",
                                    fontSize: "0.75rem", color: "#f59e0b", fontWeight: 500,
                                }}>
                                    <AlertTriangle size={14} />
                                    {docErrors.size === 1 ? "1 document" : `${docErrors.size} documents`} failed server validation — see details above.
                                </div>
                            )}
                            {uploadError && (
                                <div style={{ color: "var(--red, #ef4444)", fontSize: "0.75rem", marginBottom: 12 }}>
                                    {uploadError}
                                </div>
                            )}

                            <div style={{ display: "flex", gap: 8 }}>
                                <button className="btn btn-ghost" onClick={() => setStep(2)}>
                                    <ChevronLeft size={14} /> Back
                                </button>
                                {anyProcessing && (
                                    <button className="btn btn-primary" disabled style={{ flex: 1 }}>
                                        <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Extracting…
                                    </button>
                                )}
                                {!anyProcessing && hasInvalidDocs && (
                                    <button className="btn btn-primary" disabled style={{ flex: 1, opacity: 0.5 }}>
                                        Fix invalid documents first <AlertCircle size={14} />
                                    </button>
                                )}
                                {!anyProcessing && !hasInvalidDocs && (
                                    <button
                                        className="btn btn-primary"
                                        disabled={uploading || !allRequiredHaveFiles}
                                        onClick={handleUpload}
                                        style={{ flex: 1 }}
                                        title={!allRequiredHaveFiles ? "Upload all required documents first" : undefined}
                                    >
                                        {uploading ? (
                                            <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Uploading…</>
                                        ) : (
                                            <>Save &amp; Continue <ChevronRight size={14} /></>
                                        )}
                                    </button>
                                )}
                            </div>
                        </div>
                    );
                })()}

                {/* ── Step 4: Confirm + submit ─────────────────────────────── */}
                {step === 4 && claimType && (
                    <div>
                        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 6 }}>Confirm your claim</h2>
                        <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", marginBottom: 20 }}>
                            Review the details below before submitting.
                        </p>

                        {/* Amount + description — pre-filled from inline OCR, editable here */}
                        <div style={{ marginBottom: 14 }}>
                            <label style={{ fontSize: "0.75rem", fontWeight: 500, display: "block", marginBottom: 4 }}>
                                Claim Amount (₹) <span style={{ color: "var(--red, #ef4444)" }}>*</span>
                            </label>
                            <input
                                className="input"
                                type="number"
                                min="1"
                                value={claimAmount}
                                onChange={(e) => setClaimAmount(e.target.value)}
                                placeholder="Enter amount"
                                style={{ width: "100%", boxSizing: "border-box" }}
                            />
                        </div>
                        <div style={{ marginBottom: 20 }}>
                            <label style={{ fontSize: "0.75rem", fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                                <span>Description</span>
                                <button
                                    type="button"
                                    title={isRecording ? "Stop recording" : "Dictate description"}
                                    onClick={isRecording ? stopRecording : startRecording}
                                    disabled={isTranscribing}
                                    style={{
                                        display: "flex", alignItems: "center", gap: 5,
                                        padding: "3px 10px", borderRadius: 20,
                                        border: `1px solid ${isRecording ? "var(--red, #ef4444)" : "var(--border)"}`,
                                        background: isRecording ? "rgba(239,68,68,0.08)" : "var(--bg-surface)",
                                        color: isRecording ? "var(--red, #ef4444)" : "var(--text-muted)",
                                        cursor: isTranscribing ? "wait" : "pointer",
                                        fontSize: "0.6875rem", fontWeight: 500,
                                        transition: "all 150ms",
                                    }}
                                >
                                    {isTranscribing ? (
                                        <><Loader size={12} className="spin" /> Transcribing…</>
                                    ) : isRecording ? (
                                        <><MicOff size={12} /> Stop</>
                                    ) : (
                                        <><Mic size={12} /> Dictate</>
                                    )}
                                </button>
                            </label>
                            {isRecording && (
                                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6, fontSize: "0.6875rem", color: "var(--red, #ef4444)" }}>
                                    <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--red, #ef4444)", display: "inline-block", animation: "pulse 1s infinite" }} />
                                    Recording… click Stop when done
                                </div>
                            )}
                            {sttError && (
                                <div style={{ fontSize: "0.6875rem", color: "var(--red, #ef4444)", marginBottom: 4 }}>{sttError}</div>
                            )}
                            <textarea
                                className="input"
                                rows={3}
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder={isRecording ? "Listening…" : "Brief description of the claim… or click Dictate to speak"}
                                style={{ width: "100%", boxSizing: "border-box", resize: "vertical", fontFamily: "inherit" }}
                            />
                        </div>

                        <div style={{
                            border: "1px solid var(--border)", borderRadius: 8,
                            overflow: "hidden", marginBottom: 20,
                        }}>
                            {[
                                { label: "Claim type", value: (claimType && TYPE_META[claimType as keyof typeof TYPE_META]?.title) ?? claimType ?? "—" },
                                { label: "Policy", value: selectedPolicy ? `${selectedPolicy.policy_number}${selectedPolicy.insured_name ? ` — ${selectedPolicy.insured_name}` : ""}` : resolvedPolicyNumber ?? "Auto-resolved" },
                                { label: "Claim amount", value: `₹${Number(claimAmount).toLocaleString("en-IN")}` },
                                { label: "Documents", value: `${uploadedDocs.length} uploaded` },
                                { label: "Description", value: description || "—" },
                            ].map(({ label, value }, i) => (
                                <div key={label} style={{
                                    display: "flex", gap: 12, padding: "10px 14px",
                                    borderBottom: i < 4 ? "1px solid var(--border)" : undefined,
                                    background: i % 2 === 0 ? "var(--bg-surface)" : "transparent",
                                }}>
                                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", minWidth: 110 }}>{label}</span>
                                    <span style={{ fontSize: "0.75rem", fontWeight: 500 }}>{value}</span>
                                </div>
                            ))}
                        </div>

                        {submitError && (
                            <div style={{ color: "var(--red, #ef4444)", fontSize: "0.75rem", marginBottom: 12 }}>
                                {submitError}
                            </div>
                        )}

                        <div style={{ display: "flex", gap: 8 }}>
                            <button className="btn btn-ghost" onClick={() => setStep(3)}>
                                <ChevronLeft size={14} /> Back
                            </button>
                            <button
                                className="btn btn-primary"
                                disabled={submitting}
                                onClick={handleSubmit}
                                style={{ flex: 1 }}
                            >
                                {submitting ? (
                                    <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Submitting…</>
                                ) : (
                                    <>Submit Claim <CheckCircle2 size={14} /></>
                                )}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </CommandLayout>
    );
}

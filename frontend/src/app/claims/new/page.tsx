"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { claimService } from "@/services/claimService";
import { documentService } from "@/services/documentService";
import type { ClaimType, DocumentResponse, DocumentType } from "@/types";
import {
    Heart, Car, ReceiptText, Upload, X, CheckCircle2,
    ChevronRight, ChevronLeft, ArrowRight, Loader2, FileText,
} from "lucide-react";

// ── Document config per claim type ────────────────────────────────────────────
interface DocSpec {
    type: DocumentType;
    label: string;
    required: boolean;
    hint: string;
}

const DOC_CONFIG: Record<ClaimType, DocSpec[]> = {
    HEALTH: [
        { type: "DISCHARGE_SUMMARY", label: "Discharge Summary", required: true, hint: "Hospital discharge letter" },
        { type: "INVOICE", label: "Policy Document", required: true, hint: "Insurance policy PDF" },
        { type: "OTHER", label: "ID Proof", required: true, hint: "Aadhaar / PAN / Passport" },
        { type: "MEDICAL_REPORT", label: "Medical Report", required: false, hint: "Diagnostic reports" },
        { type: "PRESCRIPTION", label: "Prescription", required: false, hint: "Doctor prescriptions" },
    ],
    MOTOR: [
        { type: "OTHER", label: "Policy Document", required: true, hint: "Vehicle insurance policy" },
        { type: "VEHICLE_RC", label: "Vehicle RC", required: true, hint: "Registration certificate" },
        { type: "OTHER", label: "Driving Licence", required: true, hint: "Valid driving licence" },
        { type: "POLICE_REPORT", label: "FIR / Police Report", required: false, hint: "If applicable" },
        { type: "ESTIMATE", label: "Repair Estimate", required: false, hint: "Workshop estimate" },
    ],
    REIMBURSEMENT: [
        { type: "INVOICE", label: "Original Bills", required: true, hint: "Hospital / pharmacy bills" },
        { type: "INVOICE", label: "Policy Document", required: true, hint: "Insurance policy PDF" },
        { type: "OTHER", label: "ID Proof", required: true, hint: "Aadhaar / PAN / Passport" },
        { type: "PRESCRIPTION", label: "Prescription", required: false, hint: "Doctor prescription" },
        { type: "OTHER", label: "Payment Receipts", required: false, hint: "Proof of payment" },
    ],
};

// ── Step indicator ────────────────────────────────────────────────────────────
function StepBar({ current }: { current: number }) {
    const steps = ["Type", "Documents", "Review", "Confirm"];
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
    spec, file, onChange,
}: { spec: DocSpec; file: File | undefined; onChange: (f: File | null) => void }) {
    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        const dropped = e.dataTransfer.files[0];
        if (dropped) onChange(dropped);
    }, [onChange]);

    return (
        <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            style={{
                border: `1px dashed ${file ? "var(--green)" : "var(--border)"}`,
                borderRadius: 6,
                padding: "12px 14px",
                background: file ? "var(--green-bg, rgba(34,197,94,0.06))" : "var(--bg-surface)",
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
                    <CheckCircle2 size={15} color="var(--green)" />
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: "0.75rem", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</div>
                        <div style={{ fontSize: "0.625rem", color: "var(--text-muted)" }}>{(file.size / 1024).toFixed(0)} KB</div>
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

    // Step 1
    const [claimType, setClaimType] = useState<ClaimType | null>(null);

    // Step 2
    const [policyNumber, setPolicyNumber] = useState("");
    const [files, setFiles] = useState<Map<number, File>>(new Map()); // keyed by docSpec index
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);

    // Step 3
    const [claimId, setClaimId] = useState<string | null>(null);
    const [uploadedDocs, setUploadedDocs] = useState<DocumentResponse[]>([]);
    const [claimAmount, setClaimAmount] = useState("");
    const [description, setDescription] = useState("");

    // Step 4
    const [submitting, setSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);
    const [done, setDone] = useState(false);

    const specs = claimType ? DOC_CONFIG[claimType] : [];

    // ── Helpers ───────────────────────────────────────────────────────────────
    function getExtractedAmount(docs: DocumentResponse[]): string {
        for (const doc of docs) {
            if (!doc.extracted_data) continue;
            const d = doc.extracted_data as Record<string, unknown>;
            const candidates = ["total_amount", "claim_amount", "amount", "net_amount", "bill_amount"];
            for (const key of candidates) {
                if (d[key] !== undefined && d[key] !== null) {
                    const val = parseFloat(String(d[key]).replace(/[^0-9.]/g, ""));
                    if (!isNaN(val) && val > 0) return String(val);
                }
            }
        }
        return "";
    }

    // ── Step 2 → 3: create claim + upload docs ────────────────────────────────
    async function handleUpload() {
        if (!claimType) return;
        const missingRequired = specs
            .map((spec, i) => ({ spec, idx: i }))
            .filter(({ spec, idx }) => spec.required && !files.get(idx));
        if (missingRequired.length > 0) {
            setUploadError(`Please upload: ${missingRequired.map(({ spec }) => spec.label).join(", ")}`);
            return;
        }
        if (!policyNumber.trim()) {
            setUploadError("Policy number is required");
            return;
        }
        setUploadError(null);
        setUploading(true);
        try {
            // Create placeholder claim
            const claim = await claimService.create({
                policy_number: policyNumber.trim(),
                claim_type: claimType,
                claim_amount: 1.0,
            });
            setClaimId(claim.id);

            // Upload documents
            const results: DocumentResponse[] = [];
            for (const [idx, file] of files.entries()) {
                const spec = specs[idx];
                const doc = await documentService.upload(claim.id, file, spec.type);
                results.push(doc);
            }
            setUploadedDocs(results);

            // Pre-fill amount from OCR
            const extracted = getExtractedAmount(results);
            if (extracted) setClaimAmount(extracted);

            setStep(3);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Upload failed";
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

                {/* ── Step 1: Choose type ─────────────────────────────────── */}
                {step === 1 && (
                    <div>
                        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 6 }}>What type of claim?</h2>
                        <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", marginBottom: 20 }}>
                            Choose the category that best describes your claim.
                        </p>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 24 }}>
                            {(["HEALTH", "MOTOR", "REIMBURSEMENT"] as ClaimType[]).map((t) => {
                                const meta = TYPE_META[t];
                                const selected = claimType === t;
                                return (
                                    <button
                                        key={t}
                                        onClick={() => setClaimType(t)}
                                        style={{
                                            border: `1px solid ${selected ? meta.color : "var(--border)"}`,
                                            borderRadius: 8,
                                            padding: "18px 14px",
                                            background: selected ? `${meta.color}18` : "var(--bg-surface)",
                                            cursor: "pointer",
                                            textAlign: "left",
                                            transition: "all 150ms",
                                        }}
                                    >
                                        <div style={{ color: meta.color, marginBottom: 8 }}>{meta.icon}</div>
                                        <div style={{ fontWeight: 600, fontSize: "0.875rem", marginBottom: 4 }}>{meta.title}</div>
                                        <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", lineHeight: 1.4 }}>{meta.desc}</div>
                                    </button>
                                );
                            })}
                        </div>
                        <button
                            className="btn btn-primary"
                            disabled={!claimType}
                            onClick={() => setStep(2)}
                            style={{ width: "100%" }}
                        >
                            Continue <ChevronRight size={14} />
                        </button>
                    </div>
                )}

                {/* ── Step 2: Policy + documents ──────────────────────────── */}
                {step === 2 && claimType && (
                    <div>
                        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 6 }}>
                            {TYPE_META[claimType].title} Claim — Documents
                        </h2>
                        <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", marginBottom: 20 }}>
                            Upload supporting documents. Required fields are marked with *.
                        </p>

                        {/* Policy number */}
                        <div style={{ marginBottom: 16 }}>
                            <label style={{ fontSize: "0.75rem", fontWeight: 500, display: "block", marginBottom: 4 }}>
                                Policy Number <span style={{ color: "var(--red, #ef4444)" }}>*</span>
                            </label>
                            <input
                                className="input"
                                value={policyNumber}
                                onChange={(e) => setPolicyNumber(e.target.value)}
                                placeholder="e.g. POL-2024-001"
                                style={{ width: "100%", boxSizing: "border-box" }}
                            />
                        </div>

                        {/* File upload areas */}
                        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
                            {specs.map((spec, idx) => (
                                <FileZone
                                    key={idx}
                                    spec={spec}
                                    file={files.get(idx)}
                                    onChange={(f) => {
                                        setFiles((prev) => {
                                            const next = new Map(prev);
                                            if (f) next.set(idx, f); else next.delete(idx);
                                            return next;
                                        });
                                    }}
                                />
                            ))}
                        </div>

                        {uploadError && (
                            <div style={{ color: "var(--red, #ef4444)", fontSize: "0.75rem", marginBottom: 12 }}>
                                {uploadError}
                            </div>
                        )}

                        <div style={{ display: "flex", gap: 8 }}>
                            <button className="btn btn-ghost" onClick={() => setStep(1)}>
                                <ChevronLeft size={14} /> Back
                            </button>
                            <button
                                className="btn btn-primary"
                                disabled={uploading}
                                onClick={handleUpload}
                                style={{ flex: 1 }}
                            >
                                {uploading ? (
                                    <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Uploading…</>
                                ) : (
                                    <>Upload & Continue <ChevronRight size={14} /></>
                                )}
                            </button>
                        </div>
                    </div>
                )}

                {/* ── Step 3: OCR review ──────────────────────────────────── */}
                {step === 3 && (
                    <div>
                        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 6 }}>Review extracted data</h2>
                        <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", marginBottom: 20 }}>
                            Documents processed. Verify or correct the details below.
                        </p>

                        {/* OCR extractions */}
                        {uploadedDocs.length > 0 && (
                            <div style={{ marginBottom: 20 }}>
                                {uploadedDocs.map((doc) => (
                                    <div key={doc.id} style={{
                                        border: "1px solid var(--border)", borderRadius: 6,
                                        padding: "10px 14px", marginBottom: 8, background: "var(--bg-surface)",
                                    }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                                            <FileText size={13} color="var(--text-muted)" />
                                            <span style={{ fontSize: "0.75rem", fontWeight: 500 }}>{doc.original_filename ?? doc.document_type}</span>
                                            {doc.extraction_confidence !== null && (
                                                <span style={{
                                                    marginLeft: "auto", fontSize: "0.625rem",
                                                    color: (doc.extraction_confidence ?? 0) >= 0.7 ? "var(--green)" : "var(--amber)",
                                                    fontFamily: "var(--font-mono)",
                                                }}>
                                                    {Math.round((doc.extraction_confidence ?? 0) * 100)}% confidence
                                                </span>
                                            )}
                                        </div>
                                        {doc.extracted_data && Object.keys(doc.extracted_data).length > 0 ? (
                                            <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: "2px 12px" }}>
                                                {Object.entries(doc.extracted_data).slice(0, 8).map(([k, v]) => (
                                                    <div key={k} style={{ fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                                                        <span style={{ textTransform: "capitalize" }}>{k.replace(/_/g, " ")}</span>:{" "}
                                                        <span style={{ color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                                                            {String(v).slice(0, 40)}
                                                        </span>
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)" }}>No structured data extracted</span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Amount + description */}
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
                            <label style={{ fontSize: "0.75rem", fontWeight: 500, display: "block", marginBottom: 4 }}>
                                Description
                            </label>
                            <textarea
                                className="input"
                                rows={3}
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder="Brief description of the claim…"
                                style={{ width: "100%", boxSizing: "border-box", resize: "vertical", fontFamily: "inherit" }}
                            />
                        </div>

                        <div style={{ display: "flex", gap: 8 }}>
                            <button className="btn btn-ghost" onClick={() => setStep(2)}>
                                <ChevronLeft size={14} /> Back
                            </button>
                            <button
                                className="btn btn-primary"
                                disabled={!claimAmount}
                                onClick={() => setStep(4)}
                                style={{ flex: 1 }}
                            >
                                Review & Confirm <ChevronRight size={14} />
                            </button>
                        </div>
                    </div>
                )}

                {/* ── Step 4: Confirm ─────────────────────────────────────── */}
                {step === 4 && claimType && (
                    <div>
                        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 6 }}>Confirm your claim</h2>
                        <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", marginBottom: 20 }}>
                            Review the details below before submitting.
                        </p>

                        <div style={{
                            border: "1px solid var(--border)", borderRadius: 8,
                            overflow: "hidden", marginBottom: 20,
                        }}>
                            {[
                                { label: "Claim type", value: TYPE_META[claimType].title },
                                { label: "Policy number", value: policyNumber },
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

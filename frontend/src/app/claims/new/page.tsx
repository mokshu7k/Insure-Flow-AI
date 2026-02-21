"use client";
import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { claimService } from "@/services/claimService";
import { documentService } from "@/services/documentService";
import { complianceService } from "@/services/complianceService";
import api from "@/services/api";
import { EditableExtractedData } from "@/components/ui/EditableExtractedData";
import type { ClaimType, DocumentResponse, DocumentType } from "@/types";
import {
    Heart, Car, ReceiptText, Upload, X, CheckCircle2,
    ChevronRight, ChevronLeft, ArrowRight, Loader2, FileText, Mic, MicOff, Loader,
    Shield, AlertCircle,
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
    const steps = ["Consent", "Type", "Documents", "Review", "Confirm"];
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

    // Step 1 — Consent
    const [consentData, setConsentData] = useState(false);       // data processing
    const [consentTerms, setConsentTerms] = useState(false);     // T&C
    const [consentLoading, setConsentLoading] = useState(false);
    const [consentError, setConsentError] = useState<string | null>(null);
    const [consentChecking, setConsentChecking] = useState(false); // always show consent step (not checking)

    // Removed: Auto-skip consent. Now shown every time user files a claim.

    // Step 2
    const [claimType, setClaimType] = useState<ClaimType | null>(null);

    // Step 2
    const [policyNumber, setPolicyNumber] = useState("");
    const [files, setFiles] = useState<Map<number, File>>(new Map()); // keyed by docSpec index
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);

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
    const [uploadedDocs, setUploadedDocs] = useState<DocumentResponse[]>([]);
    const [extracting, setExtracting] = useState(false); // true while background tasks are pending

    // ── Polling for background Gemini extraction on the wizard ────────────────
    const wizardPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const stopWizardPoll = useCallback(() => {
        if (wizardPollRef.current) { clearInterval(wizardPollRef.current); wizardPollRef.current = null; }
    }, []);

    useEffect(() => {
        // Start polling when we hit step 4 and any doc is still pending
        if (step !== 4 || !claimId) return;
        const hasPending = uploadedDocs.some((d) => d.validation_status === "pending");
        if (!hasPending) { setExtracting(false); return; }

        setExtracting(true);
        if (wizardPollRef.current) return; // already running

        wizardPollRef.current = setInterval(async () => {
            try {
                const refreshed = await documentService.listForClaim(claimId);
                setUploadedDocs(refreshed);
                const stillPending = refreshed.some((d) => d.validation_status === "pending");
                if (!stillPending) {
                    setExtracting(false);
                    stopWizardPoll();
                    // Pre-fill amount now that extraction is done
                    const extracted = getExtractedAmount(refreshed);
                    if (extracted) setClaimAmount(extracted);
                }
            } catch { /* ignore transient poll errors */ }
        }, 2000);

        return () => stopWizardPoll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [step, claimId, uploadedDocs.map(d => d.validation_status).join(",")]);

    useEffect(() => () => stopWizardPoll(), [stopWizardPoll]);

    // Step 5
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
                    const raw = d[key];
                    // field may be {text: "42500", value: 42500} or a plain scalar
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

    // ── Step 3 → 4: create claim + upload docs ────────────────────────────────
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

            setStep(4);
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
                <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>Step {step} of 5</span>
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
                                <a href="#" style={{ color: "var(--blue)" }}>Terms &amp; Conditions</a>{" "}and{" "}
                                <a href="#" style={{ color: "var(--blue)" }}>Privacy Policy</a>.
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

                {/* ── Step 2: Choose type ─────────────────────────────────── */}
                {step === 2 && (
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
                            onClick={() => setStep(3)}
                            style={{ width: "100%" }}
                        >
                            Continue <ChevronRight size={14} />
                        </button>
                    </div>
                )}

                {/* ── Step 3: Policy + documents ──────────────────────────── */}
                {step === 3 && claimType && (
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
                            <button className="btn btn-ghost" onClick={() => setStep(2)}>
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

                {/* ── Step 4: OCR review ──────────────────────────────────── */}
                {step === 4 && (
                    <div>
                        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 6 }}>Review extracted data</h2>
                        <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", marginBottom: 20 }}>
                            {extracting ? "AI is reading your documents — this takes about 20–40 s…" : "Documents processed. Verify or correct the details below."}
                        </p>

                        {/* OCR extractions */}
                        {uploadedDocs.length > 0 && (
                            <div style={{ marginBottom: 20 }}>
                                {uploadedDocs.map((doc) => (
                                    <div key={doc.id} style={{
                                        border: "1px solid var(--border)", borderRadius: 6,
                                        padding: "10px 14px", marginBottom: 8, background: "var(--bg-surface)",
                                    }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
                                            <FileText size={13} color="var(--text-muted)" />
                                            <span style={{ fontSize: "0.75rem", fontWeight: 500 }}>{doc.original_filename ?? doc.document_type}</span>
                                            {doc.validation_status === "pending" ? (
                                                <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4, fontSize: "0.625rem", color: "var(--blue)", fontFamily: "var(--font-mono)" }}>
                                                    <Loader2 size={11} style={{ animation: "spin 1s linear infinite" }} /> extracting…
                                                </span>
                                            ) : doc.extraction_confidence !== null ? (
                                                <span style={{
                                                    marginLeft: "auto", fontSize: "0.625rem",
                                                    color: (doc.extraction_confidence ?? 0) >= 0.7 ? "var(--green)" : "var(--amber)",
                                                    fontFamily: "var(--font-mono)",
                                                }}>
                                                    {Math.round((doc.extraction_confidence ?? 0) * 100)}% confidence
                                                </span>
                                            ) : null}
                                        </div>
                                        {doc.validation_status === "pending" ? (
                                            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                                                {[80, 60, 70].map((w, i) => (
                                                    <div key={i} className="skeleton" style={{ height: 10, width: `${w}%` }} />
                                                ))}
                                            </div>
                                        ) : (
                                            <EditableExtractedData
                                                document={doc}
                                                onUpdate={(updated) => setUploadedDocs((prev) => prev.map((d) => d.id === updated.id ? updated : d))}
                                                onError={() => {}}
                                            />
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

                        <div style={{ display: "flex", gap: 8 }}>
                            <button className="btn btn-ghost" onClick={() => setStep(3)}>
                                <ChevronLeft size={14} /> Back
                            </button>
                            <button
                                className="btn btn-primary"
                                disabled={!claimAmount || extracting}
                                onClick={() => setStep(5)}
                                style={{ flex: 1 }}
                            >
                                {extracting ? (
                                    <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Extracting…</>
                                ) : (
                                    <>Review &amp; Confirm <ChevronRight size={14} /></>
                                )}
                            </button>
                        </div>
                    </div>
                )}

                {/* ── Step 5: Confirm ─────────────────────────────────────── */}
                {step === 5 && claimType && (
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
                            <button className="btn btn-ghost" onClick={() => setStep(4)}>
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

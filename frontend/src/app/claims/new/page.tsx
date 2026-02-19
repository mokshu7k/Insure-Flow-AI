"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { claimService } from "@/services/claimService";
import { documentService } from "@/services/documentService";
import { complianceService } from "@/services/complianceService";
import { extractErrorMessage } from "@/lib/utils";
import type { ClaimType, DocumentType, DocumentResponse, OCRResult } from "@/types";
import {
    Loader2,
    FileText,
    Upload,
    CheckCircle2,
    ChevronRight,
    ChevronLeft,
    AlertTriangle,
    X,
    Heart,
    Car,
    Receipt,
    Eye,
} from "lucide-react";

// Document requirements per claim type
const REQUIRED_DOCS: Record<ClaimType, { type: DocumentType; label: string; required: boolean }[]> = {
    HEALTH: [
        { type: "INVOICE", label: "Policy Document", required: true },
        { type: "OTHER", label: "PAN Card / ID Proof", required: true },
        { type: "DISCHARGE_SUMMARY", label: "Discharge Summary", required: true },
        { type: "MEDICAL_REPORT", label: "Medical Reports", required: false },
        { type: "PRESCRIPTION", label: "Prescriptions", required: false },
        { type: "INVOICE", label: "Hospital Bills/Invoices", required: false },
    ],
    MOTOR: [
        { type: "OTHER", label: "Policy Document", required: true },
        { type: "VEHICLE_RC", label: "Driving License", required: true },
        { type: "VEHICLE_RC", label: "Vehicle RC", required: true },
        { type: "POLICE_REPORT", label: "FIR / Police Report", required: false },
        { type: "ESTIMATE", label: "Repair Estimate", required: false },
        { type: "OTHER", label: "Photos of Damage", required: false },
    ],
    REIMBURSEMENT: [
        { type: "INVOICE", label: "Policy Document", required: true },
        { type: "OTHER", label: "ID Proof", required: true },
        { type: "INVOICE", label: "Original Bills/Invoices", required: true },
        { type: "PRESCRIPTION", label: "Prescriptions", required: false },
        { type: "OTHER", label: "Payment Receipts", required: false },
    ],
};

const CLAIM_TYPE_INFO = {
    HEALTH: {
        icon: Heart,
        label: "Health Insurance",
        description: "Medical expenses, hospitalization, treatments",
        color: "text-rose-500",
        bgColor: "bg-rose-50 dark:bg-rose-950/20",
        borderColor: "border-rose-200 dark:border-rose-800",
    },
    MOTOR: {
        icon: Car,
        label: "Motor Insurance",
        description: "Vehicle damage, accidents, theft claims",
        color: "text-blue-500",
        bgColor: "bg-blue-50 dark:bg-blue-950/20",
        borderColor: "border-blue-200 dark:border-blue-800",
    },
    REIMBURSEMENT: {
        icon: Receipt,
        label: "Reimbursement",
        description: "Out-of-pocket medical expense reimbursement",
        color: "text-amber-500",
        bgColor: "bg-amber-50 dark:bg-amber-950/20",
        borderColor: "border-amber-200 dark:border-amber-800",
    },
};

interface UploadedDoc {
    file: File;
    docType: DocumentType;
    label: string;
    status: "pending" | "uploading" | "done" | "error";
    response?: DocumentResponse;
    ocrData?: OCRResult;
    error?: string;
}

export default function NewClaimPage() {
    const router = useRouter();
    const [step, setStep] = useState(1);
    const [claimType, setClaimType] = useState<ClaimType | null>(null);
    const [policyNumber, setPolicyNumber] = useState("");
    const [uploadedDocs, setUploadedDocs] = useState<UploadedDoc[]>([]);
    const [claimAmount, setClaimAmount] = useState("");
    const [createdClaimId, setCreatedClaimId] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [ocrLoading, setOcrLoading] = useState(false);
    const [extractedInfo, setExtractedInfo] = useState<Record<string, string>>({});

    // Step 1: Select claim type
    const handleSelectClaimType = (type: ClaimType) => {
        setClaimType(type);
        setUploadedDocs([]);
        setStep(2);
    };

    // Step 2: Document upload dropzone
    const onDrop = useCallback(
        (acceptedFiles: File[], docLabel: string, docType: DocumentType) => {
            const newDocs = acceptedFiles.map((file) => ({
                file,
                docType,
                label: docLabel,
                status: "pending" as const,
            }));
            setUploadedDocs((prev) => [...prev, ...newDocs]);
        },
        []
    );

    const removeDoc = (index: number) => {
        setUploadedDocs((prev) => prev.filter((_, i) => i !== index));
    };

    // Check if required docs are uploaded
    const requiredDocs = claimType ? REQUIRED_DOCS[claimType].filter((d) => d.required) : [];
    const hasAllRequired = requiredDocs.every((req) =>
        uploadedDocs.some((u) => u.label === req.label)
    );

    // Step 2 -> Step 3: Create claim and upload docs
    const handleProceedToReview = async () => {
        if (!claimType || !policyNumber.trim()) {
            setError("Please enter a policy number");
            return;
        }
        if (!hasAllRequired) {
            setError("Please upload all required documents");
            return;
        }

        setLoading(true);
        setError("");

        try {
            // Ensure consent is given before creating claim
            const consentStatus = await complianceService.getConsentStatus();
            if (!consentStatus.has_valid_consent) {
                await complianceService.giveConsent();
            }

            // Create claim (amount will be set in final step)
            const claim = await claimService.create({
                policy_number: policyNumber,
                claim_type: claimType,
            });
            setCreatedClaimId(claim.id);

            // Upload all documents
            const updatedDocs = [...uploadedDocs];
            for (let i = 0; i < updatedDocs.length; i++) {
                updatedDocs[i].status = "uploading";
                setUploadedDocs([...updatedDocs]);

                try {
                    const response = await documentService.upload(
                        claim.id,
                        updatedDocs[i].file,
                        updatedDocs[i].docType
                    );
                    updatedDocs[i].status = "done";
                    updatedDocs[i].response = response;
                    setUploadedDocs([...updatedDocs]);
                } catch {
                    updatedDocs[i].status = "error";
                    updatedDocs[i].error = "Upload failed";
                    setUploadedDocs([...updatedDocs]);
                }
            }

            // Fetch OCR data for uploaded documents
            setOcrLoading(true);
            const ocrResults: Record<string, string> = {};
            for (const doc of updatedDocs) {
                if (doc.response && doc.response.has_ocr_data) {
                    try {
                        const ocr = await documentService.getOCR(doc.response.id);
                        doc.ocrData = ocr;
                        // Extract key fields
                        if (ocr.extracted_fields) {
                            Object.entries(ocr.extracted_fields).forEach(([key, value]) => {
                                if (typeof value === "string" && value.trim()) {
                                    ocrResults[key] = value;
                                }
                            });
                        }
                    } catch {
                        // OCR data not available
                    }
                }
            }
            setUploadedDocs([...updatedDocs]);
            setExtractedInfo(ocrResults);
            setOcrLoading(false);
            setStep(3);
        } catch (err: unknown) {
            setError(extractErrorMessage(err, "Failed to create claim"));
        } finally {
            setLoading(false);
        }
    };

    // Step 4: Submit final claim with amount
    const handleSubmitClaim = async () => {
        if (!createdClaimId || !claimAmount) {
            setError("Please enter the claim amount");
            return;
        }

        setLoading(true);
        setError("");

        try {
            // Update claim with final amount
            await claimService.updateAmount(createdClaimId, parseFloat(claimAmount));
            // Navigate to the claim page
            router.push(`/claims/${createdClaimId}`);
        } catch (err: unknown) {
            setError(extractErrorMessage(err, "Failed to submit claim"));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-3xl mx-auto space-y-6">
            {/* Progress Steps */}
            <div className="flex items-center justify-between mb-8">
                {[1, 2, 3, 4].map((s) => (
                    <div key={s} className="flex items-center">
                        <div
                            className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold text-sm transition-colors ${
                                step >= s
                                    ? "bg-indigo-600 text-white"
                                    : "bg-gray-200 dark:bg-gray-700 text-gray-500"
                            }`}
                        >
                            {step > s ? <CheckCircle2 size={20} /> : s}
                        </div>
                        {s < 4 && (
                            <div
                                className={`w-16 sm:w-24 h-1 mx-2 rounded ${
                                    step > s ? "bg-indigo-600" : "bg-gray-200 dark:bg-gray-700"
                                }`}
                            />
                        )}
                    </div>
                ))}
            </div>

            {/* Step Labels */}
            <div className="flex justify-between text-xs text-[var(--color-muted-foreground)] px-2 mb-6">
                <span className={step >= 1 ? "text-indigo-600 font-medium" : ""}>Type</span>
                <span className={step >= 2 ? "text-indigo-600 font-medium" : ""}>Documents</span>
                <span className={step >= 3 ? "text-indigo-600 font-medium" : ""}>Review</span>
                <span className={step >= 4 ? "text-indigo-600 font-medium" : ""}>Submit</span>
            </div>

            {error && (
                <div className="px-4 py-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm flex items-center gap-2">
                    <AlertTriangle size={16} />
                    {error}
                </div>
            )}

            {/* Step 1: Select Claim Type */}
            {step === 1 && (
                <div className="space-y-4">
                    <div>
                        <h1 className="text-2xl font-bold">Select Claim Type</h1>
                        <p className="text-sm text-[var(--color-muted-foreground)]">
                            Choose the type of insurance claim you want to file
                        </p>
                    </div>

                    <div className="grid gap-4">
                        {(Object.keys(CLAIM_TYPE_INFO) as ClaimType[]).map((type) => {
                            const info = CLAIM_TYPE_INFO[type];
                            const Icon = info.icon;
                            return (
                                <button
                                    key={type}
                                    onClick={() => handleSelectClaimType(type)}
                                    className={`flex items-center gap-4 p-5 rounded-xl border-2 ${info.bgColor} ${info.borderColor} hover:shadow-md transition-all text-left`}
                                >
                                    <div className={`p-3 rounded-xl bg-white dark:bg-gray-900 ${info.color}`}>
                                        <Icon size={28} />
                                    </div>
                                    <div>
                                        <h3 className="font-semibold text-lg">{info.label}</h3>
                                        <p className="text-sm text-[var(--color-muted-foreground)]">
                                            {info.description}
                                        </p>
                                    </div>
                                    <ChevronRight size={24} className="ml-auto text-gray-400" />
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Step 2: Upload Documents */}
            {step === 2 && claimType && (
                <div className="space-y-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-bold">Upload Documents</h1>
                            <p className="text-sm text-[var(--color-muted-foreground)]">
                                Upload required documents for your {CLAIM_TYPE_INFO[claimType].label} claim
                            </p>
                        </div>
                        <button
                            onClick={() => setStep(1)}
                            className="text-sm text-indigo-600 hover:underline flex items-center gap-1"
                        >
                            <ChevronLeft size={16} />
                            Back
                        </button>
                    </div>

                    {/* Policy Number Input */}
                    <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-4">
                        <label className="block text-sm font-medium mb-1.5">
                            Policy Number <span className="text-red-500">*</span>
                        </label>
                        <input
                            type="text"
                            value={policyNumber}
                            onChange={(e) => setPolicyNumber(e.target.value)}
                            placeholder="e.g. POL-2026-001234"
                            className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-transparent text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                        />
                    </div>

                    {/* Document Upload Sections */}
                    <div className="space-y-4">
                        {REQUIRED_DOCS[claimType].map((doc, idx) => (
                            <DocumentUploadSection
                                key={idx}
                                label={doc.label}
                                docType={doc.type}
                                required={doc.required}
                                uploadedDocs={uploadedDocs.filter((u) => u.label === doc.label)}
                                onDrop={(files) => onDrop(files, doc.label, doc.type)}
                                onRemove={(i) => {
                                    const allWithLabel = uploadedDocs
                                        .map((u, idx) => ({ ...u, idx }))
                                        .filter((u) => u.label === doc.label);
                                    if (allWithLabel[i]) {
                                        removeDoc(allWithLabel[i].idx);
                                    }
                                }}
                            />
                        ))}
                    </div>

                    {/* Consent Notice */}
                    <div className="p-4 rounded-lg bg-indigo-50 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/30">
                        <div className="flex gap-3">
                            <FileText size={18} className="text-indigo-500 shrink-0 mt-0.5" />
                            <div>
                                <p className="text-sm font-medium text-indigo-700 dark:text-indigo-300">
                                    Document Processing Consent
                                </p>
                                <p className="text-xs text-indigo-600/70 dark:text-indigo-400/70 mt-1">
                                    By uploading documents, you consent to AI-powered OCR analysis to extract
                                    policy details, claim information, and relevant data as per DPDP regulations.
                                </p>
                            </div>
                        </div>
                    </div>

                    <button
                        onClick={handleProceedToReview}
                        disabled={loading || !policyNumber.trim() || !hasAllRequired}
                        className="w-full py-3 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-medium text-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                        {loading && <Loader2 size={16} className="animate-spin" />}
                        {loading ? "Processing Documents..." : "Process & Review"}
                        {!loading && <ChevronRight size={16} />}
                    </button>
                </div>
            )}

            {/* Step 3: Review Extracted Information */}
            {step === 3 && (
                <div className="space-y-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-bold">Review Extracted Information</h1>
                            <p className="text-sm text-[var(--color-muted-foreground)]">
                                Verify the information extracted from your documents
                            </p>
                        </div>
                    </div>

                    {ocrLoading ? (
                        <div className="flex flex-col items-center justify-center py-12">
                            <Loader2 size={32} className="animate-spin text-indigo-500 mb-4" />
                            <p className="text-sm text-[var(--color-muted-foreground)]">
                                Extracting information from documents...
                            </p>
                        </div>
                    ) : (
                        <>
                            {/* Uploaded Documents Summary */}
                            <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5">
                                <h3 className="font-semibold mb-4 flex items-center gap-2">
                                    <FileText size={18} className="text-indigo-500" />
                                    Uploaded Documents
                                </h3>
                                <div className="space-y-2">
                                    {uploadedDocs.map((doc, idx) => (
                                        <div
                                            key={idx}
                                            className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg"
                                        >
                                            <div className="flex items-center gap-3">
                                                {doc.status === "done" ? (
                                                    <CheckCircle2 size={18} className="text-emerald-500" />
                                                ) : doc.status === "error" ? (
                                                    <AlertTriangle size={18} className="text-red-500" />
                                                ) : (
                                                    <FileText size={18} className="text-gray-400" />
                                                )}
                                                <div>
                                                    <p className="text-sm font-medium">{doc.label}</p>
                                                    <p className="text-xs text-[var(--color-muted-foreground)]">
                                                        {doc.file.name}
                                                    </p>
                                                </div>
                                            </div>
                                            {doc.response?.has_ocr_data && (
                                                <span className="text-xs bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-300 px-2 py-1 rounded">
                                                    OCR: {Math.round((doc.response.ocr_confidence || 0) * 100)}%
                                                </span>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Extracted Information */}
                            <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5">
                                <h3 className="font-semibold mb-4 flex items-center gap-2">
                                    <Eye size={18} className="text-purple-500" />
                                    Extracted Information
                                </h3>
                                {Object.keys(extractedInfo).length > 0 ? (
                                    <div className="grid grid-cols-2 gap-4">
                                        {Object.entries(extractedInfo).map(([key, value]) => (
                                            <div key={key} className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                                                <p className="text-xs text-[var(--color-muted-foreground)] uppercase tracking-wider">
                                                    {key.replace(/_/g, " ")}
                                                </p>
                                                <p className="text-sm font-medium mt-1">{value}</p>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-[var(--color-muted-foreground)]">
                                        No structured information could be extracted. Please ensure documents
                                        are clear and legible.
                                    </p>
                                )}
                            </div>

                            {/* Policy Information from manual input */}
                            <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5">
                                <h3 className="font-semibold mb-4">Claim Summary</h3>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <p className="text-xs text-[var(--color-muted-foreground)]">Policy Number</p>
                                        <p className="font-medium">{policyNumber}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-[var(--color-muted-foreground)]">Claim Type</p>
                                        <p className="font-medium">{claimType && CLAIM_TYPE_INFO[claimType].label}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-[var(--color-muted-foreground)]">Documents Uploaded</p>
                                        <p className="font-medium">{uploadedDocs.length}</p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-[var(--color-muted-foreground)]">Status</p>
                                        <p className="font-medium text-amber-600">Pending Amount Entry</p>
                                    </div>
                                </div>
                            </div>

                            <button
                                onClick={() => setStep(4)}
                                className="w-full py-3 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-medium text-sm transition-all flex items-center justify-center gap-2"
                            >
                                Continue to Submit
                                <ChevronRight size={16} />
                            </button>
                        </>
                    )}
                </div>
            )}

            {/* Step 4: Enter Amount and Submit */}
            {step === 4 && (
                <div className="space-y-6">
                    <div>
                        <h1 className="text-2xl font-bold">Submit Your Claim</h1>
                        <p className="text-sm text-[var(--color-muted-foreground)]">
                            Enter the claim amount and submit for processing
                        </p>
                    </div>

                    <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6 space-y-6">
                        {/* Claim Summary */}
                        <div className="grid grid-cols-2 gap-4 pb-4 border-b border-[var(--color-border)]">
                            <div>
                                <p className="text-xs text-[var(--color-muted-foreground)]">Policy Number</p>
                                <p className="font-semibold">{policyNumber}</p>
                            </div>
                            <div>
                                <p className="text-xs text-[var(--color-muted-foreground)]">Claim Type</p>
                                <p className="font-semibold">{claimType && CLAIM_TYPE_INFO[claimType].label}</p>
                            </div>
                        </div>

                        {/* Amount Input */}
                        <div>
                            <label className="block text-sm font-medium mb-1.5">
                                Claim Amount (₹) <span className="text-red-500">*</span>
                            </label>
                            <input
                                type="number"
                                value={claimAmount}
                                onChange={(e) => setClaimAmount(e.target.value)}
                                placeholder="Enter the total claim amount"
                                className="w-full px-4 py-3 rounded-lg border border-[var(--color-input)] bg-transparent text-lg font-semibold outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                            />
                            <p className="text-xs text-[var(--color-muted-foreground)] mt-2">
                                Enter the total amount you are claiming based on your bills and expenses
                            </p>
                        </div>

                        {/* Final Consent */}
                        <div className="p-4 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800">
                            <div className="flex gap-3">
                                <AlertTriangle size={18} className="text-amber-500 shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
                                        Declaration
                                    </p>
                                    <p className="text-xs text-amber-600/80 dark:text-amber-400/80 mt-1">
                                        I hereby declare that the information provided is true and accurate.
                                        I understand that submitting false claims is punishable by law.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-3">
                        <button
                            onClick={() => setStep(3)}
                            className="flex-1 py-3 rounded-lg border border-[var(--color-border)] text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors flex items-center justify-center gap-2"
                        >
                            <ChevronLeft size={16} />
                            Back
                        </button>
                        <button
                            onClick={handleSubmitClaim}
                            disabled={loading || !claimAmount}
                            className="flex-[2] py-3 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white font-medium text-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                            {loading && <Loader2 size={16} className="animate-spin" />}
                            {loading ? "Submitting..." : "Submit Claim"}
                            {!loading && <CheckCircle2 size={16} />}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

// Document Upload Section Component
function DocumentUploadSection({
    label,
    docType,
    required,
    uploadedDocs,
    onDrop,
    onRemove,
}: {
    label: string;
    docType: DocumentType;
    required: boolean;
    uploadedDocs: UploadedDoc[];
    onDrop: (files: File[]) => void;
    onRemove: (index: number) => void;
}) {
    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            "image/*": [".jpeg", ".jpg", ".png"],
            "application/pdf": [".pdf"],
        },
        multiple: true,
    });

    return (
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium">
                    {label} {required && <span className="text-red-500">*</span>}
                </label>
                {uploadedDocs.length > 0 && (
                    <span className="text-xs bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-300 px-2 py-1 rounded-full">
                        {uploadedDocs.length} file(s)
                    </span>
                )}
            </div>

            {/* Uploaded files */}
            {uploadedDocs.length > 0 && (
                <div className="space-y-2 mb-3">
                    {uploadedDocs.map((doc, idx) => (
                        <div
                            key={idx}
                            className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg text-sm"
                        >
                            <div className="flex items-center gap-2 truncate">
                                <FileText size={14} className="text-indigo-500 shrink-0" />
                                <span className="truncate">{doc.file.name}</span>
                                <span className="text-xs text-gray-500">
                                    ({(doc.file.size / 1024).toFixed(0)} KB)
                                </span>
                            </div>
                            <button
                                onClick={() => onRemove(idx)}
                                className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                            >
                                <X size={14} />
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {/* Dropzone */}
            <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
                    isDragActive
                        ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/20"
                        : "border-gray-300 dark:border-gray-600 hover:border-indigo-400"
                }`}
            >
                <input {...getInputProps()} />
                <Upload size={20} className="mx-auto text-gray-400 mb-2" />
                <p className="text-xs text-[var(--color-muted-foreground)]">
                    {isDragActive
                        ? "Drop files here..."
                        : "Drag & drop or click to upload (JPEG, PNG, PDF)"}
                </p>
            </div>
        </div>
    );
}

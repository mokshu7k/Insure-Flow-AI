/**
 * Privacy Policy — InsureFlow AI
 * Version 1.0 | Effective: 1 January 2026
 *
 * This notice satisfies the obligations of a Data Fiduciary under:
 *  - Digital Personal Data Protection Act, 2023 (DPDP Act) — India
 *  - DPDP Rules, 2025
 *  - IRDAI Guidelines on Information Security, 2023
 */
import type { Metadata } from "next";

export const metadata: Metadata = {
    title: "Privacy Policy — InsureFlow AI",
    description: "InsureFlow AI Privacy Policy and DPDP Act Data Processing Notice",
};

const Section = ({
    id,
    heading,
    children,
}: {
    id: string;
    heading: string;
    children: React.ReactNode;
}) => (
    <section id={id} style={{ marginBottom: 32 }}>
        <h2
            style={{
                fontSize: "1rem",
                fontWeight: 600,
                color: "var(--text-primary)",
                marginBottom: 10,
                paddingBottom: 6,
                borderBottom: "1px solid var(--border)",
            }}
        >
            {heading}
        </h2>
        <div
            style={{
                fontSize: "0.8125rem",
                lineHeight: 1.75,
                color: "var(--text-secondary)",
            }}
        >
            {children}
        </div>
    </section>
);

const P = ({ children }: { children: React.ReactNode }) => (
    <p style={{ marginBottom: 10 }}>{children}</p>
);

const Table = ({
    rows,
}: {
    rows: { category: string; examples: string; purpose: string; basis: string }[];
}) => (
    <div style={{ overflowX: "auto", marginBottom: 12 }}>
        <table
            style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "0.8125rem",
            }}
        >
            <thead>
                <tr
                    style={{
                        background: "var(--bg-surface)",
                        borderBottom: "1px solid var(--border)",
                    }}
                >
                    {["Category", "Examples", "Purpose", "Legal Basis"].map((h) => (
                        <th
                            key={h}
                            style={{
                                padding: "8px 10px",
                                textAlign: "left",
                                fontWeight: 600,
                                color: "var(--text-primary)",
                                whiteSpace: "nowrap",
                            }}
                        >
                            {h}
                        </th>
                    ))}
                </tr>
            </thead>
            <tbody>
                {rows.map((row, i) => (
                    <tr
                        key={i}
                        style={{
                            borderBottom: "1px solid var(--border)",
                            background: i % 2 === 0 ? "transparent" : "var(--bg-surface)",
                        }}
                    >
                        <td
                            style={{
                                padding: "8px 10px",
                                fontWeight: 500,
                                color: "var(--text-primary)",
                            }}
                        >
                            {row.category}
                        </td>
                        <td style={{ padding: "8px 10px" }}>{row.examples}</td>
                        <td style={{ padding: "8px 10px" }}>{row.purpose}</td>
                        <td style={{ padding: "8px 10px" }}>{row.basis}</td>
                    </tr>
                ))}
            </tbody>
        </table>
    </div>
);

const Ul = ({ items }: { items: string[] }) => (
    <ul style={{ paddingLeft: 20, marginBottom: 10 }}>
        {items.map((item, i) => (
            <li key={i} style={{ marginBottom: 4 }}>
                {item}
            </li>
        ))}
    </ul>
);

export default function PrivacyPage() {
    return (
        <div
            style={{
                minHeight: "100vh",
                background: "var(--bg-base)",
                color: "var(--text-primary)",
                fontFamily: "var(--font-sans)",
            }}
        >
            {/* Header */}
            <div
                style={{
                    borderBottom: "1px solid var(--border)",
                    background: "var(--bg-panel)",
                    padding: "20px 24px",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                }}
            >
                <a
                    href="/"
                    style={{
                        fontSize: "0.8125rem",
                        color: "var(--blue)",
                        textDecoration: "none",
                    }}
                >
                    ← Back
                </a>
                <span style={{ color: "var(--border-strong)" }}>|</span>
                <span
                    style={{
                        fontSize: "0.875rem",
                        fontWeight: 600,
                        color: "var(--text-primary)",
                    }}
                >
                    InsureFlow AI
                </span>
            </div>

            {/* Body */}
            <div
                style={{
                    maxWidth: 860,
                    margin: "0 auto",
                    padding: "40px 24px 80px",
                }}
            >
                {/* Title block */}
                <div style={{ marginBottom: 36 }}>
                    <h1
                        style={{
                            fontSize: "1.375rem",
                            fontWeight: 700,
                            marginBottom: 6,
                        }}
                    >
                        Privacy Policy
                    </h1>
                    <p
                        style={{
                            fontSize: "0.8125rem",
                            color: "var(--text-muted)",
                        }}
                    >
                        Version 1.0 &nbsp;·&nbsp; Effective 1 January 2026
                    </p>

                    {/* DPDP Act prominent notice */}
                    <div
                        style={{
                            marginTop: 14,
                            padding: "14px 16px",
                            background: "var(--blue-bg)",
                            border: "1px solid var(--blue-border)",
                            borderRadius: 4,
                            fontSize: "0.8125rem",
                            color: "var(--text-secondary)",
                            lineHeight: 1.7,
                        }}
                    >
                        <strong style={{ color: "var(--blue)", display: "block", marginBottom: 4 }}>
                            DPDP Act 2023 — Data Fiduciary Notice
                        </strong>
                        This Privacy Policy is the{" "}
                        <strong>notice required under Section 5 of the Digital Personal
                        Data Protection Act, 2023</strong>. It describes the personal data we
                        collect, why we collect it, how long we retain it, your rights as a
                        Data Principal, and how to contact our Grievance Officer. Please read
                        it before registering.
                    </div>
                </div>

                <Section id="fiduciary" heading="1. Data Fiduciary Details">
                    <div
                        style={{
                            padding: "12px 16px",
                            background: "var(--bg-surface)",
                            border: "1px solid var(--border)",
                            borderRadius: 4,
                            lineHeight: 1.8,
                        }}
                    >
                        <strong>InsureFlow AI</strong>
                        <br />
                        Platform: Insurance Claims Automation (SaaS)
                        <br />
                        Contact:{" "}
                        <a
                            href="mailto:privacy@insureflow.ai"
                            style={{ color: "var(--blue)" }}
                        >
                            privacy@insureflow.ai
                        </a>
                        <br />
                        Grievance Officer:{" "}
                        <a
                            href="mailto:grievance@insureflow.ai"
                            style={{ color: "var(--blue)" }}
                        >
                            grievance@insureflow.ai
                        </a>
                    </div>
                </Section>

                <Section id="data-collected" heading="2. Personal Data We Collect">
                    <Table
                        rows={[
                            {
                                category: "Identity",
                                examples: "Full name, date of birth, PAN, Aadhaar (masked), passport",
                                purpose: "KYC verification, account creation",
                                basis: "Consent / Legal obligation",
                            },
                            {
                                category: "Contact",
                                examples: "Email address, mobile number, postal address",
                                purpose: "Communication, OTP, notifications",
                                basis: "Consent",
                            },
                            {
                                category: "Health & Medical",
                                examples: "Diagnosis, treatment records, hospital bills, discharge summaries",
                                purpose: "Claim processing, fraud detection",
                                basis: "Explicit Consent (Sensitive PD)",
                            },
                            {
                                category: "Financial",
                                examples: "Policy number, bank account (for settlement), claim amounts",
                                purpose: "Claim settlement, payment disbursement",
                                basis: "Consent / Contract",
                            },
                            {
                                category: "Technical",
                                examples: "IP address, browser type, device ID, session logs",
                                purpose: "Security, fraud prevention, audit logs",
                                basis: "Legitimate interest (security)",
                            },
                            {
                                category: "Documents",
                                examples: "Scanned PDFs, images, QR tokens",
                                purpose: "OCR extraction, claim validation",
                                basis: "Consent",
                            },
                        ]}
                    />
                    <P>
                        <strong>Sensitive Personal Data (SPD)</strong> — Health and
                        medical information is classified as sensitive personal data.
                        We collect and process it only with your explicit consent and
                        strictly for insurance-related purposes.
                    </P>
                </Section>

                <Section id="legal-basis" heading="3. Legal Basis for Processing (DPDP Act)">
                    <Ul
                        items={[
                            "Consent (Section 6) — your explicit, informed consent given at registration",
                            "Legal obligation (Section 7(b)) — mandatory IRDAI reporting, court orders, statutory audits",
                            "Contract performance — processing necessary to execute your insurance claim",
                            "Legitimate interest (security/fraud) — protecting the platform and all users from fraudulent activity",
                        ]}
                    />
                </Section>

                <Section id="sharing" heading="4. Data Sharing & Disclosure">
                    <P>We do not sell your data. We share it only when necessary:</P>
                    <Ul
                        items={[
                            "Insurers / TPAs — to process and settle your claim (contractual necessity)",
                            "Healthcare providers — for cashless claim pre-authorisation",
                            "Fraud intelligence platforms — anonymised risk signals for industry fraud prevention",
                            "Government & regulatory bodies — IRDAI, courts, law enforcement when legally compelled",
                            "Cloud infrastructure (AWS / GCP) — as Data Processors under binding DPAs with equivalent safeguards",
                        ]}
                    />
                    <P>
                        All third-party Data Processors are required to maintain
                        at least equivalent data protection standards under
                        contractual obligations.
                    </P>
                </Section>

                <Section id="retention" heading="5. Retention Periods">
                    <Ul
                        items={[
                            "Active accounts — data retained for the duration of the account",
                            "Claim records — minimum 7 years post-settlement (IRDAI mandate)",
                            "Audit & access logs — 5 years (compliance requirement)",
                            "Consent records — retained for at least as long as the underlying data they relate to",
                            "Deleted accounts — anonymised after 90 days; claim records retained per IRDAI requirements",
                        ]}
                    />
                </Section>

                <Section id="security" heading="6. Security Measures">
                    <Ul
                        items={[
                            "AES-256 encryption for data at rest",
                            "TLS 1.3 for all data in transit",
                            "Role-based access control (RBAC) with least-privilege enforcement",
                            "Immutable append-only audit trail for all data access events",
                            "Automated fraud detection with human-in-the-loop review",
                            "Regular vulnerability assessments and penetration testing",
                            "Multi-factor authentication for administrator accounts",
                        ]}
                    />
                    <P>
                        In the event of a data breach that is likely to result in
                        harm to your rights, we will notify the Data Protection
                        Board of India and affected users within the timelines
                        prescribed under the DPDP Act.
                    </P>
                </Section>

                <Section id="rights" heading="7. Your Rights as a Data Principal">
                    <P>
                        You may exercise any of the following rights at any time
                        from your{" "}
                        <a href="/profile" style={{ color: "var(--blue)" }}>
                            Profile & Privacy Settings
                        </a>{" "}
                        or by emailing{" "}
                        <a
                            href="mailto:privacy@insureflow.ai"
                            style={{ color: "var(--blue)" }}
                        >
                            privacy@insureflow.ai
                        </a>
                        :
                    </P>
                    <Ul
                        items={[
                            "Right to Information — request a summary of personal data held and its processing details",
                            "Right of Correction — request correction of incorrect or incomplete personal data",
                            "Right of Erasure — request deletion of data no longer needed (subject to legal retention obligations)",
                            "Right to Withdraw Consent — withdraw consent at any time without penalty; withdrawal does not affect processing already performed",
                            "Right to Nominate — designate a trusted person to exercise rights on your behalf",
                            "Right to Grievance Redressal — raise a complaint with our Grievance Officer (response within 30 days)",
                        ]}
                    />
                    <P>
                        If you are not satisfied with our response, you may
                        escalate to the{" "}
                        <strong>Data Protection Board of India</strong> once
                        constituted under the DPDP Act.
                    </P>
                </Section>

                <Section id="children" heading="8. Children's Data">
                    <P>
                        InsureFlow AI does not knowingly process personal data of
                        individuals under 18 years of age without verifiable
                        parental consent, in accordance with Section 9 of the DPDP
                        Act. If you believe a minor's data has been processed
                        without consent, please contact us immediately.
                    </P>
                </Section>

                <Section id="cross-border" heading="9. Cross-Border Data Transfers">
                    <P>
                        Personal data is primarily stored and processed within India.
                        Where data is transferred outside India (e.g., to cloud
                        infrastructure in notified countries under the DPDP Act), we
                        ensure adequate safeguards are in place through Standard
                        Contractual Clauses or equivalent mechanisms.
                    </P>
                </Section>

                <Section id="consent-management" heading="10. Consent Management & Withdrawal">
                    <P>
                        You can review, update or withdraw your consent at any time
                        from your account's{" "}
                        <a href="/profile" style={{ color: "var(--blue)" }}>
                            Privacy Settings
                        </a>{" "}
                        page. Each consent event is timestamped, versioned and
                        retained in an immutable audit log.
                    </P>
                    <P>
                        Withdrawing consent will restrict data processing to
                        legally mandated activities (e.g., ongoing regulatory
                        obligations). It may prevent you from using certain
                        platform features.
                    </P>
                </Section>

                <Section id="cookies" heading="11. Cookies & Session Data">
                    <P>
                        We use strictly necessary session cookies for authentication
                        and security. We do not use advertising, tracking or
                        analytics cookies. No third-party advertising code is
                        present on this Platform.
                    </P>
                </Section>

                <Section id="changes" heading="12. Policy Updates">
                    <P>
                        When we update this Policy, we will notify you by email and
                        in-app notice at least 14 days before the change takes
                        effect. The current version and its effective date are shown
                        at the top of this page. Continued use after the notice
                        period constitutes acceptance; you may withdraw consent if
                        you disagree.
                    </P>
                </Section>

                <Section id="contact" heading="13. Contact & Grievance Officer">
                    <div
                        style={{
                            padding: "12px 16px",
                            background: "var(--bg-surface)",
                            border: "1px solid var(--border)",
                            borderRadius: 4,
                            fontSize: "0.8125rem",
                            lineHeight: 1.8,
                        }}
                    >
                        <strong>Grievance Officer — InsureFlow AI</strong>
                        <br />
                        Email:{" "}
                        <a
                            href="mailto:grievance@insureflow.ai"
                            style={{ color: "var(--blue)" }}
                        >
                            grievance@insureflow.ai
                        </a>
                        <br />
                        Privacy email:{" "}
                        <a
                            href="mailto:privacy@insureflow.ai"
                            style={{ color: "var(--blue)" }}
                        >
                            privacy@insureflow.ai
                        </a>
                        <br />
                        Response time: within 30 days of receipt of complaint
                    </div>
                </Section>

                <div
                    style={{
                        marginTop: 40,
                        paddingTop: 16,
                        borderTop: "1px solid var(--border)",
                        fontSize: "0.75rem",
                        color: "var(--text-muted)",
                        textAlign: "center",
                    }}
                >
                    InsureFlow AI · Privacy Policy v1.0 · Effective 1 January 2026 ·{" "}
                    <a
                        href="/terms"
                        style={{ color: "var(--blue)", textDecoration: "none" }}
                    >
                        Terms &amp; Conditions
                    </a>
                </div>
            </div>
        </div>
    );
}

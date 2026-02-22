/**
 * Terms & Conditions — InsureFlow AI
 * Version 1.0 | Effective: 1 January 2026
 *
 * Drafted in compliance with:
 *  - Digital Personal Data Protection Act, 2023 (DPDP Act) — India
 *  - IRDAI Guidelines on Information Security
 */
import type { Metadata } from "next";

export const metadata: Metadata = {
    title: "Terms & Conditions — InsureFlow AI",
    description: "InsureFlow AI Terms and Conditions of Use",
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

const Ul = ({ items }: { items: string[] }) => (
    <ul style={{ paddingLeft: 20, marginBottom: 10 }}>
        {items.map((item, i) => (
            <li key={i} style={{ marginBottom: 4 }}>
                {item}
            </li>
        ))}
    </ul>
);

export default function TermsPage() {
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
                    maxWidth: 800,
                    margin: "0 auto",
                    padding: "40px 24px 80px",
                }}
            >
                <div style={{ marginBottom: 36 }}>
                    <h1
                        style={{
                            fontSize: "1.375rem",
                            fontWeight: 700,
                            marginBottom: 6,
                        }}
                    >
                        Terms &amp; Conditions
                    </h1>
                    <p
                        style={{
                            fontSize: "0.8125rem",
                            color: "var(--text-muted)",
                        }}
                    >
                        Version 1.0 &nbsp;·&nbsp; Effective 1 January 2026
                    </p>
                    <div
                        style={{
                            marginTop: 14,
                            padding: "10px 14px",
                            background: "var(--blue-bg)",
                            border: "1px solid var(--blue-border)",
                            borderRadius: 4,
                            fontSize: "0.8125rem",
                            color: "var(--text-secondary)",
                        }}
                    >
                        <strong style={{ color: "var(--blue)" }}>
                            DPDP Act 2023 — Consent Notice:
                        </strong>{" "}
                        By registering and using InsureFlow AI you are providing
                        free, specific, informed and unambiguous consent to the
                        collection and processing of your personal data as
                        described below. You may withdraw consent at any time
                        from your profile settings.
                    </div>
                </div>

                <Section id="parties" heading="1. Parties">
                    <P>
                        These Terms govern the relationship between{" "}
                        <strong>InsureFlow AI</strong> ("Platform", "we", "us") and
                        you ("User", "Data Principal") when you access or use the
                        InsureFlow AI insurance claims automation platform.
                    </P>
                    <P>
                        InsureFlow AI acts as a{" "}
                        <strong>Data Fiduciary</strong> under the Digital Personal
                        Data Protection Act, 2023 (DPDP Act) and is responsible for
                        the lawful processing of your personal data.
                    </P>
                </Section>

                <Section id="acceptance" heading="2. Acceptance of Terms">
                    <P>
                        Clicking <em>"I accept the Terms &amp; Conditions"</em>{" "}
                        during registration constitutes your explicit and informed
                        consent under Section 6 of the DPDP Act, 2023. This consent
                        is:
                    </P>
                    <Ul
                        items={[
                            "Freely given — not bundled with unrelated services without an opt-out",
                            "Specific — tied to the purposes listed in Section 4 below",
                            "Informed — you have access to these Terms and our Privacy Policy before consenting",
                            "Unambiguous — confirmed by an affirmative checkbox action",
                        ]}
                    />
                    <P>
                        If you do not agree, you must not register or use the
                        Platform.
                    </P>
                </Section>

                <Section id="services" heading="3. Services Provided">
                    <P>InsureFlow AI provides:</P>
                    <Ul
                        items={[
                            "AI-assisted insurance claim submission and tracking",
                            "Document OCR extraction and validation",
                            "Fraud risk assessment (automated + human review)",
                            "Cashless claim pre-authorisation coordination",
                            "Role-based access for Policyholders, Healthcare Providers, Insurer Admins and Compliance Auditors",
                            "Compliance audit trails and data access logs",
                        ]}
                    />
                </Section>

                <Section id="data-processing" heading="4. Personal Data — Purposes of Processing">
                    <P>
                        We process your personal data only for the following
                        specific, lawful purposes (DPDP Act, Section 4):
                    </P>
                    <Ul
                        items={[
                            "Account creation, authentication and access control",
                            "Processing, verifying and settling insurance claims",
                            "OCR extraction of policy and medical documents you upload",
                            "Automated fraud detection to protect all parties",
                            "Compliance monitoring and mandatory IRDAI reporting obligations",
                            "Customer support and dispute resolution",
                            "Platform security, abuse prevention and audit logging",
                        ]}
                    />
                    <P>
                        We do not process your personal data for advertising,
                        profiling for non-insurance purposes, or sale to third
                        parties.
                    </P>
                </Section>

                <Section id="user-obligations" heading="5. User Obligations">
                    <Ul
                        items={[
                            "You must provide accurate, truthful information during registration and claims submission",
                            "You are responsible for maintaining the confidentiality of your credentials",
                            "You must not submit fraudulent, forged or manipulated documents — this is a criminal offence under IPC/BNS and IRDAI regulations",
                            "You must not attempt to reverse-engineer, scrape or abuse the Platform's AI systems",
                            "You must promptly notify us of any unauthorised access to your account",
                        ]}
                    />
                </Section>

                <Section id="data-rights" heading="6. Your Rights as a Data Principal (DPDP Act)">
                    <P>
                        Under the DPDP Act, 2023, you have the following rights
                        exercisable at any time through your account or via our
                        Grievance Officer:
                    </P>
                    <Ul
                        items={[
                            "Right to Information — know what personal data we hold about you and how it is processed",
                            "Right of Correction & Erasure — request correction of inaccurate data or erasure where legally permissible",
                            "Right of Grievance Redressal — raise a complaint; we will respond within 30 days",
                            "Right to Nominate — nominate another individual to exercise these rights on your behalf",
                            "Right to Withdraw Consent — withdraw consent at any time (subject to legal retention obligations); withdrawal does not affect processing already done",
                        ]}
                    />
                </Section>

                <Section id="retention" heading="7. Data Retention">
                    <P>
                        Personal data is retained only for as long as necessary for
                        the purposes described above, or as mandated by IRDAI
                        regulations (minimum 7 years for claim records). Upon
                        expiry of the retention period or a valid erasure request,
                        data is securely deleted or anonymised.
                    </P>
                </Section>

                <Section id="security" heading="8. Security">
                    <P>
                        We implement technical and organisational measures including
                        AES-256 encryption at rest, TLS 1.3 in transit, role-based
                        access control (RBAC), immutable audit logs and regular
                        penetration testing. If a data breach occurs that is likely
                        to affect your rights, we will notify you and the Data
                        Protection Board of India within the timelines prescribed
                        under the DPDP Act.
                    </P>
                </Section>

                <Section id="third-parties" heading="9. Sharing with Third Parties">
                    <P>
                        We share your data only with:
                    </P>
                    <Ul
                        items={[
                            "Your insurer or third-party administrator (TPA) for claims processing — as your insurer is a necessary party",
                            "Healthcare providers involved in your cashless claim",
                            "Regulatory bodies (IRDAI, courts) when legally mandated",
                            "Cloud infrastructure providers acting as Data Processors under binding data processing agreements",
                        ]}
                    />
                    <P>
                        All Data Processors are required to provide equivalent data
                        protection standards under contractual obligations.
                    </P>
                </Section>

                <Section id="liability" heading="10. Limitation of Liability">
                    <P>
                        InsureFlow AI provides the Platform on an "as is" basis for
                        operational assistance only. Final claim decisions rest with
                        the insurer. Our liability is limited to direct losses
                        arising from gross negligence or wilful misconduct on our
                        part, to the extent permitted by applicable law.
                    </P>
                </Section>

                <Section id="governing-law" heading="11. Governing Law & Disputes">
                    <P>
                        These Terms are governed by the laws of India. Disputes
                        shall first be subject to mediation; unresolved disputes
                        shall be referred to the courts of Mumbai, Maharashtra.
                    </P>
                </Section>

                <Section id="changes" heading="12. Changes to These Terms">
                    <P>
                        We may update these Terms when required by law or to
                        reflect changes in our services. We will notify you by email
                        and via an in-app notice at least 14 days before changes
                        take effect. If you do not withdraw consent within that
                        period, continued use constitutes acceptance of the revised
                        Terms.
                    </P>
                </Section>

                <Section id="grievance" heading="13. Grievance Officer (DPDP Act)">
                    <P>
                        In accordance with Section 13 of the DPDP Act and Rule 4 of
                        the DPDP Rules, our designated Grievance Officer is:
                    </P>
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
                    InsureFlow AI · Version 1.0 · Effective 1 January 2026 ·{" "}
                    <a
                        href="/privacy"
                        style={{ color: "var(--blue)", textDecoration: "none" }}
                    >
                        Privacy Policy
                    </a>
                </div>
            </div>
        </div>
    );
}

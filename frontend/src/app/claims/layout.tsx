import DashboardLayout from "@/components/layout/DashboardLayout";

export default function ClaimsLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <DashboardLayout>{children}</DashboardLayout>;
}

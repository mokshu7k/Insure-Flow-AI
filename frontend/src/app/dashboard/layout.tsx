import DashboardLayout from "@/components/layout/DashboardLayout";

export default function DashLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <DashboardLayout>{children}</DashboardLayout>;
}

"use client";
import { LeftRail } from "./LeftRail";

interface CommandLayoutProps {
    children: React.ReactNode;
    rightPanel?: React.ReactNode;
    header?: React.ReactNode;
}

export function CommandLayout({ children, rightPanel, header }: CommandLayoutProps) {
    return (
        <div style={{
            display: "grid",
            gridTemplateColumns: `auto 1fr${rightPanel ? " auto" : ""}`,
            gridTemplateRows: header ? "var(--header-height) 1fr" : "1fr",
            height: "100vh",
            overflow: "hidden",
        }}>
            <LeftRail />

            {header && (
                <div style={{
                    gridColumn: rightPanel ? "2" : "2",
                    gridRow: "1",
                    borderBottom: "1px solid var(--border)",
                    background: "var(--bg-panel)",
                    display: "flex",
                    alignItems: "center",
                    padding: "0 20px",
                    gap: 12,
                    zIndex: 5,
                }}>
                    {header}
                </div>
            )}

            <main style={{
                gridColumn: "2",
                gridRow: header ? "2" : "1 / -1",
                overflowY: "auto",
                background: "var(--bg-base)",
            }}>
                {children}
            </main>

            {rightPanel && (
                <div style={{
                    gridColumn: "3",
                    gridRow: "1 / -1",
                    overflow: "visible",
                    display: "flex",
                    flexDirection: "column",
                }}>
                    {rightPanel}
                </div>
            )}
        </div>
    );
}

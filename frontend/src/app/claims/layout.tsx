import { ClaimAssistantBubble } from "@/components/chat/ClaimAssistantBubble";

export default function ClaimsLayout({ children }: { children: React.ReactNode }) {
    return (
        <>
            {children}
            <ClaimAssistantBubble />
        </>
    );
}

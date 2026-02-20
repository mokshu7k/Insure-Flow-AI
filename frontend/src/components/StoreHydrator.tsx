"use client";
import { useEffect } from "react";
import { useAuthStore } from "@/store/authStore";

/**
 * Triggers Zustand persist rehydration from localStorage after the component
 * mounts on the client. This must run after React finishes hydrating the
 * server-rendered HTML so the initial server/client render remains identical
 * and no hydration mismatch is produced.
 */
export function StoreHydrator() {
    useEffect(() => {
        useAuthStore.persist.rehydrate();
    }, []);
    return null;
}

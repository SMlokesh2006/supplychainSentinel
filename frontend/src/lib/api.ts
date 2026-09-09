export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const fetcher = (url: string) => fetch(API_URL + url).then((res) => {
    if (!res.ok) throw new Error("API error");
    return res.json();
});

export function getStatusDetails(status: string) {
    const s = status || "created";
    switch (s) {
        case "created":
        case "context_gathering":
        case "ready_for_routing":
        case "routes_ready":
        case "evaluating_tier":
            return { label: s.replace(/_/g, " ").toUpperCase(), color: "bg-blue-100 text-blue-800 border-blue-200", dot: "bg-blue-500" };
        case "awaiting_approval":
            return { label: "AWAITING APPROVAL", color: "bg-amber-100 text-amber-800 border-amber-200", dot: "bg-amber-500" };
        case "approved":
            return { label: "APPROVED", color: "bg-purple-100 text-purple-800 border-purple-200", dot: "bg-purple-500" };
        case "auto_executed":
        case "executed":
            return { label: "EXECUTED", color: "bg-green-100 text-green-800 border-green-200", dot: "bg-green-500" };
        case "rejected":
            return { label: "REJECTED", color: "bg-red-100 text-red-800 border-red-200", dot: "bg-red-500" };
        case "error":
            return { label: "ERROR", color: "bg-red-100 text-red-800 border-red-200", dot: "bg-red-500" };
        default:
            return { label: s.toUpperCase(), color: "bg-gray-100 text-gray-800 border-gray-200", dot: "bg-gray-500" };
    }
}

export function saveTrackedThread(threadId: string) {
    if (typeof window === "undefined") return;
    const tracked = JSON.parse(localStorage.getItem("trackedThreads") || "[]");
    if (!tracked.includes(threadId)) {
        tracked.push(threadId);
        localStorage.setItem("trackedThreads", JSON.stringify(tracked));
    }
}

export function getTrackedThreads(): string[] {
    if (typeof window === "undefined") return [];
    return JSON.parse(localStorage.getItem("trackedThreads") || "[]");
}

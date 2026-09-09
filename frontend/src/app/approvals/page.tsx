"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import Link from "next/link";
import { AlertTriangle, Clock, CheckCircle2 } from "lucide-react";

export default function ApprovalsQueue() {
  const { data, error } = useSWR("/cases/pending-approval", fetcher, { refreshInterval: 3000 });

  if (error) return <div className="p-8 text-red-500">Failed to load approvals queue.</div>;
  if (!data) return <div className="p-8 animate-pulse text-gray-500">Loading queue...</div>;

  const pendingList = data.pending_cases || [];

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center justify-between border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Approvals Queue</h1>
          <p className="text-sm text-gray-500 mt-1">High-risk reroutes awaiting human review.</p>
        </div>
        <div className="bg-amber-100 text-amber-800 px-3 py-1 rounded-full text-sm font-bold flex items-center gap-2">
          <Clock className="w-4 h-4" />
          {pendingList.length} Pending
        </div>
      </div>

      {pendingList.length === 0 ? (
        <div className="p-12 bg-white rounded-xl border border-gray-200 text-center shadow-sm">
          <CheckCircle2 className="w-12 h-12 mx-auto text-green-400 mb-3" />
          <h2 className="text-xl font-medium text-gray-900">All caught up</h2>
          <p className="text-gray-500 mt-1">There are no cases requiring human approval right now.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {pendingList.map((c: any) => (
            <Link key={c.thread_id} href={`/cases/${c.thread_id}`} className="block group">
              <div className="bg-white p-6 rounded-xl border border-amber-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6 hover:shadow-md transition-shadow border-l-4 border-l-amber-400">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="font-semibold text-lg text-gray-900 group-hover:text-blue-900 transition-colors">
                      {c.shipment_id}
                    </span>
                    <span className="bg-amber-100 text-amber-800 text-xs font-bold px-2 py-0.5 rounded uppercase tracking-wide flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      Needs Review
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm mt-3 bg-gray-50 p-3 rounded-lg border border-gray-100">
                    <div>
                      <p className="text-gray-500 text-xs uppercase tracking-wider mb-0.5">Recommended Route</p>
                      <p className="font-medium text-gray-900">{c.recommended_carrier}</p>
                    </div>
                    <div>
                      <p className="text-gray-500 text-xs uppercase tracking-wider mb-0.5">Estimated Cost</p>
                      <p className="font-medium text-gray-900">USD {c.recommended_cost?.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-gray-500 text-xs uppercase tracking-wider mb-0.5">Risk Score</p>
                      <p className="font-medium text-amber-700">{c.composite_score}</p>
                    </div>
                  </div>
                </div>
                
                <div className="hidden md:flex">
                  <span className="bg-blue-900 text-white px-5 py-2.5 rounded-lg font-medium text-sm hover:bg-blue-800 transition-colors">
                    Review Case
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

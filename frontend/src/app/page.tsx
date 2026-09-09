"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { Play, Activity, Clock, CheckCircle2, AlertCircle } from "lucide-react";
import { fetcher, API_URL, getStatusDetails, saveTrackedThread, getTrackedThreads } from "@/lib/api";
import Link from "next/link";

export default function Dashboard() {
  const router = useRouter();
  const [triggering, setTriggering] = useState(false);
  const [shipmentId, setShipmentId] = useState("SHP-2026-001");
  const [trackedCases, setTrackedCases] = useState<any[]>([]);
  const [loadingCases, setLoadingCases] = useState(true);

  // Poll pending approvals every 3 seconds
  const { data: pendingData, error: pendingError } = useSWR("/cases/pending-approval", fetcher, { refreshInterval: 3000 });

  // Load tracked threads and fetch details
  useEffect(() => {
    const loadCases = async () => {
      const threads = getTrackedThreads();
      
      // Also add any threads from pending data to tracked
      if (pendingData?.pending_cases) {
        pendingData.pending_cases.forEach((c: any) => saveTrackedThread(c.thread_id));
      }

      const allThreads = getTrackedThreads();
      if (allThreads.length === 0) {
        setLoadingCases(false);
        return;
      }

      try {
        const results = await Promise.all(
          allThreads.map(id => fetch(`${API_URL}/cases/${id}`).then(r => r.ok ? r.json() : null))
        );
        const valid = results.filter(Boolean).map(c => ({
          thread_id: c.thread_id,
          ...c.state
        }));
        
        // Sort by most recent first (using simple array reverse since we append)
        setTrackedCases(valid.reverse());
      } catch (e) {
        console.error(e);
      } finally {
        setLoadingCases(false);
      }
    };

    loadCases();
    const interval = setInterval(loadCases, 3000);
    return () => clearInterval(interval);
  }, [pendingData]);

  const handleReactiveTrigger = async () => {
    setTriggering(true);
    try {
      const res = await fetch(`${API_URL}/cases/trigger/reactive`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shipment_id: shipmentId,
          disruption_description: "Simulated disruption from Dashboard"
        })
      });
      const data = await res.json();
      if (data.thread_id) {
        saveTrackedThread(data.thread_id);
        router.push(`/cases/${data.thread_id}`);
      }
    } catch (e) {
      console.error(e);
      alert("Failed to trigger case");
    } finally {
      setTriggering(false);
    }
  };

  const handleProactiveScan = async () => {
    setTriggering(true);
    try {
      const res = await fetch(`${API_URL}/cases/trigger/proactive-scan`, { method: "POST" });
      const data = await res.json();
      if (data.created_cases && data.created_cases.length > 0) {
        data.created_cases.forEach((c: any) => saveTrackedThread(c.thread_id));
        // Go to the first one
        router.push(`/cases/${data.created_cases[0].thread_id}`);
      } else {
        alert("Scan completed but no active disruptions affected tracked shipments.");
      }
    } catch (e) {
      console.error(e);
      alert("Failed to trigger proactive scan");
    } finally {
      setTriggering(false);
    }
  };

  const stats = {
    total: trackedCases.length,
    pending: pendingData?.count || 0,
    autoExecuted: trackedCases.filter(c => c.status === "auto_executed").length,
    completed: trackedCases.filter(c => ["executed", "auto_executed", "rejected"].includes(c.status)).length
  };

  const pendingList = pendingData?.pending_cases || [];

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Stats row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Active Cases tracked" value={stats.total} icon={<Activity className="w-5 h-5 text-blue-500" />} />
        <StatCard title="Pending Approvals" value={stats.pending} icon={<Clock className="w-5 h-5 text-amber-500" />} alert={stats.pending > 0} />
        <StatCard title="Auto-Executed" value={stats.autoExecuted} icon={<Play className="w-5 h-5 text-purple-500" />} />
        <StatCard title="Completed/Resolved" value={stats.completed} icon={<CheckCircle2 className="w-5 h-5 text-green-500" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          {/* Pending Approvals */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                Action Required
                {pendingList.length > 0 && (
                  <span className="bg-amber-100 text-amber-800 text-xs font-bold px-2 py-0.5 rounded-full">
                    {pendingList.length}
                  </span>
                )}
              </h2>
              <Link href="/approvals" className="text-sm font-medium text-blue-900 hover:underline">View Queue</Link>
            </div>
            
            {pendingError ? (
              <div className="p-4 bg-red-50 text-red-600 rounded-lg border border-red-100">Failed to load pending approvals</div>
            ) : pendingList.length === 0 ? (
              <div className="p-8 bg-white rounded-xl border border-gray-200 text-center text-gray-500 shadow-sm">
                <CheckCircle2 className="w-10 h-10 mx-auto text-green-400 mb-2" />
                <p>No cases awaiting human approval. All clear.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {pendingList.map((c: any) => (
                  <PendingCard key={c.thread_id} caseData={c} />
                ))}
              </div>
            )}
          </section>

          {/* Recent Activity */}
          <section>
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Recent Activity</h2>
            {loadingCases ? (
              <div className="animate-pulse space-y-3">
                {[1,2,3].map(i => <div key={i} className="h-16 bg-gray-100 rounded-xl" />)}
              </div>
            ) : trackedCases.length === 0 ? (
              <div className="p-8 bg-white rounded-xl border border-gray-200 text-center text-gray-500 shadow-sm">
                <p>No recent activity. Trigger a disruption to start.</p>
              </div>
            ) : (
              <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden divide-y divide-gray-100">
                {trackedCases.slice(0, 10).map((c) => (
                  <ActivityRow key={c.thread_id} caseData={c} />
                ))}
              </div>
            )}
          </section>
        </div>

        {/* Demo Control Panel */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden sticky top-24">
            <div className="bg-blue-900 p-4 text-white">
              <h2 className="font-semibold flex items-center gap-2">
                <AlertCircle className="w-5 h-5" />
                Simulate Disruption
              </h2>
              <p className="text-blue-100 text-sm mt-1">Control panel for demo scenarios</p>
            </div>
            <div className="p-5 space-y-6">
              <div className="space-y-3">
                <label className="text-sm font-medium text-gray-700">Target Shipment (Reactive)</label>
                <select 
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                  value={shipmentId}
                  onChange={e => setShipmentId(e.target.value)}
                >
                  <option value="SHP-2026-001">SHP-2026-001 (High Penalty/Value - High Risk)</option>
                  <option value="SHP-2026-005">SHP-2026-005 (Textiles - Low Risk)</option>
                  <option value="SHP-2026-002">SHP-2026-002 (Normal)</option>
                </select>
                <button 
                  onClick={handleReactiveTrigger}
                  disabled={triggering}
                  className="w-full bg-blue-900 hover:bg-blue-800 text-white font-medium py-2 px-4 rounded-lg transition-colors disabled:opacity-50 flex justify-center items-center gap-2"
                >
                  {triggering ? "Triggering..." : "Inject Reactive Alert"}
                </button>
              </div>

              <hr className="border-gray-100" />

              <div className="space-y-3">
                <label className="text-sm font-medium text-gray-700">Proactive Scan</label>
                <p className="text-xs text-gray-500">Polls Risk MCP for active global disruptions and correlates with our lanes.</p>
                <button 
                  onClick={handleProactiveScan}
                  disabled={triggering}
                  className="w-full bg-white border-2 border-blue-900 text-blue-900 hover:bg-blue-50 font-medium py-2 px-4 rounded-lg transition-colors disabled:opacity-50 flex justify-center items-center gap-2"
                >
                  {triggering ? "Scanning..." : "Run Proactive Scan"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon, alert }: { title: string, value: number, icon: React.ReactNode, alert?: boolean }) {
  return (
    <div className={`bg-white p-5 rounded-xl border ${alert ? 'border-amber-300 shadow-amber-100' : 'border-gray-200'} shadow-sm flex items-center justify-between`}>
      <div>
        <p className="text-sm font-medium text-gray-500">{title}</p>
        <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
      </div>
      <div className={`p-3 rounded-full ${alert ? 'bg-amber-50' : 'bg-gray-50'}`}>
        {icon}
      </div>
    </div>
  );
}

function PendingCard({ caseData }: { caseData: any }) {
  return (
    <div className="bg-white p-5 rounded-xl border border-amber-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-l-4 border-l-amber-400">
      <div>
        <div className="flex items-center gap-3 mb-1">
          <span className="font-semibold text-lg text-gray-900">{caseData.shipment_id}</span>
          <span className="bg-amber-100 text-amber-800 text-xs font-bold px-2 py-0.5 rounded uppercase tracking-wide">
            Needs Review
          </span>
        </div>
        <p className="text-sm text-gray-600">
          Recommended <span className="font-medium text-gray-900">{caseData.recommended_carrier}</span> • 
          Est. Cost <span className="font-medium text-gray-900">USD {caseData.recommended_cost?.toLocaleString()}</span> • 
          Score <span className="font-medium text-gray-900">{caseData.composite_score}</span>
        </p>
      </div>
      <Link 
        href={`/cases/${caseData.thread_id}`}
        className="bg-amber-500 hover:bg-amber-600 text-white px-5 py-2 rounded-lg font-medium text-sm transition-colors text-center whitespace-nowrap"
      >
        Review & Approve
      </Link>
    </div>
  );
}

function ActivityRow({ caseData }: { caseData: any }) {
  const statusDef = getStatusDetails(caseData.status);
  
  return (
    <Link href={`/cases/${caseData.thread_id}`} className="block hover:bg-gray-50 transition-colors p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="font-medium text-gray-900 w-32">{caseData.shipment_id || "Unknown"}</div>
          <div className="hidden sm:block text-sm text-gray-500 capitalize">{caseData.trigger_type} trigger</div>
        </div>
        <div className="flex items-center gap-4">
          <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${statusDef.color}`}>
            {statusDef.label}
          </span>
          <div className="text-gray-400">→</div>
        </div>
      </div>
    </Link>
  );
}

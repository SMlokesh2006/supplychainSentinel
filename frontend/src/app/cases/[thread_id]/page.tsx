"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { fetcher, API_URL, getStatusDetails } from "@/lib/api";
import { ArrowRight, Box, MapPin, Package, Settings, AlertTriangle, ShieldCheck, CheckCircle2, XCircle, FileText, ChevronDown, ChevronUp } from "lucide-react";

export default function CaseDetail({ params }: { params: { thread_id: string } }) {
  const { thread_id } = params;
  
  // Poll every 3s to keep state live
  const { data, error, mutate } = useSWR(`/cases/${thread_id}`, fetcher, { refreshInterval: 3000 });
  const { data: detailData, mutate: mutateDetail } = useSWR(
    data?.state?.status === "awaiting_approval" || data?.next?.length > 0 ? `/cases/${thread_id}/approval-detail` : null, 
    fetcher, 
    { refreshInterval: 3000 }
  );

  const [logsExpanded, setLogsExpanded] = useState(false);

  if (error) return <div className="p-8 text-red-500">Failed to load case.</div>;
  if (!data) return <div className="p-8 animate-pulse text-gray-500">Loading case details...</div>;

  // We consider it paused if there is a next node OR if our manual API mapped it to awaiting_approval
  const isAwaiting = data.next?.length > 0;
  
  // Get state
  const state = data.state;
  const status = isAwaiting ? "awaiting_approval" : state.status;
  const statusDef = getStatusDetails(status);

  // We use detailData payload if interrupted, otherwise state itself
  const interruptPayload = detailData?.interrupt_payload;
  const routeOptions = interruptPayload?.route_options || state.route_options || [];
  const recommended = interruptPayload?.recommended_option || state.recommended_option || null;
  const execution = state.execution_result;
  
  // Origin/Dest
  const origin = state.shipment_details?.origin || "Unknown";
  const destination = state.shipment_details?.destination || "Unknown";

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-20">
      {/* Header */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-bold text-gray-900">{state.shipment_id || "Unknown Shipment"}</h1>
            <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${statusDef.color}`}>
              {statusDef.label}
            </span>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <MapPin className="w-4 h-4" />
            <span className="font-medium text-gray-700">{origin}</span>
            <ArrowRight className="w-4 h-4" />
            <span className="font-medium text-gray-700">{destination}</span>
            <span className="mx-2">•</span>
            <Package className="w-4 h-4" />
            <span className="capitalize">{state.trigger_type} trigger</span>
          </div>
        </div>
      </div>

      {/* Step Tracker */}
      <div className="bg-white p-8 rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
        <StepTracker status={status} riskTier={state.risk_tier} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Route Options */}
          {routeOptions.length > 0 && (
            <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">Alternative Routes</h2>
              </div>
              <div className="divide-y divide-gray-100">
                {routeOptions.map((route: any, idx: number) => {
                  const isRec = recommended?.route_id === route.route_id;
                  const isExec = execution?.confirmed_route_id === route.route_id || (state.approval_decision === "approved" && state.recommended_option?.route_id === route.route_id);
                  const isRejected = status === "rejected";
                  
                  let badge = null;
                  let borderClass = "border-transparent";
                  let bgClass = "bg-white";

                  if (isExec) {
                    badge = <span className="bg-green-100 text-green-800 text-xs font-bold px-2 py-0.5 rounded ml-2">EXECUTED</span>;
                    borderClass = "border-l-4 border-l-green-500";
                    bgClass = "bg-green-50/30";
                  } else if (isRec && status === "awaiting_approval") {
                    badge = <span className="bg-blue-100 text-blue-800 text-xs font-bold px-2 py-0.5 rounded ml-2">RECOMMENDED</span>;
                    borderClass = "border-l-4 border-l-blue-500";
                    bgClass = "bg-blue-50/30";
                  } else if (isRec && !isRejected && !isExec) {
                    badge = <span className="bg-gray-100 text-gray-800 text-xs font-bold px-2 py-0.5 rounded ml-2">RECOMMENDED</span>;
                  }

                  return (
                    <div key={idx} className={`p-6 flex flex-col sm:flex-row justify-between gap-4 transition-colors border-l-4 ${borderClass} ${bgClass}`}>
                      <div>
                        <div className="flex items-center mb-1">
                          <span className="font-semibold text-gray-900">{route.carrier}</span>
                          <span className="text-sm text-gray-500 ml-2">({route.route_id})</span>
                          {badge}
                        </div>
                        <p className="text-sm text-gray-600 mb-2">Transit: <span className="font-medium">{route.transit_time_days} days</span></p>
                        <p className="text-sm text-gray-600 italic">"{route.risk_note}"</p>
                      </div>
                      <div className="sm:text-right flex flex-col justify-center">
                        <div className="text-lg font-bold text-gray-900">USD {route.cost.toLocaleString()}</div>
                        <div className="text-xs text-gray-500 mt-1">Score: {route.composite_score}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Raw Log */}
          <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <button 
              onClick={() => setLogsExpanded(!logsExpanded)}
              className="w-full bg-gray-50 px-6 py-4 border-b border-gray-200 flex items-center justify-between hover:bg-gray-100 transition-colors"
            >
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <FileText className="w-5 h-5 text-gray-500" />
                System Audit Log
              </h2>
              {logsExpanded ? <ChevronUp className="w-5 h-5 text-gray-500" /> : <ChevronDown className="w-5 h-5 text-gray-500" />}
            </button>
            {logsExpanded && (
              <div className="p-6 bg-gray-900 text-gray-300 font-mono text-xs overflow-x-auto">
                {state.notes?.map((n: string, i: number) => (
                  <div key={i} className="mb-2 pb-2 border-b border-gray-800 last:border-0 last:mb-0 last:pb-0 whitespace-pre-wrap">
                    {n}
                  </div>
                ))}
                {(!state.notes || state.notes.length === 0) && "No logs available."}
              </div>
            )}
          </section>
        </div>

        {/* Right Column: Reasoning & Actions */}
        <div className="space-y-6">
          {/* Reasoning Panel */}
          <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">Decision Context</h3>
            
            <div className="space-y-4">
              <div>
                <p className="text-xs text-gray-500 mb-1">Risk Tier Evaluated</p>
                {state.risk_tier ? (
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-sm font-semibold ${state.risk_tier === 'high' ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-800'}`}>
                    {state.risk_tier === 'high' ? <AlertTriangle className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
                    {state.risk_tier.toUpperCase()} RISK
                  </span>
                ) : <span className="text-sm text-gray-400">Pending</span>}
              </div>

              {state.autonomy_threshold_used && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">Autonomy Threshold (Score)</p>
                  <p className="text-sm font-medium text-gray-900">{state.autonomy_threshold_used}</p>
                </div>
              )}

              {interruptPayload?.risk_reasoning && (
                <div className="bg-amber-50 p-3 rounded-lg border border-amber-100">
                  <p className="text-xs text-amber-800 font-medium">{interruptPayload.risk_reasoning.replace(/\[.*?\] /, '')}</p>
                </div>
              )}
            </div>
          </section>

          {/* Approval Panel */}
          {isAwaiting && interruptPayload && (
            <ApprovalPanel 
              threadId={thread_id} 
              payload={interruptPayload} 
              onComplete={() => { mutate(); mutateDetail(); }} 
            />
          )}

          {/* Execution Result */}
          {execution && (
             <section className="bg-green-50 rounded-xl shadow-sm border border-green-200 p-6">
               <div className="flex items-center gap-2 text-green-800 font-semibold mb-3">
                 <CheckCircle2 className="w-5 h-5" />
                 Booking Confirmed
               </div>
               <div className="space-y-2 text-sm text-green-900">
                 <p><span className="opacity-70">ID:</span> <span className="font-medium">{execution.booking_id}</span></p>
                 <p><span className="opacity-70">Carrier:</span> <span className="font-medium">{execution.confirmed_carrier}</span></p>
                 <p><span className="opacity-70">Cost:</span> <span className="font-medium">USD {execution.confirmed_cost_usd?.toLocaleString()}</span></p>
                 <p><span className="opacity-70">Delivery:</span> <span className="font-medium">{execution.confirmed_delivery_date}</span></p>
               </div>
             </section>
          )}

          {status === "rejected" && (
             <section className="bg-red-50 rounded-xl shadow-sm border border-red-200 p-6">
               <div className="flex items-center gap-2 text-red-800 font-semibold mb-3">
                 <XCircle className="w-5 h-5" />
                 Reroute Rejected
               </div>
               <p className="text-sm text-red-900">
                 The recommended reroute was rejected by <b>{state.approved_by}</b>. No booking was created.
               </p>
             </section>
          )}

        </div>
      </div>
    </div>
  );
}

function ApprovalPanel({ threadId, payload, onComplete }: { threadId: string, payload: any, onComplete: () => void }) {
  const [approver, setApprover] = useState("Logistics Operator");
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleApprove = async () => {
    setSubmitting(true);
    try {
      await fetch(`${API_URL}/cases/${threadId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved_by: approver, selected_option_index: selectedIdx })
      });
      onComplete();
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!reason) { alert("Please provide a reason for rejection"); return; }
    setSubmitting(true);
    try {
      await fetch(`${API_URL}/cases/${threadId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved_by: approver, reason })
      });
      onComplete();
    } finally {
      setSubmitting(false);
    }
  };

  // Find index of recommended option
  useEffect(() => {
    if (payload?.route_options && payload?.recommended_option) {
      const idx = payload.route_options.findIndex((r: any) => r.route_id === payload.recommended_option.route_id);
      if (idx >= 0) setSelectedIdx(idx);
    }
  }, [payload]);

  return (
    <section className="bg-amber-50 rounded-xl shadow-sm border border-amber-300 p-6 animate-in slide-in-from-bottom-4 duration-500">
      <h2 className="text-lg font-bold text-amber-900 mb-4 flex items-center gap-2">
        <AlertTriangle className="w-5 h-5" />
        Human Review Required
      </h2>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-amber-900 mb-1">Approver Name</label>
          <input 
            type="text" 
            value={approver} 
            onChange={e => setApprover(e.target.value)}
            className="w-full px-3 py-2 border border-amber-200 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm bg-white"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-amber-900 mb-1">Select Route to Execute</label>
          <select 
            value={selectedIdx} 
            onChange={e => setSelectedIdx(Number(e.target.value))}
            className="w-full px-3 py-2 border border-amber-200 rounded-md shadow-sm focus:ring-amber-500 focus:border-amber-500 sm:text-sm bg-white"
          >
            {payload?.route_options?.map((r: any, i: number) => (
              <option key={r.route_id} value={i}>
                {r.carrier} (USD {r.cost}) - {r.transit_time_days}d {payload.recommended_option?.route_id === r.route_id ? '★ REC' : ''}
              </option>
            ))}
          </select>
        </div>

        <button 
          onClick={handleApprove}
          disabled={submitting}
          className="w-full bg-amber-600 hover:bg-amber-700 text-white font-medium py-2.5 px-4 rounded-lg shadow-sm transition-colors disabled:opacity-50"
        >
          {submitting ? "Processing..." : "Approve & Execute"}
        </button>

        <div className="pt-4 border-t border-amber-200/60 space-y-3">
          <input 
            type="text" 
            placeholder="Reason for rejection (required)"
            value={reason}
            onChange={e => setReason(e.target.value)}
            className="w-full px-3 py-2 border border-amber-200 rounded-md shadow-sm focus:ring-red-500 focus:border-red-500 sm:text-sm bg-white"
          />
          <button 
            onClick={handleReject}
            disabled={submitting}
            className="w-full bg-white border border-red-200 text-red-600 hover:bg-red-50 font-medium py-2 px-4 rounded-lg transition-colors disabled:opacity-50"
          >
            Reject Reroute
          </button>
        </div>
      </div>
    </section>
  );
}

// Very simple static step tracker based on status strings
function StepTracker({ status, riskTier }: { status: string, riskTier?: string }) {
  const steps = [
    { key: "ingest", label: "Signal Ingested", active: true },
    { key: "context", label: "Context Gathered", active: !["created", "context_gathering"].includes(status) },
    { key: "routes", label: "Routes Generated", active: !["created", "context_gathering", "ready_for_routing"].includes(status) },
    { key: "tier", label: "Tiered Autonomy Check", active: !["created", "context_gathering", "ready_for_routing", "routes_ready"].includes(status) },
  ];

  let finalStep = { key: "exec", label: "Auto-Executed", active: status === "auto_executed", color: "green" };
  
  if (riskTier === "high" || ["awaiting_approval", "approved", "rejected", "executed"].includes(status)) {
    if (status === "awaiting_approval") finalStep = { key: "exec", label: "Awaiting Approval", active: true, color: "amber" };
    else if (status === "rejected") finalStep = { key: "exec", label: "Rejected", active: true, color: "red" };
    else if (["approved", "executed"].includes(status)) finalStep = { key: "exec", label: "Executed (Approved)", active: true, color: "purple" };
    else finalStep = { key: "exec", label: "Pending Review", active: false, color: "gray" };
  }

  const allSteps = [...steps, finalStep];

  return (
    <div className="flex items-center justify-between min-w-[600px]">
      {allSteps.map((step, idx) => {
        const isLast = idx === allSteps.length - 1;
        const color = step.active ? (step.color === 'amber' ? 'bg-amber-500' : step.color === 'red' ? 'bg-red-500' : step.color === 'purple' ? 'bg-purple-600' : 'bg-blue-600') : 'bg-gray-200';
        const textColor = step.active ? 'text-gray-900 font-semibold' : 'text-gray-400';
        
        return (
          <div key={step.key} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center relative z-10 w-32">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${color} text-white shadow-sm transition-colors duration-500`}>
                {step.active && step.key !== 'exec' ? <CheckCircle2 className="w-5 h-5" /> : (idx + 1)}
              </div>
              <span className={`text-xs mt-3 text-center transition-colors duration-500 ${textColor}`}>
                {step.label}
              </span>
            </div>
            {!isLast && (
              <div className="flex-1 h-1 mx-[-1rem] bg-gray-200 relative top-[-10px] z-0">
                <div className={`h-full transition-all duration-1000 ${allSteps[idx+1].active ? 'bg-blue-600' : 'bg-transparent'}`} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

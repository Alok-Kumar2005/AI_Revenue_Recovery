"use client";

// src/app/cases/[id]/page.tsx — Case Detail with Audit Trail

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { fetchCaseDetail } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";
import CaseTimeline from "@/components/CaseTimeline";

function Skeleton() {
  return (
    <div className="mx-auto max-w-7xl px-5 py-8 space-y-6 animate-pulse">
      <div className="skeleton h-5 w-48 rounded" />
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="card space-y-3">
            {[...Array(5)].map((_, i) => <div key={i} className="skeleton h-4 w-full rounded" />)}
          </div>
          <div className="card space-y-3">
            {[...Array(3)].map((_, i) => <div key={i} className="skeleton h-4 w-full rounded" />)}
          </div>
        </div>
        <div className="lg:col-span-3">
          <div className="card space-y-4">
            {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-16 w-full rounded" />)}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    fetchCaseDetail(id)
      .then(setCaseDetail)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load case details")
      )
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <Skeleton />;

  if (error || !caseDetail) {
    return (
      <div className="mx-auto max-w-7xl px-5 py-8">
        <div className="card text-center py-16">
          <p className="text-red-400 font-medium mb-2">Failed to load case</p>
          <p className="text-sm text-slate-500 mb-4">{error}</p>
          <button
            onClick={() => router.back()}
            className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            Go back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-5 py-8 space-y-6 animate-fade-in">
      {/* Breadcrumb / back */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft size={14} />
          All Cases
        </button>

        <a
          href={`http://localhost:8000/api/cases/${id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          View raw JSON <ExternalLink size={11} />
        </a>
      </div>

      {/* Case heading */}
      <div>
        <h1 className="text-xl font-bold text-slate-100 tracking-tight">
          Case Detail
        </h1>
        <p className="text-xs text-slate-500 font-mono mt-0.5">{id}</p>
      </div>

      {/* Timeline */}
      <CaseTimeline caseDetail={caseDetail} />
    </div>
  );
}

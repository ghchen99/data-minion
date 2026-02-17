"use client";

import React, { useEffect, useState } from "react";
import { Table, Layout, FileText, BarChart3, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ArtifactResultProps {
    artifactId: string;
}

export function ArtifactResult({ artifactId }: ArtifactResultProps) {
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function fetchArtifact() {
            setLoading(true);
            try {
                const response = await fetch(`http://localhost:8000/artifacts/${artifactId}`);
                if (!response.ok) throw new Error("Failed to fetch artifact");
                const result = await response.json();
                setData(result);
            } catch (err: any) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        }
        fetchArtifact();
    }, [artifactId]);

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8 bg-slate-50/50 rounded-xl border border-dashed border-slate-200 animate-pulse">
                <div className="flex flex-col items-center gap-2">
                    <div className="w-8 h-8 rounded-full border-2 border-minionBlue border-t-transparent animate-spin" />
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Loading Artifact...</span>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-4 bg-red-50 rounded-xl border border-red-100 flex items-center gap-3 text-red-600">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <p className="text-sm font-medium">{error}</p>
            </div>
        );
    }

    const isChart = artifactId.startsWith("chart_") || data?.type === "chart" || data?.image_path;

    return (
        <div className="group relative bg-white rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden hover:shadow-[0_20px_40px_rgb(0,0,0,0.08)] transition-all duration-500 animate-in fade-in slide-in-from-bottom-4">
            {/* Top Bar Accent */}
            <div className={cn(
                "h-1.5 w-full",
                isChart ? "bg-gradient-to-r from-minionBlue to-blue-400" : "bg-gradient-to-r from-minionYellow via-orange-300 to-minionYellow"
            )} />

            {/* Header / Meta */}
            <div className="px-5 py-3 border-b border-slate-50 bg-slate-50/50 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                    <div className={cn(
                        "p-1.5 rounded-lg shadow-sm border",
                        isChart ? "bg-blue-50 border-blue-100 text-minionBlue" : "bg-amber-50 border-amber-100 text-amber-600"
                    )}>
                        {isChart ? <BarChart3 className="w-4 h-4" /> : <Table className="w-4 h-4" />}
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest leading-none mb-0.5">
                            Artifact ID
                        </span>
                        <span className="text-xs font-bold text-slate-700 truncate max-w-[250px]">
                            {artifactId}
                        </span>
                    </div>
                </div>
                <div className={cn(
                    "text-[9px] font-black px-2.5 py-1 rounded-full shadow-sm border uppercase tracking-wider",
                    isChart ? "bg-blue-600 text-white border-blue-700" : "bg-white text-slate-500 border-slate-200"
                )}>
                    {isChart ? "Visualization" : "Dataset Artifact"}
                </div>
            </div>

            <div className="p-6">
                {isChart ? (
                    <div className="relative group/img rounded-2xl overflow-hidden border border-slate-100 shadow-2xl bg-white">
                        <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent opacity-0 group-hover/img:opacity-100 transition-opacity duration-300 z-10 pointer-events-none" />
                        <img
                            src={`http://localhost:8000${data.image_path}`}
                            alt={artifactId}
                            className="w-full h-auto rounded-xl transition-transform duration-700 ease-out group-hover/img:scale-[1.03]"
                        />
                    </div>
                ) : data?.sample_data ? (
                    <div className="flex flex-col gap-4">
                        <div className="overflow-x-auto rounded-2xl border border-slate-200 shadow-xl bg-white custom-scrollbar">
                            <table className="w-full text-left border-collapse min-w-[600px]">
                                <thead>
                                    <tr className="bg-slate-900 border-b-2 border-slate-800">
                                        {data.columns?.map((col: string) => (
                                            <th key={col} className="px-4 py-3 text-[10px] font-black text-slate-300 uppercase tracking-widest truncate">
                                                {col}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.sample_data.map((row: any, rIdx: number) => (
                                        <tr key={rIdx} className="group/row border-b last:border-0 border-slate-100 hover:bg-minionYellow/10 transition-colors">
                                            {data.columns?.map((col: string) => (
                                                <td key={col} className="px-4 py-3 text-[13px] text-slate-600 font-medium group-hover/row:text-slate-900 transition-colors">
                                                    {row[col] === null || row[col] === undefined ? (
                                                        <span className="text-slate-300 italic text-[10px]">null</span>
                                                    ) : typeof row[col] === 'number' ? (
                                                        <span className="font-mono text-minionBlue font-bold">{row[col].toLocaleString()}</span>
                                                    ) : (
                                                        String(row[col])
                                                    )}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        <div className="flex items-center justify-between px-2">
                            <div className="flex items-center gap-2">
                                <Layout className="w-3.5 h-3.5 text-slate-400" />
                                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">
                                    Preview: {data.sample_data.length} rows • {data.columns?.length} columns
                                </span>
                            </div>
                            {data.metadata?.row_count && (
                                <span className="text-[10px] bg-slate-100 text-slate-500 font-black px-2 py-0.5 rounded uppercase tracking-tighter">
                                    Total {data.metadata.row_count} rows
                                </span>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="py-16 text-center bg-slate-50/50 rounded-2xl border-2 border-dashed border-slate-200 flex flex-col items-center justify-center">
                        <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center mb-4 shadow-sm border border-slate-100">
                            <FileText className="w-8 h-8 text-slate-200" />
                        </div>
                        <p className="text-xs font-black text-slate-400 uppercase tracking-widest">No data preview generated</p>
                        <p className="text-[10px] text-slate-300 mt-1 uppercase font-bold tabular-nums italic">Check artifact JSON for details</p>
                    </div>
                )}
            </div>
        </div>
    );
}

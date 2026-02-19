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
            <div className="flex items-center justify-center p-8 bg-zinc-900 rounded-xl border border-dashed border-zinc-700 animate-pulse">
                <div className="flex flex-col items-center gap-2">
                    <div className="w-8 h-8 rounded-full border-2 border-zinc-400 border-t-transparent animate-spin" />
                    <span className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">Loading Artifact...</span>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-4 bg-red-950/40 rounded-xl border border-red-900/60 flex items-center gap-3 text-red-400">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <p className="text-sm font-medium">{error}</p>
            </div>
        );
    }

    const isChart = artifactId.startsWith("chart_") || data?.type === "chart" || data?.image_path;

    return (
        <div className="group relative bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden transition-all duration-300 animate-in fade-in slide-in-from-bottom-4">
            {/* Top accent bar */}
            <div className={cn(
                "h-px w-full",
                isChart ? "bg-zinc-600" : "bg-zinc-700"
            )} />

            {/* Header */}
            <div className="px-4 py-3 border-b border-zinc-800 bg-zinc-900/80 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                    <div className={cn(
                        "p-1.5 rounded-lg border",
                        isChart
                            ? "bg-zinc-800 border-zinc-700 text-zinc-400"
                            : "bg-zinc-800 border-zinc-700 text-zinc-400"
                    )}>
                        {isChart ? <BarChart3 className="w-3.5 h-3.5" /> : <Table className="w-3.5 h-3.5" />}
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[9px] font-semibold text-zinc-600 uppercase tracking-widest leading-none mb-0.5">
                            Artifact ID
                        </span>
                        <span className="text-xs font-medium text-zinc-300 truncate max-w-[250px]">
                            {artifactId}
                        </span>
                    </div>
                </div>
                <div className="text-[9px] font-semibold px-2.5 py-1 rounded-md bg-zinc-800 text-zinc-500 border border-zinc-700 uppercase tracking-wider">
                    {isChart ? "Visualization" : "Dataset Artifact"}
                </div>
            </div>

            <div className="p-4">
                {isChart ? (
                    <div className="rounded-lg overflow-hidden border border-zinc-800 bg-zinc-950">
                        <img
                            src={`http://localhost:8000${data.image_path}`}
                            alt={artifactId}
                            className="w-full h-auto"
                        />
                    </div>
                ) : data?.sample_data ? (
                    <div className="flex flex-col gap-3">
                        <div className="overflow-x-auto rounded-lg border border-zinc-800">
                            <table className="w-full text-left border-collapse min-w-[600px]">
                                <thead>
                                    <tr className="bg-zinc-800 border-b border-zinc-700">
                                        {data.columns?.map((col: string) => (
                                            <th key={col} className="px-4 py-2.5 text-[10px] font-bold text-zinc-400 uppercase tracking-widest">
                                                {col}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.sample_data.map((row: any, rIdx: number) => (
                                        <tr key={rIdx} className="border-b last:border-0 border-zinc-800/80 hover:bg-zinc-800/40 transition-colors">
                                            {data.columns?.map((col: string) => (
                                                <td key={col} className="px-4 py-2.5 text-[13px] text-zinc-400">
                                                    {row[col] === null || row[col] === undefined ? (
                                                        <span className="text-zinc-700 italic text-[10px]">null</span>
                                                    ) : typeof row[col] === 'number' ? (
                                                        <span className="font-mono text-zinc-200 font-semibold">{row[col].toLocaleString()}</span>
                                                    ) : (
                                                        <span className="text-zinc-300">{String(row[col])}</span>
                                                    )}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        <div className="flex items-center justify-between px-1">
                            <div className="flex items-center gap-2">
                                <Layout className="w-3 h-3 text-zinc-600" />
                                <span className="text-[10px] text-zinc-600 font-medium uppercase tracking-widest">
                                    Preview: {data.sample_data.length} rows • {data.columns?.length} columns
                                </span>
                            </div>
                            {data.metadata?.row_count && (
                                <span className="text-[10px] bg-zinc-800 text-zinc-500 font-semibold px-2 py-0.5 rounded border border-zinc-700 uppercase tracking-tighter">
                                    Total {data.metadata.row_count} rows
                                </span>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="py-12 text-center bg-zinc-950/50 rounded-lg border border-dashed border-zinc-800 flex flex-col items-center justify-center">
                        <FileText className="w-8 h-8 text-zinc-700 mb-3" />
                        <p className="text-xs font-semibold text-zinc-600 uppercase tracking-widest">No data preview available</p>
                    </div>
                )}
            </div>
        </div>
    );
}
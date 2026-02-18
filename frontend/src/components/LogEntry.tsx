"use client";

import React from "react";
import {
    CheckCircle2,
    Code,
    Terminal,
    Search,
    Info,
    BarChart3,
    HelpCircle,
    FileJson,
    Activity,
    ArrowRight
} from "lucide-react";
import { cn } from "@/lib/utils";

interface LogEntryProps {
    data: any;
}

const nodeConfig: Record<string, { icon: any; color: string; label: string }> = {
    mark_complete: { icon: CheckCircle2, color: "text-emerald-400", label: "Step Complete" },
    route_tool: { icon: Search, color: "text-violet-400", label: "Routing Tool" },
    reformulate_prompt: { icon: HelpCircle, color: "text-sky-400", label: "Reformulating" },
    generate_code: { icon: Code, color: "text-amber-400", label: "Generating Code" },
    execute_code: { icon: Terminal, color: "text-zinc-300", label: "Executing Code" },
    validate_schema: { icon: Info, color: "text-teal-400", label: "Validating Schema" },
    register_artifacts: { icon: BarChart3, color: "text-indigo-400", label: "Registering Artifacts" },
    generate_summary: { icon: FileJson, color: "text-blue-400", label: "Summary" },
    fix_code: { icon: Code, color: "text-red-400", label: "Fixing Code" },
};

export function LogEntry({ data }: LogEntryProps) {
    if (data.status_update) {
        return (
            <div className="flex items-start gap-2 px-2 py-1.5 animate-in fade-in slide-in-from-left-2 duration-300">
                <Activity className="w-3 h-3 text-zinc-600 mt-0.5 flex-shrink-0" />
                <p className="text-[11px] text-zinc-400 leading-relaxed">{data.status_update.status}</p>
            </div>
        );
    }

    if (data.updates) {
        return (
            <div className="space-y-1">
                {data.updates.map((update: any, idx: number) => {
                    const config = nodeConfig[update.node] || {
                        icon: Activity,
                        color: "text-zinc-500",
                        label: update.node,
                    };
                    const Icon = config.icon;

                    return (
                        <div
                            key={idx}
                            className="flex flex-col gap-2 px-2 py-2.5 rounded-lg bg-zinc-800/40 border border-zinc-800 animate-in fade-in duration-200"
                        >
                            {/* Node label */}
                            <div className="flex items-center gap-2">
                                <Icon className={cn("w-3.5 h-3.5 flex-shrink-0", config.color)} />
                                <span className={cn("text-[10px] font-bold uppercase tracking-widest", config.color)}>
                                    {config.label}
                                </span>
                            </div>

                            {/* Messages */}
                            {update.messages && update.messages.length > 0 && (
                                <div className="flex flex-col gap-0.5 pl-5">
                                    {update.messages.map((msg: string, mIdx: number) => (
                                        <p key={mIdx} className="text-[11px] text-zinc-400 leading-relaxed">
                                            {msg}
                                        </p>
                                    ))}
                                </div>
                            )}

                            {/* Code block */}
                            {update.python_code && (
                                <div className="rounded-md overflow-hidden border border-zinc-700 ml-5">
                                    <div className="bg-zinc-800 px-3 py-1 flex items-center justify-between">
                                        <span className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">Python</span>
                                        <Code className="w-3 h-3 text-zinc-600" />
                                    </div>
                                    <pre className="p-3 bg-zinc-950 text-[10px] text-emerald-400/80 font-mono overflow-x-auto whitespace-pre leading-relaxed">
                                        {update.python_code}
                                    </pre>
                                </div>
                            )}

                            {/* Artifact tags */}
                            {update.artifacts && update.artifacts.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 pl-5">
                                    {update.artifacts.map((art: string, aIdx: number) => (
                                        <span
                                            key={aIdx}
                                            className="inline-flex items-center px-2 py-0.5 rounded text-[9px] font-mono text-zinc-500 bg-zinc-800 border border-zinc-700"
                                        >
                                            <ArrowRight className="w-2 h-2 mr-1 opacity-50" />
                                            {art}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        );
    }

    return null;
}
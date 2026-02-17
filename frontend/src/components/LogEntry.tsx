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

const nodeConfig: Record<string, { icon: any, color: string, bgColor: string, label: string }> = {
    mark_complete: { icon: CheckCircle2, color: "text-green-600", bgColor: "bg-green-50", label: "Step Complete" },
    route_tool: { icon: Search, color: "text-purple-600", bgColor: "bg-purple-50", label: "Routing Tool" },
    reformulate_prompt: { icon: HelpCircle, color: "text-blue-600", bgColor: "bg-blue-50", label: "Reformulating" },
    generate_code: { icon: Code, color: "text-orange-600", bgColor: "bg-orange-50", label: "Generating Code" },
    execute_code: { icon: Terminal, color: "text-slate-700", bgColor: "bg-slate-50", label: "Executing Code" },
    validate_schema: { icon: Info, color: "text-teal-600", bgColor: "bg-teal-50", label: "Validating Schema" },
    register_artifacts: { icon: BarChart3, color: "text-indigo-600", bgColor: "bg-indigo-50", label: "Registering Artifacts" },
    generate_summary: { icon: FileJson, color: "text-blue-700", bgColor: "bg-blue-50", label: "Summary" },
    fix_code: { icon: Code, color: "text-red-600", bgColor: "bg-red-50", label: "Fixing Code" },
};

export function LogEntry({ data }: LogEntryProps) {
    if (data.status_update) {
        return (
            <div className="flex items-start gap-3 p-3 mb-3 bg-white border-l-4 border-minionBlue rounded-r-lg shadow-sm animate-in fade-in slide-in-from-left-2 duration-300">
                <div className="mt-1 p-1.5 bg-blue-50 rounded-full">
                    <Activity className="w-4 h-4 text-minionBlue" />
                </div>
                <div>
                    <p className="text-sm font-medium text-slate-800">{data.status_update.status}</p>
                </div>
            </div>
        );
    }

    if (data.updates) {
        return (
            <div className="space-y-3">
                {data.updates.map((update: any, idx: number) => {
                    const config = nodeConfig[update.node] || {
                        icon: Activity,
                        color: "text-slate-500",
                        bgColor: "bg-slate-100",
                        label: update.node
                    };
                    const Icon = config.icon;

                    return (
                        <div
                            key={idx}
                            className={cn(
                                "group relative overflow-hidden flex flex-col gap-2 p-4 mb-4 border rounded-xl shadow-sm transition-all hover:shadow-md",
                                config.bgColor,
                                "border-slate-200"
                            )}
                        >
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className={cn("p-2 rounded-lg", config.color, "bg-white border border-current opacity-80")}>
                                        <Icon className="w-5 h-5" />
                                    </div>
                                    <span className={cn("font-bold text-sm tracking-wide uppercase", config.color)}>
                                        {config.label}
                                    </span>
                                </div>
                            </div>

                            {update.messages && update.messages.length > 0 && (
                                <div className="flex flex-col gap-1 mt-1">
                                    {update.messages.map((msg: string, mIdx: number) => (
                                        <p key={mIdx} className="text-sm text-slate-700 leading-relaxed font-medium">
                                            {msg}
                                        </p>
                                    ))}
                                </div>
                            )}

                            {update.python_code && (
                                <div className="mt-2 rounded-lg overflow-hidden border border-slate-200 shadow-inner">
                                    <div className="bg-slate-800 px-3 py-1.5 flex items-center justify-between">
                                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Python Code</span>
                                        <Code className="w-3 h-3 text-slate-400" />
                                    </div>
                                    <pre className="p-4 bg-slate-900 text-xs text-blue-300 font-mono overflow-x-auto whitespace-pre leading-relaxed">
                                        {update.python_code}
                                    </pre>
                                </div>
                            )}

                            {update.artifacts && update.artifacts.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2 pt-2 border-t border-slate-200/50">
                                    {update.artifacts.map((art: string, aIdx: number) => (
                                        <span
                                            key={aIdx}
                                            className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-white text-slate-500 border border-slate-200"
                                        >
                                            <ArrowRight className="w-2.5 h-2.5 mr-1 opacity-50" />
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

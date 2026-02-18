"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LogEntry } from "@/components/LogEntry";
import { ArtifactResult } from "@/components/ArtifactResult";
import {
  FileUp,
  Sparkles,
  Loader2,
  Activity,
  ChevronRight,
  FileText,
  BarChart3,
  Table as TableIcon,
  RotateCcw,
  Search,
  Terminal,
  CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Tab = "summary" | "charts" | "tables";

export default function HomePage() {
  const [prompt, setPrompt] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [artifacts, setArtifacts] = useState<any[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [isStarted, setIsStarted] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("charts");
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTo({
        top: logContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [logs]);

  const groupedArtifacts = useMemo(() => {
    const figures = artifacts.filter((a) => a.startsWith("chart_"));
    const tables = artifacts.filter((a) => !a.startsWith("chart_"));
    return { figures, tables };
  }, [artifacts]);

  const handleUpload = async () => {
    if (!file || !prompt) return alert("Select a CSV and enter a prompt");

    setLogs([]);
    setArtifacts([]);
    setSummary(null);
    setStreaming(true);
    setIsStarted(true);
    setActiveTab("charts");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("prompt", prompt);

    try {
      const response = await fetch("http://localhost:8000/upload-and-run-stream", {
        method: "POST",
        body: formData,
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let done = false;
      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        const chunk = decoder.decode(value);
        chunk.split("\n").forEach((line) => {
          if (line) {
            try {
              const data = JSON.parse(line);
              if (data.updates || data.status_update) setLogs((prev) => [...prev, data]);
              if (data.all_artifacts) setArtifacts(data.all_artifacts);
              if (data.final_summary) {
                setSummary(data.final_summary);
                setActiveTab("summary");
              }
            } catch (e) { }
          }
        });
      }
    } catch (e) {
      console.error("Upload error:", e);
    } finally {
      setStreaming(false);
    }
  };

  const reset = () => {
    setIsStarted(false);
    setLogs([]);
    setArtifacts([]);
    setSummary(null);
    setPrompt("");
    setFile(null);
  };

  // ── Landing Page ──────────────────────────────────────────────────────────
  if (!isStarted) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6 relative overflow-hidden">
        {/* Subtle grid */}
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />
        {/* Radial glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[500px] bg-zinc-800/60 rounded-full blur-[120px] pointer-events-none" />

        <div className="relative max-w-xl w-full space-y-8 animate-in fade-in slide-in-from-bottom-6 duration-700">
          {/* Badge */}
          <div className="flex justify-center">
            <div className="inline-flex items-center gap-2 bg-zinc-800/80 border border-zinc-700/60 px-3.5 py-1.5 rounded-full text-zinc-400">
              <Sparkles className="w-3 h-3 fill-zinc-400" />
              <span className="text-[10px] font-semibold uppercase tracking-[0.2em]">Data Minion v1.0</span>
            </div>
          </div>

          {/* Heading */}
          <div className="text-center space-y-3">
            <h1 className="text-5xl md:text-6xl font-black text-white tracking-tight leading-[1.05]">
              Ask questions
              <br />
              <span className="text-zinc-400">about your data.</span>
            </h1>
            <p className="text-zinc-500 text-sm max-w-xs mx-auto leading-relaxed">
              Upload a CSV, describe what you want. The agent writes code and returns charts and insights.
            </p>
          </div>

          {/* Card */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4">
            {/* File input */}
            <div className="space-y-2">
              <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.18em]">
                Dataset
              </label>
              <div className="relative">
                <Input
                  type="file"
                  accept=".csv"
                  className="h-11 cursor-pointer bg-zinc-800/60 border-zinc-700/60 text-zinc-300 rounded-xl
                    file:mr-4 file:py-1 file:px-3 file:rounded-lg file:border-0
                    file:text-xs file:font-semibold file:bg-zinc-700 file:text-zinc-300
                    hover:file:bg-zinc-600 focus-visible:ring-zinc-500 transition-all"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
                {!file && (
                  <FileUp className="absolute right-3.5 top-3 w-4 h-4 text-zinc-600 pointer-events-none" />
                )}
              </div>
              {file && (
                <p className="text-[11px] text-emerald-400 flex items-center gap-1.5 ml-1">
                  <CheckCircle2 className="w-3 h-3" />
                  {file.name}
                </p>
              )}
            </div>

            {/* Prompt */}
            <div className="space-y-2">
              <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.18em]">
                Question
              </label>
              <div className="relative">
                <Search className="absolute left-3.5 top-3 w-4 h-4 text-zinc-600 pointer-events-none" />
                <Input
                  type="text"
                  placeholder="e.g. Show me the top 10 products by revenue"
                  value={prompt}
                  className="h-11 pl-10 bg-zinc-800/60 border-zinc-700/60 text-zinc-200 placeholder:text-zinc-600
                    rounded-xl focus-visible:ring-zinc-500 focus-visible:border-zinc-500 transition-all"
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleUpload()}
                />
              </div>
            </div>

            {/* CTA */}
            <Button
              onClick={handleUpload}
              disabled={!file || !prompt}
              className="w-full h-11 bg-white hover:bg-zinc-100 text-zinc-900 font-semibold rounded-xl
                disabled:opacity-20 disabled:cursor-not-allowed transition-all group text-sm"
            >
              Run Analysis
              <ChevronRight className="w-4 h-4 ml-1.5 group-hover:translate-x-0.5 transition-transform" />
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // ── Dashboard ─────────────────────────────────────────────────────────────
  const tabs: { id: Tab; label: string; icon: React.ReactNode; count?: number }[] = [
    {
      id: "summary",
      label: "Summary",
      icon: <FileText className="w-3.5 h-3.5" />,
    },
    {
      id: "charts",
      label: "Charts",
      icon: <BarChart3 className="w-3.5 h-3.5" />,
      count: groupedArtifacts.figures.length || undefined,
    },
    {
      id: "tables",
      label: "Tables",
      icon: <TableIcon className="w-3.5 h-3.5" />,
      count: groupedArtifacts.tables.length || undefined,
    },
  ];

  return (
    <div className="h-screen bg-zinc-950 flex flex-col overflow-hidden text-zinc-100">
      {/* Header */}
      <header className="h-14 border-b border-zinc-800/80 flex items-center justify-between px-5 flex-shrink-0 bg-zinc-900/90 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-zinc-800 border border-zinc-700 rounded-lg flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5 text-zinc-300 fill-zinc-300" />
          </div>
          <span className="text-sm font-semibold text-zinc-200">Data Minion</span>
          <span className="text-zinc-700">·</span>
          <span className="text-sm text-zinc-500 truncate max-w-xs hidden sm:block">"{prompt}"</span>
        </div>

        <div className="flex items-center gap-3">
          {streaming && (
            <div className="flex items-center gap-2 text-zinc-400 text-xs font-medium">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Running</span>
            </div>
          )}
          {!streaming && isStarted && (
            <div className="flex items-center gap-1.5 text-emerald-400 text-xs font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Complete</span>
            </div>
          )}
          <button
            onClick={reset}
            className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors border border-zinc-700/60 hover:border-zinc-600 px-3 py-1.5 rounded-lg"
          >
            <RotateCcw className="w-3 h-3" />
            New
          </button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* ── Left: Terminal Log ─────────────────────────────────────────── */}
        <aside className="w-72 xl:w-80 flex-shrink-0 border-r border-zinc-800/80 flex flex-col bg-zinc-900/50 hidden md:flex">
          {/* Log header */}
          <div className="h-10 flex items-center gap-2 px-4 border-b border-zinc-800/80">
            <Terminal className="w-3.5 h-3.5 text-zinc-600" />
            <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">
              Execution Log
            </span>
            {streaming && (
              <div className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            )}
          </div>

          {/* Log entries */}
          <div
            ref={logContainerRef}
            className="flex-1 overflow-y-auto p-3 space-y-0.5 font-mono text-[11px]"
          >
            {logs.length === 0 ? (
              <div className="h-full flex items-center justify-center text-zinc-700 text-xs">
                Waiting for agent...
              </div>
            ) : (
              logs.map((l, i) => <LogEntry key={i} data={l} />)
            )}
          </div>

          {/* Log footer */}
          <div className="border-t border-zinc-800/80 px-4 py-3 flex items-center gap-2">
            <Activity className="w-3 h-3 text-zinc-700" />
            <span className="text-[10px] text-zinc-600 truncate">{file?.name}</span>
          </div>
        </aside>

        {/* ── Right: Tabbed Artifact View ────────────────────────────────── */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Tab bar */}
          <div className="h-11 border-b border-zinc-800/80 flex items-end px-5 gap-0.5 flex-shrink-0 bg-zinc-900/30">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-t-lg border-b-2 transition-all",
                  activeTab === tab.id
                    ? "text-zinc-100 border-zinc-300 bg-zinc-800/50"
                    : "text-zinc-500 border-transparent hover:text-zinc-300 hover:bg-zinc-800/30"
                )}
              >
                {tab.icon}
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span
                    className={cn(
                      "px-1.5 py-0.5 rounded-full text-[9px] font-bold",
                      activeTab === tab.id
                        ? "bg-zinc-600 text-zinc-200"
                        : "bg-zinc-800 text-zinc-500"
                    )}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto bg-zinc-950">
            {/* Summary Tab */}
            {activeTab === "summary" && (
              <div className="p-8 max-w-3xl mx-auto">
                {summary ? (
                  <div className="space-y-4 animate-in fade-in duration-400">
                    <div className="flex items-center gap-2 mb-6">
                      <FileText className="w-4 h-4 text-zinc-500" />
                      <h2 className="text-xs font-semibold uppercase tracking-widest text-zinc-500">
                        Executive Summary
                      </h2>
                    </div>
                    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
                      <p className="text-zinc-300 leading-relaxed whitespace-pre-wrap text-sm">{summary}</p>
                    </div>
                  </div>
                ) : (
                  <div className="h-64 flex flex-col items-center justify-center gap-3 text-zinc-700">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <p className="text-xs uppercase tracking-widest">Generating summary...</p>
                  </div>
                )}
              </div>
            )}

            {/* Charts Tab */}
            {activeTab === "charts" && (
              <div className="p-5">
                {groupedArtifacts.figures.length === 0 ? (
                  <div className="h-64 flex flex-col items-center justify-center gap-3 text-zinc-700 border border-dashed border-zinc-800 rounded-xl mt-2">
                    <BarChart3 className="w-7 h-7 opacity-40" />
                    {streaming ? (
                      <p className="text-xs uppercase tracking-widest text-zinc-600 flex items-center gap-2">
                        <Loader2 className="w-3 h-3 animate-spin" /> Generating charts...
                      </p>
                    ) : (
                      <p className="text-xs uppercase tracking-widest">No charts produced</p>
                    )}
                  </div>
                ) : (
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 animate-in fade-in duration-400">
                    {groupedArtifacts.figures.map((a) => (
                      <div key={a} className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
                        <ArtifactResult artifactId={a} />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tables Tab */}
            {activeTab === "tables" && (
              <div className="p-5">
                {groupedArtifacts.tables.length === 0 ? (
                  <div className="h-64 flex flex-col items-center justify-center gap-3 text-zinc-700 border border-dashed border-zinc-800 rounded-xl mt-2">
                    <TableIcon className="w-7 h-7 opacity-40" />
                    {streaming ? (
                      <p className="text-xs uppercase tracking-widest text-zinc-600 flex items-center gap-2">
                        <Loader2 className="w-3 h-3 animate-spin" /> Generating tables...
                      </p>
                    ) : (
                      <p className="text-xs uppercase tracking-widest">No tables produced</p>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col gap-4 animate-in fade-in duration-400">
                    {[...groupedArtifacts.tables].reverse().map((a) => (
                      <div key={a} className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
                        <ArtifactResult artifactId={a} />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
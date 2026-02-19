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
  Zap,
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
  const [dragOver, setDragOver] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.name.endsWith(".csv")) setFile(dropped);
  };

  // ── Landing Page ──────────────────────────────────────────────────────────
  if (!isStarted) {
    return (
      <div className="min-h-screen bg-[#090909] flex overflow-hidden relative">
        {/* Ambient glow bg */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full bg-yellow-500/[0.03] blur-3xl" />
          <div className="absolute bottom-0 right-1/4 w-[500px] h-[400px] rounded-full bg-orange-500/[0.04] blur-3xl" />
        </div>

        {/* ── Left: Hero image panel ── */}
        <div className="hidden md:flex w-[52%] flex-shrink-0 relative items-center justify-center overflow-hidden border-r border-white/[0.04]">
          {/* Diagonal accent stripe */}
          <div className="absolute inset-0 bg-[linear-gradient(135deg,#0f0f0f_0%,#090909_60%)]" />

          {/* Grid lines */}
          <div
            className="absolute inset-0 opacity-[0.03]"
            style={{
              backgroundImage:
                "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
              backgroundSize: "60px 60px",
            }}
          />

          {/* Big label top-left */}
          <div className="absolute top-8 left-8 flex items-center gap-2.5 z-10">
            <div className="w-2 h-2 rounded-full bg-yellow-400 shadow-[0_0_10px_rgba(250,204,21,0.8)]" />
            <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-white/30">
              Data Minion v1.0
            </span>
          </div>

          {/* Vertical label */}
          <div className="absolute left-8 bottom-12 flex flex-col items-center gap-4 z-10">
            <div className="w-px h-24 bg-gradient-to-b from-transparent to-white/10" />
            <span
              className="font-mono text-[9px] tracking-[0.3em] uppercase text-white/20"
              style={{ writingMode: "vertical-rl" }}
            >
              AI-powered analysis
            </span>
          </div>

          {/* Hero image — vertically centered */}
          <div className="relative z-10 w-full flex items-center justify-center px-12">
            <img
              src="/minion-main.png"
              alt="Data Minion"
              className="w-full max-w-[560px] h-auto object-contain drop-shadow-2xl"
              style={{ filter: "drop-shadow(0 20px 60px rgba(250,204,21,0.1))" }}
            />
          </div>
        </div>

        {/* ── Right: Form panel ── */}
        <div className="flex-1 flex flex-col justify-center px-10 md:px-16 lg:px-20 py-16 relative z-10">
          {/* Mobile badge */}
          <div className="flex md:hidden items-center gap-2 mb-8">
            <div className="w-1.5 h-1.5 rounded-full bg-yellow-400 shadow-[0_0_8px_rgba(250,204,21,0.8)]" />
            <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-white/30">
              Data Minion v1.0
            </span>
          </div>

          <div className="max-w-md w-full">
            {/* Eyebrow */}
            <p className="font-mono text-[10px] tracking-[0.25em] uppercase text-yellow-400/60 mb-5">
              Ask questions about your data
            </p>

            {/* Headline */}
            <h1
              className="text-white font-black leading-[0.9] tracking-tight mb-6"
              style={{ fontSize: "clamp(52px, 6vw, 80px)" }}
            >
              YOUR DATA.
              <br />
              <span className="text-yellow-400">UNLEASHED.</span>
            </h1>

            {/* Sub */}
            <p className="text-white/30 text-sm leading-relaxed mb-10 max-w-sm">
              Upload a CSV, ask anything in plain English — get charts, tables
              and a full analysis in seconds.
            </p>

            {/* Card */}
            <div className="relative rounded-2xl border border-white/[0.08] bg-white/[0.03] backdrop-blur-sm p-6 space-y-5">
              {/* Top shimmer line */}
              <div className="absolute top-0 left-6 right-6 h-px bg-gradient-to-r from-transparent via-yellow-400/30 to-transparent" />

              {/* File drop zone */}
              <div className="space-y-1.5">
                <label className="font-mono text-[9px] tracking-[0.22em] uppercase text-white/30">
                  Dataset
                </label>
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={cn(
                    "relative h-12 flex items-center rounded-xl border cursor-pointer transition-all duration-200 overflow-hidden group",
                    dragOver
                      ? "border-yellow-400/60 bg-yellow-400/[0.06]"
                      : file
                        ? "border-emerald-500/40 bg-emerald-500/[0.04]"
                        : "border-white/[0.08] bg-white/[0.03] hover:border-white/[0.15] hover:bg-white/[0.05]"
                  )}
                >
                  <Input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    className="hidden"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                  <div className="flex items-center justify-between w-full px-4">
                    <div className="flex items-center gap-2.5">
                      <FileUp
                        className={cn(
                          "w-3.5 h-3.5 flex-shrink-0 transition-colors",
                          file ? "text-emerald-400" : "text-white/20 group-hover:text-white/40"
                        )}
                      />
                      <span
                        className={cn(
                          "text-sm truncate max-w-[200px] transition-colors",
                          file ? "text-white/80" : "text-white/20"
                        )}
                      >
                        {file ? file.name : "Drop CSV or click to browse"}
                      </span>
                    </div>
                    {file ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                    ) : (
                      <span className="text-[10px] font-mono text-white/20 group-hover:text-white/40 flex-shrink-0">
                        Browse
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Question input — always visible, disabled until file chosen */}
              <div className="space-y-1.5">
                <label className="font-mono text-[9px] tracking-[0.22em] uppercase text-white/30">
                  Question
                </label>
                <div className="relative">
                  <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/20 pointer-events-none" />
                  <Input
                    type="text"
                    placeholder={file ? "e.g. Show me top 10 products by revenue" : "Upload a file first…"}
                    value={prompt}
                    disabled={!file}
                    className={cn(
                      "h-12 pl-10 rounded-xl text-sm text-white/80 placeholder:text-white/20 border transition-all",
                      "bg-white/[0.03] border-white/[0.08]",
                      "focus-visible:ring-0 focus-visible:border-yellow-400/50 focus-visible:bg-white/[0.05]",
                      "disabled:opacity-40 disabled:cursor-not-allowed"
                    )}
                    onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleUpload()}
                  />
                </div>
              </div>

              {/* CTA */}
              <button
                onClick={handleUpload}
                disabled={!file || !prompt}
                className={cn(
                  "w-full h-12 rounded-xl text-sm font-bold tracking-wide transition-all duration-200 flex items-center justify-center gap-2 font-mono uppercase",
                  !file || !prompt
                    ? "bg-white/[0.04] text-white/20 cursor-not-allowed border border-white/[0.06]"
                    : "bg-yellow-400 text-black hover:bg-yellow-300 shadow-[0_0_30px_rgba(250,204,21,0.25)] hover:shadow-[0_0_40px_rgba(250,204,21,0.4)] active:scale-[0.99]"
                )}
              >
                <Zap className="w-4 h-4" />
                Run Analysis
              </button>
            </div>

            {/* Footer stats */}
            <div className="flex items-center gap-6 mt-8">
              {[
                { val: "~3s", label: "Avg. response" },
                { val: "CSV", label: "Format" },
                { val: "∞", label: "Questions" },
              ].map((s, i) => (
                <div key={i} className="flex items-center gap-4">
                  {i > 0 && <div className="w-px h-6 bg-white/[0.06]" />}
                  <div>
                    <div className="text-white font-black text-lg leading-none">{s.val}</div>
                    <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-white/20 mt-0.5">
                      {s.label}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Dashboard ─────────────────────────────────────────────────────────────
  const tabs: { id: Tab; label: string; icon: React.ReactNode; count?: number }[] = [
    { id: "summary", label: "Summary", icon: <FileText className="w-3.5 h-3.5" /> },
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
        <aside className="w-72 xl:w-80 flex-shrink-0 border-r border-zinc-800/80 flex-col bg-zinc-900/50 hidden md:flex">
          <div className="h-10 flex items-center gap-2 px-4 border-b border-zinc-800/80">
            <Terminal className="w-3.5 h-3.5 text-zinc-600" />
            <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">
              Execution Log
            </span>
            {streaming && (
              <div className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            )}
          </div>

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

          <div className="border-t border-zinc-800/80 px-4 py-3 flex items-center gap-2">
            <Activity className="w-3 h-3 text-zinc-700" />
            <span className="text-[10px] text-zinc-600 truncate">{file?.name}</span>
          </div>
        </aside>

        {/* ── Right: Tabbed Artifact View ────────────────────────────────── */}
        <div className="flex-1 flex flex-col overflow-hidden">
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

          <div className="flex-1 overflow-y-auto bg-zinc-950">
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
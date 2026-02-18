"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LogEntry } from "@/components/LogEntry";
import { ArtifactResult } from "@/components/ArtifactResult";
import {
  FileUp,
  Sparkles,
  Loader2,
  Database,
  Box,
  Activity,
  ChevronRight,
  LayoutDashboard,
  FileText,
  BarChart3,
  Table as TableIcon,
  RotateCcw,
  Search
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function HomePage() {
  const [prompt, setPrompt] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [artifacts, setArtifacts] = useState<any[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [isStarted, setIsStarted] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTo({
        top: logContainerRef.current.scrollHeight,
        behavior: "smooth"
      });
    }
  }, [logs]);

  // Grouping logic
  const groupedArtifacts = useMemo(() => {
    const figures = artifacts.filter(a => a.startsWith("chart_"));
    const tables = artifacts.filter(a => !a.startsWith("chart_"));
    return { figures, tables };
  }, [artifacts]);

  const handleUpload = async () => {
    if (!file || !prompt) return alert("Select a CSV and enter a prompt");

    setLogs([]);
    setArtifacts([]);
    setSummary(null);
    setStreaming(true);
    setIsStarted(true);

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
              if (data.final_summary) setSummary(data.final_summary);
            } catch (e) {
              // Ignore partial chunks
            }
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

  if (!isStarted) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 bg-[radial-gradient(#e5e7eb_1px,transparent_1px)] [background-size:16px_16px]">
        <div className="max-w-3xl w-full space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700">
          <div className="text-center space-y-4">
            <div className="inline-flex items-center gap-2 bg-minionBlue/10 px-4 py-2 rounded-full border border-minionBlue/20 text-minionBlue mb-4">
              <Sparkles className="w-4 h-4 fill-minionBlue" />
              <span className="text-sm font-black uppercase tracking-widest">Powered by Data Minion v1.0</span>
            </div>
            <h1 className="text-6xl md:text-7xl font-black text-slate-900 tracking-tight leading-none uppercase">
              Analyse your <br />
              <span className="text-minionBlue">Data</span> effortlessly.
            </h1>
            <p className="text-slate-500 text-xl max-w-xl mx-auto font-medium">
              Upload any CSV file and ask questions in plain English. Our AI agent handles the code and visualisations.
            </p>
          </div>

          <Card className="border-none shadow-[0_32px_64px_-16px_rgba(0,0,0,0.1)] rounded-[2.5rem] overflow-hidden bg-white p-2">
            <div className="bg-slate-50 rounded-[2rem] p-8 space-y-8">
              <div className="space-y-4">
                <label className="block text-xs font-black text-slate-400 uppercase tracking-widest ml-1">1. Choose your dataset</label>
                <div className="group relative">
                  <div className="absolute inset-0 bg-minionBlue/5 opacity-0 group-hover:opacity-100 rounded-2xl transition-opacity duration-300 pointer-events-none border-2 border-dashed border-minionBlue/20" />
                  <Input
                    type="file"
                    accept=".csv"
                    className="h-20 cursor-pointer file:mr-6 file:py-2 file:px-6 file:rounded-full file:border-0 file:text-sm file:font-black file:bg-minionBlue file:text-white hover:file:bg-minionBlue/90 bg-white border-2 border-slate-100 rounded-2xl shadow-sm transition-all focus-visible:ring-minionBlue"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                  {!file && <FileUp className="absolute right-6 top-7 w-6 h-6 text-slate-300 pointer-events-none group-hover:text-minionBlue transition-colors" />}
                </div>
              </div>

              <div className="space-y-4">
                <label className="block text-xs font-black text-slate-400 uppercase tracking-widest ml-1">2. Tell the Minion what to do</label>
                <div className="relative">
                  <Search className="absolute left-4 top-4.5 w-6 h-6 text-slate-300 pointer-events-none" />
                  <Input
                    type="text"
                    placeholder="e.g., 'Show me the correlation between price and demand'"
                    value={prompt}
                    className="h-16 pl-14 text-lg border-2 border-slate-100 focus-visible:ring-minionBlue rounded-2xl bg-white shadow-sm"
                    onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleUpload()}
                  />
                </div>
              </div>

              <Button
                onClick={handleUpload}
                disabled={!file || !prompt}
                className="w-full h-16 bg-minionBlue hover:bg-minionBlue/90 text-white text-lg font-black rounded-2xl shadow-[0_8px_0_0_rgba(29,78,216,1)] active:translate-y-1 active:shadow-none transition-all uppercase tracking-widest group"
              >
                Start Magic Calculation
                <ChevronRight className="w-6 h-6 ml-2 group-hover:translate-x-1 transition-transform" />
              </Button>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      {/* Mini Header */}
      <header className="bg-white border-b border-slate-200 h-16 flex items-center justify-between px-6 sticky top-0 z-50">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-minionBlue rounded-xl flex items-center justify-center shadow-lg shadow-minionBlue/20">
            <Sparkles className="w-5 h-5 text-minionYellow fill-current" />
          </div>
          <div className="flex flex-col">
            <h2 className="text-sm font-black uppercase tracking-tighter text-slate-900 leading-none">Data Minion</h2>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-widest truncate max-w-[200px]">
              {file?.name || "Processing..."}
            </span>
          </div>
          <div className="h-6 w-[1px] bg-slate-100 mx-2" />
          <p className="text-sm text-slate-500 font-medium italic truncate max-w-md hidden md:block">
            "{prompt}"
          </p>
        </div>

        <div className="flex items-center gap-3">
          {streaming && (
            <div className="flex items-center gap-2 bg-amber-50 px-3 py-1.5 rounded-full border border-amber-100 text-amber-600 animate-pulse">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span className="text-[10px] font-black uppercase tracking-widest">Agent Working</span>
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={reset}
            className="rounded-full border-slate-200 text-slate-600 font-black uppercase text-[10px] hover:bg-red-50 hover:text-red-600 hover:border-red-100 transition-colors"
          >
            <RotateCcw className="w-3 h-3 mr-1" />
            New Task
          </Button>
        </div>
      </header>

      <main className="flex-1 flex overflow-hidden">
        {/* Left Sidebar: Execution Log */}
        <aside className="w-[350px] lg:w-[450px] border-r border-slate-200 bg-slate-50/50 flex flex-col hidden md:flex">
          <div className="p-6 border-b border-slate-200 bg-white">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-minionBlue" />
              <h3 className="text-xs font-black uppercase tracking-widest text-slate-800">Process Log</h3>
            </div>
          </div>
          <div ref={logContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
            {logs.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-slate-300">
                <Database className="w-12 h-12 mb-4 opacity-10" />
                <p className="text-[10px] font-black uppercase tracking-widest">Initializing pipeline...</p>
              </div>
            )}
            <div className="space-y-1">
              {logs.map((l, i) => (
                <LogEntry key={i} data={l} />
              ))}
            </div>
          </div>
        </aside>

        {/* Right Content: Artifacts Grid */}
        <div className="flex-1 overflow-y-auto bg-white p-8 space-y-12">
          {/* Dashboard Header */}
          <div className="space-y-2">
            <h1 className="text-3xl font-black text-slate-900 uppercase tracking-tight flex items-center gap-3">
              <LayoutDashboard className="w-8 h-8 text-minionBlue" />
              Analysis Dashboard
            </h1>
            <p className="text-slate-400 font-medium">Insights and artifacts generated by the agent.</p>
          </div>

          {/* Group: Reports */}
          {(summary || streaming) && (
            <section className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500 delay-150">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600 shadow-sm border border-indigo-100">
                  <FileText className="w-5 h-5" />
                </div>
                <h2 className="text-lg font-black uppercase text-slate-800 tracking-widest">Executive Summary</h2>
              </div>
              <Card className="border-none bg-indigo-50/30 rounded-3xl overflow-hidden shadow-[0_8px_32px_rgb(99,102,241,0.04)] transition-all hover:bg-indigo-50/40">
                <CardContent className="p-10">
                  {summary ? (
                    <div className="max-w-none">
                      <p className="text-slate-700 text-lg leading-relaxed font-semibold whitespace-pre-wrap tracking-tight italic border-l-4 border-indigo-200 pl-6 py-2">
                        {summary}
                      </p>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-8 text-slate-400 gap-4">
                      <div className="w-12 h-12 rounded-full bg-white flex items-center justify-center shadow-sm">
                        <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
                      </div>
                      <p className="text-[10px] font-black uppercase tracking-widest text-indigo-400">Synthesizing final report...</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </section>
          )}

          {/* Group: Figures */}
          <section className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500 delay-300">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-rose-50 rounded-lg text-rose-600 shadow-sm border border-rose-100">
                <BarChart3 className="w-5 h-5" />
              </div>
              <h2 className="text-lg font-black uppercase text-slate-800 tracking-widest">Figures & Visualizations</h2>
            </div>
            {groupedArtifacts.figures.length === 0 ? (
              <div className="py-20 border-2 border-dashed border-slate-100 rounded-3xl flex flex-col items-center justify-center text-slate-300 bg-slate-50/30">
                <BarChart3 className="w-12 h-12 mb-4 opacity-10" />
                <p className="text-xs font-bold uppercase tracking-widest">No charts generated yet</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-10">
                {groupedArtifacts.figures.map((a) => (
                  <ArtifactResult key={a} artifactId={a} />
                ))}
              </div>
            )}
          </section>

          {/* Group: Tables */}
          <section className="space-y-6 pb-20 animate-in fade-in slide-in-from-top-4 duration-500 delay-500">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-50 rounded-lg text-amber-600 shadow-sm border border-amber-100">
                <TableIcon className="w-5 h-5" />
              </div>
              <h2 className="text-lg font-black uppercase text-slate-800 tracking-widest">Generated Datasets</h2>
            </div>
            {groupedArtifacts.tables.length === 0 ? (
              <div className="py-20 border-2 border-dashed border-slate-100 rounded-3xl flex flex-col items-center justify-center text-slate-300 bg-slate-50/30">
                <TableIcon className="w-12 h-12 mb-4 opacity-10" />
                <p className="text-xs font-bold uppercase tracking-widest">No data tables generated yet</p>
              </div>
            ) : (
              <div className="flex flex-col gap-10">
                {groupedArtifacts.tables.reverse().map((a) => (
                  <ArtifactResult key={a} artifactId={a} />
                ))}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}


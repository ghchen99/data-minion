"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LogEntry } from "@/components/LogEntry";
import { FileUp, Sparkles, Loader2, Database, Box, Activity } from "lucide-react";

export default function HomePage() {
  const [prompt, setPrompt] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [artifacts, setArtifacts] = useState<any[]>([]);
  const [streaming, setStreaming] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleUpload = async () => {
    if (!file || !prompt) return alert("Select a CSV and enter a prompt");

    setLogs([]);
    setArtifacts([]);
    setStreaming(true);

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
            } catch (e) {
              console.error("Error parsing JSON chunk:", e);
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

  return (
    <div className="min-h-screen bg-minionYellow font-sans selection:bg-minionBlue/20">
      {/* Hero Section */}
      <header className="bg-minionBlue text-white py-12 px-6 shadow-lg mb-8">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-white/20 p-2 rounded-lg backdrop-blur-sm">
              <Sparkles className="w-8 h-8 text-minionYellow" />
            </div>
            <h1 className="text-4xl font-black tracking-tight uppercase">
              Data Minion <span className="text-minionYellow">v1.0</span>
            </h1>
          </div>
          <p className="text-blue-50 text-xl max-w-2xl font-medium opacity-90">
            Intelligent data processing at your service. Upload a CSV and let the agent work its magic.
          </p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 pb-12">
        {/* Controls */}
        <div className="bg-white rounded-2xl shadow-xl p-6 mb-8 border-b-8 border-minionBlue/20 flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <label className="block text-sm font-bold text-slate-500 uppercase mb-2 ml-1">Upload Data</label>
            <div className="relative group">
              <Input
                type="file"
                accept=".csv"
                className="cursor-pointer file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-minionBlue file:text-white hover:file:bg-minionBlue/90"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              <FileUp className="absolute right-3 top-2.5 w-5 h-5 text-slate-400 pointer-events-none" />
            </div>
          </div>

          <div className="flex-[2]">
            <label className="block text-sm font-bold text-slate-500 uppercase mb-2 ml-1">Analysis Prompt</label>
            <Input
              type="text"
              placeholder="e.g., 'Group sales by region and create a bar chart'"
              value={prompt}
              className="border-2 border-slate-100 h-12 focus-visible:ring-minionBlue rounded-xl text-lg"
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleUpload()}
            />
          </div>

          <div className="flex items-end">
            <Button
              onClick={handleUpload}
              disabled={streaming}
              className="h-12 px-8 bg-minionBlue hover:bg-minionBlue/90 text-white font-black rounded-xl shadow-[0_4px_0_0_rgba(29,78,216,1)] active:translate-y-1 active:shadow-none transition-all uppercase tracking-wider"
            >
              {streaming ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                "Run Agent"
              )}
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Logs */}
          <div className="lg:col-span-12 xl:col-span-5">
            <Card className="border-none shadow-2xl rounded-3xl overflow-hidden bg-slate-50/50 backdrop-blur-md h-[600px] flex flex-col">
              <CardHeader className="bg-white border-b px-6 py-4">
                <div className="flex items-center gap-2">
                  <Activity className="w-5 h-5 text-minionBlue" />
                  <CardTitle className="text-xl font-black uppercase text-slate-800">Execution Process</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto p-6">
                {logs.length === 0 && !streaming && (
                  <div className="h-full flex flex-col items-center justify-center text-slate-400 animate-pulse">
                    <Database className="w-12 h-12 mb-2 opacity-20" />
                    <p className="font-medium italic">Waiting for instructions...</p>
                  </div>
                )}
                <div className="space-y-1">
                  {logs.map((l, i) => (
                    <LogEntry key={i} data={l} />
                  ))}
                  <div ref={logEndRef} />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Artifacts */}
          <div className="lg:col-span-12 xl:col-span-7">
            <Card className="border-none shadow-2xl rounded-3xl overflow-hidden bg-white h-[600px] flex flex-col">
              <CardHeader className="bg-white border-b px-6 py-4">
                <div className="flex items-center gap-2">
                  <Box className="w-5 h-5 text-minionYellow" />
                  <CardTitle className="text-xl font-black uppercase text-slate-800">Generated Results</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto p-8 bg-slate-50/30">
                {artifacts.length === 0 && (
                  <div className="h-full flex flex-col items-center justify-center text-slate-400">
                    <div className="w-24 h-24 bg-slate-100 rounded-full flex items-center justify-center mb-4 border-4 border-white shadow-inner">
                      <Box className="w-10 h-10 opacity-20" />
                    </div>
                    <p className="font-medium">No results generated yet</p>
                  </div>
                )}
                <div className="grid grid-cols-1 gap-8">
                  {artifacts.map((a, i) => (
                    <div key={i} className="group relative bg-white p-4 rounded-2xl shadow-sm border border-slate-100 hover:shadow-xl transition-all duration-300">
                      <div className="absolute top-4 right-4 bg-slate-100 text-[10px] font-mono font-bold px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity uppercase text-slate-500">
                        {a.startsWith("chart_") ? "Visualization" : "Dataset"}
                      </div>

                      {a.startsWith("chart_") ? (
                        <div className="bg-slate-50 rounded-xl overflow-hidden p-2 border border-slate-100 shadow-inner">
                          <img
                            src={`http://localhost:8000/static/images/${a}.png`}
                            alt={a}
                            className="w-full h-auto rounded-lg shadow-sm"
                          />
                        </div>
                      ) : (
                        <div className="p-4 bg-slate-900 rounded-xl overflow-hidden border-2 border-slate-800 shadow-2xl">
                          <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap leading-relaxed">
                            {a}
                          </pre>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}

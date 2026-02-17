"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  const [prompt, setPrompt] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [artifacts, setArtifacts] = useState<any[]>([]);
  const [streaming, setStreaming] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const handleUpload = async () => {
    if (!file || !prompt) return alert("Select a CSV and enter a prompt");

    setLogs([]);
    setArtifacts([]);
    setStreaming(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("prompt", prompt);

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
          const data = JSON.parse(line);
          if (data.updates || data.status_update) setLogs((prev) => [...prev, data]);
          if (data.all_artifacts) setArtifacts(data.all_artifacts);
        }
      });
    }
    setStreaming(false);
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="min-h-screen bg-minionYellow text-minionBlue p-6 font-sans">
      <h1 className="text-4xl font-bold mb-6">Agentic Data Stream Demo</h1>

      <div className="flex gap-4 mb-6">
        <Input
          type="file"
          accept=".csv"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <Input
          type="text"
          placeholder="Enter your NLP prompt..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <Button onClick={handleUpload} disabled={streaming}>
          {streaming ? "Streaming..." : "Run Agent"}
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Logs */}
        <Card className="overflow-auto max-h-[500px] bg-white text-black">
          <CardHeader>
            <CardTitle>Execution Logs</CardTitle>
          </CardHeader>
          <CardContent>
            {logs.map((l, i) => (
              <div key={i} className="mb-2">
                <pre className="text-sm">{JSON.stringify(l, null, 2)}</pre>
              </div>
            ))}
            <div ref={logEndRef} />
          </CardContent>
        </Card>

        {/* Artifacts */}
        <Card className="overflow-auto max-h-[500px] bg-white text-black">
          <CardHeader>
            <CardTitle>Artifacts</CardTitle>
          </CardHeader>
          <CardContent>
            {artifacts.map((a, i) => (
              <div key={i} className="mb-4">
                {a.startsWith("chart_") ? (
                  <img
                    src={`http://localhost:8000/static/images/${a}.png`}
                    alt={a}
                    className="border border-black"
                  />
                ) : (
                  <pre className="text-sm">{a}</pre>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

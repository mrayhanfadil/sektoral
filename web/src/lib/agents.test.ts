import { describe, expect, it } from "vitest";
import type { JobEvent } from "./api";
import { derive, duration } from "./agents";
import { playbackTimes } from "./replay";

const ev = (stage: string, label: string, status: JobEvent["status"], t: number, extra: Partial<JobEvent> = {}): JobEvent =>
  ({ stage, label, status, t, ...extra });

const RUN: JobEvent[] = [
  ev("memory", "Membaca memori riset", "ok", 0.1, { detail: "belum ada riset sebelumnya" }),
  ev("plan", "Agent menyusun rencana riset", "run", 0.2),
  ev("plan", "Rencana siap", "ok", 9, { detail: "Apakah margin bertahan?" }),
  ev("plan", "Hipotesis 1", "ok", 9, { tool: "hypothesis", detail: "Margin di atas peer", data: { index: "1" } }),
  ev("tool", "Menjalankan find_peers", "run", 10, { tool: "find_peers", detail: "bandingkan peer" }),
  ev("tool", "find_peers selesai", "ok", 11, { tool: "find_peers", detail: "5 emiten" }),
  ev("tool", "Menjalankan foreign_flow", "run", 11.2, { tool: "foreign_flow" }),
  ev("tool", "foreign_flow: data tidak tersedia", "warn", 11.5, { tool: "foreign_flow" }),
  ev("synthesis", "H1: didukung", "ok", 20, { tool: "verdict", data: { index: "1", verdict: "didukung" } }),
  ev("research", "Agent riset membaca data", "run", 21),
  ev("research", "Membaca /company/report/X/", "run", 21.5, { tool: "cache_get", agent: "riset" }),
  ev("research", "Membaca /company/report/X/", "ok", 22, { tool: "cache_get", agent: "riset" }),
  ev("research", "Brief riset tervalidasi", "ok", 30),
  ev("forecast", "Agent forecast mulai", "run", 31),
  ev("forecast", "Subagent dampak berita", "run", 31.1, { agent: "forecast.news" }),
  ev("forecast", "Subagent dampak berita selesai", "ok", 40, { agent: "forecast.news" }),
  ev("forecast", "Asumsi forecast selesai", "ok", 41),
  ev("report", "Menyusun company update", "run", 42),
  ev("gate", "Gerbang metode menilai emiten", "run", 43, { agent: "gerbang" }),
  ev("gate", "Model bisnis", "ok", 43.1, { agent: "gerbang", tool: "gate_0", data: { gate: "0", verdict: "lolos" } }),
  ev("gate", "Kelayakan data", "ok", 43.2, { agent: "gerbang", tool: "gate_1", data: { gate: "1", verdict: "tidak berlaku" } }),
  ev("gate", "DDM", "ok", 43.3, { agent: "gerbang", tool: "chain_step", data: { decision: "Terpilih", value: "Rp5.075" } }),
  ev("gate", "Metode utama DDM", "ok", 43.4, { agent: "gerbang" }),
];

describe("derive", () => {
  it("pairs each tool call with its result and nests subagents under their task", () => {
    const s = derive(RUN);
    const peers = s.steps.find((x) => x.tool === "find_peers")!;
    expect(peers.status).toBe("ok");
    expect(peers.reason).toBe("bandingkan peer");
    expect(peers.resultDetail).toBe("5 emiten");
    expect(s.steps.find((x) => x.tool === "foreign_flow")!.status).toBe("warn");
    const research = s.steps.find((x) => x.title === "Agent riset membaca data")!;
    expect(research.children.map((id) => s.byId.get(id)!.tool)).toEqual(["cache_get"]);
    const forecast = s.steps.find((x) => x.title === "Agent forecast mulai")!;
    expect(s.byId.get(forecast.children[0])!.sub).toBe("news");
    expect(s.subagents.news).toBe("ok");
  });

  it("reads the plan, hypotheses, gates and method chain", () => {
    const s = derive(RUN);
    expect(s.plan.question).toBe("Apakah margin bertahan?");
    expect(s.plan.hypotheses).toEqual([{ index: 1, text: "Margin di atas peer", verdict: "didukung", reason: undefined }]);
    expect(s.gates[0].status).toBe("ok");
    expect(s.gates[1].status).toBe("skip");
    expect(s.gates[5].status).toBe("idle");
    expect(s.chain).toEqual([{ method: "DDM", decision: "Terpilih", value: "Rp5.075", reason: undefined, order: 0 }]);
  });

  it("keeps the running agent and phase while the run is live, and closes them when finished", () => {
    const live = derive(RUN);
    expect(live.agents.laporan.status).toBe("run");
    expect(live.agents.analis.status).toBe("warn");
    expect(live.phases[4].status).toBe("run");
    expect(live.active?.title).toBe("Menyusun company update");
    const done = derive(RUN, { finished: true });
    expect(done.agents.laporan.status).toBe("ok");
    expect(done.phases.every((p) => p.status !== "run")).toBe(true);
    expect(done.active).toBeUndefined();
  });
});

describe("helpers", () => {
  it("formats durations the Indonesian way", () => {
    expect(duration(12.44)).toBe("12,4 dtk");
    expect(duration(125)).toBe("2 mnt 05 dtk");
  });
  it("shortens long waits on playback but keeps order", () => {
    const times = playbackTimes([ev("plan", "a", "ok", 0), ev("plan", "b", "ok", 60), ev("plan", "c", "ok", 60)]);
    expect(times[1]).toBeLessThan(3);
    expect(times[2]).toBeGreaterThan(times[1]);
  });
});

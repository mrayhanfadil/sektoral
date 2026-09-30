import { describe, expect, it } from "vitest";
import type { Intel, JobEvent } from "./api";
import { derive, duration, planIn, releaseFigures } from "./agents";
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
    expect(s.plan.hypotheses).toEqual([{ index: 1, text: "Margin di atas peer", verdict: "didukung", code: "supported", reason: undefined }]);
    expect(s.gates[0].status).toBe("ok");
    expect(s.gates[0].code).toBe("pass");
    expect(s.gates[1].status).toBe("skip");
    expect(s.gates[5].status).toBe("idle");
    expect(s.chain).toEqual([{ method: "DDM", decision: "Terpilih", code: "selected", value: "Rp5.075", reason: undefined, order: 0 }]);
  });

  it("reads the step kinds from the labels of a run without codes", () => {
    const s = derive(RUN);
    const peers = s.steps.find((x) => x.tool === "find_peers")!;
    expect([peers.event, peers.resultEvent]).toEqual(["tool_start", "tool_done"]);
    expect(s.steps.find((x) => x.tool === "foreign_flow")!.resultEvent).toBe("tool_error");
    expect(s.steps.find((x) => x.title === "Gerbang metode menilai emiten")!.resultEvent).toBe("primary_method");
  });

  it("reads codes and kinds a newer server sends, whatever its labels say", () => {
    const s = derive([
      ev("synthesis", "Hipotesis 1", "ok", 1, { tool: "hypothesis", detail: "Margin", data: { kind: "hypothesis", index: "1" } }),
      ev("synthesis", "H1 x", "ok", 2, { tool: "verdict", data: { kind: "hypothesis", index: "1", verdict: "x", verdict_code: "not_supported" } }),
      ev("gate", "Kewajaran hasil", "warn", 3, { agent: "gerbang", tool: "gate_5", data: { kind: "gate", gate: "5", verdict: "x", verdict_code: "fail" } }),
      ev("gate", "Kelayakan data", "ok", 4, { agent: "gerbang", tool: "gate_1", data: { kind: "gate", gate: "1", verdict: "x", verdict_code: "not_applicable" } }),
      ev("gate", "P/BV", "ok", 5, { agent: "gerbang", tool: "chain_step", data: { kind: "chain_row", decision: "x", decision_code: "cross_check", value: "-" } }),
      ev("tool", "Running news", "run", 6, { tool: "news", data: { kind: "tool_start" } }),
      ev("tool", "news: none", "warn", 7, { tool: "news", data: { kind: "tool_empty" } }),
    ]);
    expect(s.plan.hypotheses[0].code).toBe("not_supported");
    expect(s.gates[5].code).toBe("fail");
    expect(s.gates[1].status).toBe("skip");
    expect(s.chain[0].code).toBe("cross_check");
    const news = s.steps.find((x) => x.tool === "news")!;
    expect([news.event, news.resultEvent]).toEqual(["tool_start", "tool_empty"]);
  });

  it("shows the server's English twins to an English reader and reads the kinds from the Indonesian", () => {
    const TWINS: JobEvent[] = [
      ev("memory", "Membaca memori riset", "ok", 0.1, { label_en: "Reading Run Memory", detail: "riset terakhir 2026-09-25", detail_en: "last run 2026-09-25" }),
      ev("plan", "Rencana siap", "ok", 1, { detail: "Apakah margin bertahan?", detail_en: "Will margins hold?" }),
      ev("plan", "Hipotesis 1", "ok", 1, { tool: "hypothesis", detail: "Margin di atas peer", detail_en: "Margins above peers", data: { index: "1" } }),
      ev("tool", "Menjalankan find_peers", "run", 2, { tool: "find_peers", label_en: "Running find_peers", detail: "bandingkan peer", detail_en: "compare peers" }),
      ev("tool", "find_peers selesai", "ok", 3, { tool: "find_peers", label_en: "find_peers done", detail: "5 emiten", detail_en: "5 issuers" }),
      ev("research", "Agent riset membaca data", "run", 4, { label_en: "Research agent reads the data" }),
      ev("research", "Agent riset membaca data", "ok", 5, { label_en: "  " }),
      ev("gate", "Siklus & tahap operasi", "ok", 6, { agent: "gerbang", tool: "gate_3", detail: "siklus dan tahap operasi",
        detail_en: "cycle and operating stage", data: { gate: "3", verdict: "lolos" } }),
      ev("gate", "PER FY skenario", "ok", 7, { agent: "gerbang", tool: "chain_step", label_en: "FY scenario PER",
        detail: "peer PER valid kurang dari tiga", detail_en: "fewer than three valid peer PERs", data: { decision: "Silang cek", value: "Rp3.150" } }),
    ];
    const en = derive(TWINS, { lang: "en" });
    expect(en.steps[0]).toMatchObject({ title: "Reading Run Memory", resultDetail: "last run 2026-09-25" });
    expect(en.plan).toEqual({ question: "Will margins hold?", hypotheses: [{ index: 1, text: "Margins above peers" }] });
    const peers = en.steps.find((x) => x.tool === "find_peers")!;
    expect(peers).toMatchObject({ title: "Running find_peers", reason: "compare peers", result: "find_peers done",
      resultDetail: "5 issuers", event: "tool_start", resultEvent: "tool_done" });
    // The same Indonesian label opens and closes the step: no separate result, whatever the twins say.
    expect(en.steps.find((x) => x.stage === "research")!.result).toBeUndefined();
    expect(en.gates[3]).toMatchObject({ code: "pass", detail: "cycle and operating stage" });
    expect(en.chain[0]).toMatchObject({ method: "FY scenario PER", code: "cross_check", reason: "fewer than three valid peer PERs" });

    const id = derive(TWINS, { lang: "id" });
    expect(id.steps[0]).toMatchObject({ title: "Membaca memori riset", resultDetail: "riset terakhir 2026-09-25" });
    expect(id.gates[3].detail).toBe("siklus dan tahap operasi");
    expect(id.chain[0].method).toBe("PER FY skenario");
    expect(derive(TWINS)).toEqual(id);
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

describe("release figures", () => {
  it("formats the raw numbers in the reader's language", () => {
    const release = { status: "production_ready", rating: "Sell", tp: "Rp4.125", upside: "−20,9%", tp_value: 4125, upside_pct: -20.9 };
    expect(releaseFigures(release, "en")).toEqual({ tp: "Rp4,125", upside: "−20.9%", down: true });
    expect(releaseFigures(release, "id")).toEqual({ tp: "Rp4.125", upside: "−20,9%", down: true });
    expect(releaseFigures({ tp_value: "12500", upside_pct: "12.3" }, "en")).toEqual({ tp: "Rp12,500", upside: "+12.3%", down: false });
  });
  it("keeps an older event's Indonesian strings", () => {
    expect(releaseFigures({ tp: "Rp5.075", upside: "+61,6%" }, "en")).toEqual({ tp: "Rp5.075", upside: "+61,6%", down: false });
    expect(releaseFigures({ status: "draft_non_distributable" }, "en")).toEqual({ tp: undefined, upside: undefined, down: false });
    expect(releaseFigures(undefined, "en").tp).toBeUndefined();
  });
});

describe("plan in the reader's language", () => {
  const intel = {
    plan: { question: "Apakah margin bertahan?", question_en: "Will margins hold?", source: "agent",
      hypotheses: ["Margin di atas peer", "Utang turun"], hypotheses_en: ["Margins above peers", null] },
    synthesis: { hypotheses: [{ index: 0, verdict: "didukung", reason: "ROE tinggi", reason_en: "High ROE", signal_ids: [] }] },
  } as unknown as Intel;
  const plan = {
    question: "Apakah margin bertahan?",
    hypotheses: [{ index: 1, text: "Margin di atas peer", verdict: "didukung", reason: "ROE tinggi" }, { index: 2, text: "Utang turun" }],
  };
  it("takes the English twins for an English reader", () => {
    expect(planIn(plan, intel, "en")).toEqual({
      question: "Will margins hold?",
      hypotheses: [{ index: 1, text: "Margins above peers", verdict: "didukung", reason: "High ROE" }, { index: 2, text: "Utang turun" }],
    });
  });
  it("keeps the Indonesian for Indonesian readers, without a result, or when the text is not the same run's", () => {
    expect(planIn(plan, intel, "id")).toBe(plan);
    expect(planIn(plan, null, "en")).toBe(plan);
    const other = { question: "Pertanyaan lain", hypotheses: [{ index: 1, text: "Hipotesis lain" }] };
    expect(planIn(other, intel, "en")).toEqual(other);
  });
});

describe("helpers", () => {
  it("formats durations the Indonesian way", () => {
    expect(duration(12.44, "id")).toBe("12,4 dtk");
    expect(duration(125, "id")).toBe("2 mnt 05 dtk");
  });
  it("formats durations the English way", () => {
    expect(duration(12.44, "en")).toBe("12.4 s");
    expect(duration(125, "en")).toBe("2 min 05 s");
  });
  it("shortens long waits on playback but keeps order", () => {
    const times = playbackTimes([ev("plan", "a", "ok", 0), ev("plan", "b", "ok", 60), ev("plan", "c", "ok", 60)]);
    expect(times[1]).toBeLessThan(3);
    expect(times[2]).toBeGreaterThan(times[1]);
  });
});

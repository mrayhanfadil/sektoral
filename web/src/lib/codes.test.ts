import { describe, expect, it } from "vitest";
import { decisionCode, eventKind, gateCode, num, primaryMethodOf, str, verdictCode } from "./codes";

describe("codes first, labels as the fallback", () => {
  it("takes the server's code when it sends one", () => {
    expect(decisionCode("cross_check", "Silang cek")).toBe("cross_check");
    expect(gateCode("not_assessable", "tidak dapat dinilai")).toBe("not_assessable");
    expect(verdictCode("partly_supported", "sebagian didukung")).toBe("partly_supported");
  });
  it("reads the Indonesian label when the code is absent, null or unknown", () => {
    expect(decisionCode(undefined, "Terpilih")).toBe("selected");
    expect(decisionCode(null, "Tidak dijalankan")).toBe("not_needed");
    expect(decisionCode("not_a_code", "Belum tersedia")).toBe("unavailable");
    expect(decisionCode(undefined, "Terpilih, ekstrem (rantai berhenti)")).toBe("stop_extreme");
    expect(decisionCode(undefined, "Terpilih, ekstrem")).toBe("stop_extreme");
    expect(gateCode(undefined, "Gagal")).toBe("fail");
    expect(gateCode(undefined, "tidak berlaku")).toBe("not_applicable");
    expect(verdictCode(undefined, "belum terjawab")).toBe("unanswered");
  });
  it("gives no code for a label it does not know", () => {
    expect(decisionCode(undefined, "Dipakai ulang")).toBeUndefined();
    expect(gateCode(undefined, "")).toBeUndefined();
    expect(verdictCode(undefined, undefined)).toBeUndefined();
    expect(verdictCode(undefined, "constructor")).toBeUndefined();
  });
});

describe("event kinds", () => {
  it("takes data.kind when present", () => {
    expect(eventKind({ label: "Running find_peers", tool: "find_peers", data: { kind: "tool_start" } })).toBe("tool_start");
    expect(eventKind({ label: "find_peers: no rows", tool: "find_peers", data: { kind: "tool_empty" } })).toBe("tool_empty");
    expect(eventKind({ label: "Primary method DDM", data: { kind: "primary_method", method: "DDM" } })).toBe("primary_method");
  });
  it("reads the pipeline's Indonesian label without it", () => {
    expect(eventKind({ label: "Menjalankan find_peers", tool: "find_peers" })).toBe("tool_start");
    expect(eventKind({ label: "find_peers selesai", tool: "find_peers" })).toBe("tool_done");
    expect(eventKind({ label: "foreign_flow: data tidak tersedia", tool: "foreign_flow" })).toBe("tool_error");
    expect(eventKind({ label: "Metode utama DDM" })).toBe("primary_method");
    expect(eventKind({ label: "Rantai metode selesai" })).toBe("chain_done");
    expect(eventKind({ label: "Model bisnis", tool: "gate_0" })).toBe("gate");
    expect(eventKind({ label: "DDM", tool: "chain_step" })).toBe("chain_row");
    expect(eventKind({ label: "Hipotesis 1", tool: "hypothesis" })).toBe("hypothesis");
    expect(eventKind({ label: "Status rilis: draft", tool: "release" })).toBe("release");
    expect(eventKind({ label: "Agent menyusun rencana riset" })).toBeUndefined();
    expect(eventKind({ label: "Membaca /company/report/X/", tool: "cache_get" })).toBeUndefined();
  });
  it("names the primary method from data.method, else the label", () => {
    expect(primaryMethodOf({ label: "Metode utama DDM [bank]", data: { method: "DDM" } })).toBe("DDM");
    expect(primaryMethodOf({ label: "Metode utama EV/EBITDA peer" })).toBe("EV/EBITDA peer");
    expect(primaryMethodOf({ label: "Rantai metode selesai" })).toBeUndefined();
  });
});

describe("event values", () => {
  it("reads numbers sent as numbers or strings", () => {
    expect(num(4125)).toBe(4125);
    expect(num("-20.9")).toBe(-20.9);
    expect(num("Rp4.125")).toBeUndefined();
    expect(num(undefined)).toBeUndefined();
    expect(num("")).toBeUndefined();
  });
  it("reads text", () => {
    expect(str(3)).toBe("3");
    expect(str("lolos")).toBe("lolos");
    expect(str(null)).toBeUndefined();
    expect(str("")).toBeUndefined();
  });
});

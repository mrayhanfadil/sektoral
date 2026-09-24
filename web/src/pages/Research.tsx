import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useLoad } from "../components/State";

const TICKER = /^[A-Za-z0-9][A-Za-z0-9.-]{0,9}$/;

function ResearchForm({ heading, level }: { heading: string; level: "h1" | "h2" }) {
  const navigate = useNavigate();
  const { data: tickers = [] } = useLoad(api.tickers);
  const [ticker, setTicker] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const Heading = level;

  async function start(event: React.FormEvent) {
    event.preventDefault();
    const value = ticker.trim().toUpperCase();
    if (!TICKER.test(value)) {
      setError("Masukkan kode emiten yang valid.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      navigate(`/jobs/${await api.submit(value)}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-labelledby="form-title">
      <Heading id="form-title" className="mb-2 text-[26px] font-black tracking-[-.02em]">{heading}</Heading>
      <p className="text-ink-soft">Masukkan kode emiten untuk menjalankan agent, memeriksa bukti, dan menyusun ringkasan riset.</p>
      <form onSubmit={start} className="mt-6" noValidate>
        <label htmlFor="ticker" className="mb-2 block text-sm font-bold">Kode emiten IDX</label>
        <div className="flex gap-2.5 max-sm:flex-col">
          <input id="ticker" name="ticker" maxLength={10} placeholder="Contoh: AMMN" required autoComplete="off"
            list="ticker-list" aria-describedby="ticker-hint" value={ticker}
            onChange={(e) => { setTicker(e.target.value); setError(null); }}
            className="h-[52px] min-w-0 flex-1 rounded-[10px] border border-rule bg-white px-4 text-xl font-bold tracking-[.08em] uppercase text-ink transition placeholder:text-base placeholder:font-normal placeholder:tracking-[.02em] placeholder:normal-case placeholder:text-ink-faint hover:border-[#A9AEB8] focus:border-brand focus:shadow-[0_0_0_4px_var(--color-brand-100)] focus:outline-none" />
          <button type="submit" disabled={busy} className="btn btn-primary h-[52px] px-6 text-base max-sm:w-full">
            {busy ? "Memulai…" : "Mulai riset"}
          </button>
        </div>
        <datalist id="ticker-list">{tickers.map((t) => <option key={t} value={t} />)}</datalist>
        <p id="ticker-hint" className="mt-2 text-[13px] text-ink-soft">Kode saham BEI, misalnya AMMN atau BBRI.</p>
        {error && (
          <div role="alert" className="mt-4 flex items-start gap-2.5 rounded-[10px] bg-err-bg px-3.5 py-3 text-[15px] font-medium text-err-ink">
            <span aria-hidden>!</span><span>{error}</span>
          </div>
        )}
      </form>
      {tickers.length > 0 && (
        <>
          <div className="mt-7 flex items-baseline justify-between gap-3">
            <h3 id="chips-title" className="text-sm">Emiten dengan data tersedia</h3>
            <span className="text-[13px] text-ink-soft">{tickers.length} emiten</span>
          </div>
          <div role="group" aria-labelledby="chips-title" className="mt-3 flex flex-wrap gap-2">
            {tickers.map((t) => <Chip key={t} ticker={t} pressed={ticker.trim().toUpperCase() === t} onPick={setTicker} />)}
          </div>
        </>
      )}
      <p className="mt-7 border-t border-rule-soft pt-[18px] text-[13.5px] text-ink-soft">
        Hasil menyajikan informasi dan analisis, bukan rekomendasi investasi. Kesimpulan ditandai parsial jika bukti belum cukup.
      </p>
    </section>
  );
}

function Chip({ ticker, pressed, onPick }: { ticker: string; pressed: boolean; onPick: (t: string) => void }) {
  return (
    <button type="button" aria-pressed={pressed}
      onClick={() => { onPick(ticker); document.getElementById("ticker")?.focus(); }}
      className="cursor-pointer rounded-lg border border-rule bg-white px-[11px] py-1.5 text-[13px] font-bold tracking-[.04em] text-ink transition-colors hover:border-brand hover:bg-brand-50 hover:text-brand aria-pressed:border-brand aria-pressed:bg-brand aria-pressed:text-white">
      {ticker}
    </button>
  );
}

function SideExplainer() {
  const { data: history = [] } = useLoad(api.history);
  return (
    <aside className="card" aria-labelledby="side-title">
      {history.length > 0 && (
        <div className="mb-[26px] border-b border-rule-soft pb-[22px]">
          <h3 id="history-title" className="text-base">Riwayat riset</h3>
          <p className="text-[13.5px] text-ink-soft">Agent mengingat riset sebelumnya dan melaporkan apa yang berubah.</p>
          <ul aria-labelledby="history-title" className="mt-3 grid list-none gap-2 p-0">
            {history.map((row) => (
              <li key={row.ticker} className="grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-[10px] border border-rule-soft px-2.5 py-2">
                <span className="min-w-[62px] rounded-lg border border-rule px-2 py-1 text-center text-[13px] font-black">{row.ticker}</span>
                <span className="text-[13px] leading-snug text-ink-soft">
                  {row.runs} kali, data {row.market_date ?? "—"}, {row.flags} sinyal bertanda
                </span>
                {row.pdf_url ? <a href={row.pdf_url} className="text-[13px] font-bold no-underline">PDF</a> : <span />}
              </li>
            ))}
          </ul>
        </div>
      )}
      <h2 id="side-title" className="mb-4 text-lg">Setelah Anda menekan Mulai riset</h2>
      <ol className="m-0 list-none p-0">
        {[
          ["Agent menyusun rencana", "Pertanyaan riset dan hipotesis yang bisa diuji, sesuai jenis usaha emiten."],
          ["Agent memilih tool", "Peer, kuartalan, harga, arus asing, valuasi, berita. Setiap hasil bisa mengubah langkah berikutnya."],
          ["Sinyal & hipotesis diuji", "Peringkat peer dan anomali dihitung deterministik; kesimpulan wajib mengutip sinyal."],
          ["Skenario, valuasi, pemeriksaan", "Agen asumsi menyusun skenario laba dan risiko; gerbang memilih rantai metode; harness memutuskan terbit atau tahan."],
        ].map(([title, body], i, all) => (
          <li key={title} className="relative pb-[18px] pl-10 last:pb-0">
            <span aria-hidden className="absolute top-0 left-0 grid size-[26px] place-items-center rounded-full bg-brand-50 text-[13px] font-black text-brand">{i + 1}</span>
            {i < all.length - 1 && <span aria-hidden className="absolute top-[30px] bottom-1 left-[12.5px] w-px bg-rule" />}
            <strong className="block text-[15px]">{title}</strong>
            <span className="text-sm text-ink-soft">{body}</span>
          </li>
        ))}
      </ol>
    </aside>
  );
}

/** Form + explainer; the run page shows it below the running job. */
export function ResearchPanels({ afterJob = false }: { afterJob?: boolean }) {
  return (
    <div className="grid items-start gap-6 min-[881px]:grid-cols-[1.5fr_1fr] [&>*]:min-w-0">
      <ResearchForm heading={afterJob ? "Riset emiten lain" : "Buat company update"} level={afterJob ? "h2" : "h1"} />
      <SideExplainer />
    </div>
  );
}

export default function Research() {
  return (
    <div className="bg-canvas py-10 max-sm:py-5">
      <div className="wrap"><ResearchPanels /></div>
    </div>
  );
}

import { lazy, StrictMode, Suspense, useEffect, type ComponentType } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import "./index.css";
import Layout from "./components/Layout";
import NotFound from "./pages/NotFound";

// Each page loads on first visit, so the landing does not ship the Deck's
// motion-heavy console and the Deck does not ship the landing's reel.
const page = <T,>(load: () => Promise<T>, pick: (m: T) => ComponentType) =>
  lazy(() => load().then((m) => ({ default: pick(m) })));
const Landing = page(() => import("./pages/Landing"), (m) => m.default);
const DeckLaunch = page(() => import("./pages/Deck"), (m) => m.DeckLaunch);
const DeckJob = page(() => import("./pages/Deck"), (m) => m.DeckJob);
const DeckReplay = page(() => import("./pages/Deck"), (m) => m.DeckReplay);
const Gallery = page(() => import("./pages/Gallery"), (m) => m.default);
const ReportTrace = page(() => import("./pages/Trace"), (m) => m.ReportTrace);
const JobTrace = page(() => import("./pages/Trace"), (m) => m.JobTrace);

/** A quiet placeholder while a page's code arrives (usually a few frames). */
function PageLoading() {
  return (
    <div role="status" className="wrap py-10">
      <span className="sr-only">Memuat halaman…</span>
      <span aria-hidden className="block h-9 w-64 animate-pulse rounded bg-raised" />
    </div>
  );
}
const suspend = (node: React.ReactNode) => <Suspense fallback={<PageLoading />}>{node}</Suspense>;

const TITLES: [RegExp, string][] = [
  [/^\/$/, "Sectoral: company update emiten BEI dengan metode valuasi berbasis gerbang"],
  [/^\/research$/, "Deck riset | Sectoral"],
  [/\/putar$/, "Putar ulang riset | Sectoral"],
  [/^\/laporan$/, "Laporan | Sectoral"],
  [/\/jejak$/, "Jejak riset | Sectoral"],
  [/^\/jobs\//, "Riset emiten | Sectoral"],
];

function DocumentTitle() {
  const { pathname } = useLocation();
  useEffect(() => {
    document.title = TITLES.find(([re]) => re.test(pathname))?.[1] ?? "Sectoral";
  }, [pathname]);
  return null;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <DocumentTitle />
      <Routes>
        <Route element={<Layout />}>
          <Route index element={suspend(<Landing />)} />
          <Route path="research" element={suspend(<DeckLaunch />)} />
          <Route path="jobs/:id" element={suspend(<DeckJob />)} />
          <Route path="laporan/:ticker/putar" element={suspend(<DeckReplay />)} />
          <Route path="jobs/:id/jejak" element={suspend(<JobTrace />)} />
          <Route path="laporan" element={suspend(<Gallery />)} />
          <Route path="laporan/:ticker/jejak" element={suspend(<ReportTrace />)} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);

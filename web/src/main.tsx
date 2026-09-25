import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import "./index.css";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import { DeckJob, DeckLaunch, DeckReplay } from "./pages/Deck";
import Gallery from "./pages/Gallery";
import { JobTrace, ReportTrace } from "./pages/Trace";
import NotFound from "./pages/NotFound";

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
          <Route index element={<Landing />} />
          <Route path="research" element={<DeckLaunch />} />
          <Route path="jobs/:id" element={<DeckJob />} />
          <Route path="laporan/:ticker/putar" element={<DeckReplay />} />
          <Route path="jobs/:id/jejak" element={<JobTrace />} />
          <Route path="laporan" element={<Gallery />} />
          <Route path="laporan/:ticker/jejak" element={<ReportTrace />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);

import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="wrap py-24">
      <h1 className="mb-3 text-3xl font-black">Halaman tidak ditemukan</h1>
      <p className="mb-6 text-ink-soft">Alamat ini tidak ada di Sectoral. Mulai riset baru atau buka laporan yang sudah terbit.</p>
      <div className="flex flex-wrap gap-3">
        <Link className="btn btn-primary" to="/research">Coba riset emiten</Link>
        <Link className="btn btn-ghost" to="/laporan">Lihat laporan</Link>
      </div>
    </div>
  );
}

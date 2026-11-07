/** Choose a meaningful local illustration from the shot, never a hash of text.
 *  The approved on-screen title has precedence over generic subject keywords.
 */
export function treatmentFor(shot) {
  const title = String(shot.title || '').toLowerCase();
  const text = (title + ' ' + String(shot.subject || '')).toLowerCase();
  const tests = [
    ['calendar', /(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember|tanggal|kronologi|timeline)/i],
    ['facilities', /(fasilitas|lokasi|gedung|cabang|facility|facilities|data center|rumah sakit)/i],
    ['warning', /(ganggu|terhenti|outage|down|gagal|risiko|bahaya|ancaman|warning|krisis)/i],
    ['security', /(siber|cyber|security|keamanan|peretas|enkripsi|firewall|serangan)/i],
    ['verified', /(resmi|verifikasi|cek fakta|sumber|verified|klarifikasi|informasi)/i],
    ['medical', /(darah|blood|donor|transfusi)/i],
    ['device', /(aplikasi|ponsel|telepon|laptop|dashboard|perangkat|device|layar)/i],
    ['people', /(manusia|orang|pasien|pegawai|pengguna|pelanggan|masyarakat|people|tim)/i],
  ];
  for (const [kind, pattern] of tests) {
    if (pattern.test(title)) return kind;
  }
  for (const [kind, pattern] of tests) {
    if (pattern.test(text)) return kind;
  }
  if (shot.family === 'data' || /(?<![\w.,+−-])[+−-]?\d+(?:[.,]\d+)*(?:\s*%)?/.test(title)) return 'data';
  return 'story';
}

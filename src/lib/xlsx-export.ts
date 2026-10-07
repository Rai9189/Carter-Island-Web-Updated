import type { Cell } from 'write-excel-file/browser'

/**
 * Unduh tabel sebagai .xlsx. Angka tetap angka (bisa dijumlah di Excel,
 * desimal mengikuti locale Excel pengguna). Library di-import saat tombol
 * diklik agar tidak menambah bundle halaman.
 */
export async function downloadXlsx(filename: string, headers: string[], rows: Cell[][]) {
  const { default: writeXlsxFile } = await import('write-excel-file/browser')
  const data: Cell[][] = [headers.map(h => ({ value: h, fontWeight: 'bold' as const })), ...rows]
  const text = (c: Cell) => String((c && typeof c === 'object' && 'value' in c ? c.value : c) ?? '')
  const columns = headers.map((_, i) =>
    ({ width: Math.min(40, Math.max(10, ...data.map(r => text(r[i]).length + 2))) }))
  // Karakter terlarang di nama file Windows
  await writeXlsxFile(data, { columns, stickyRowsCount: 1 }).toFile(filename.replace(/[\\/:*?"<>|]/g, '-'))
}

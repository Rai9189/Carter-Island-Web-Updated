// src/components/providers/SWRProvider.tsx
'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { SWRConfig } from 'swr';
import { toast } from 'sonner';
import { isApiStatus } from '@/lib/api-client';

const TOAST_ID = 'swr-fetch-error';

// Endpoint yang sedang gagal — satu toast untuk semuanya agar polling
// (tiap 2-5 detik) tidak menumpuk toast, dan hilang sendiri saat semua pulih
const failingKeys = new Set<string>();

function showFailingToast() {
  toast.error('Gagal memuat data dari server', {
    id: TOAST_ID,
    description: `${failingKeys.size} permintaan gagal. Data di halaman ini mungkin tidak terbaru.`,
    duration: Infinity,
  });
}

function markRecovered(key: string) {
  if (!failingKeys.delete(key)) return;
  if (failingKeys.size === 0) toast.dismiss(TOAST_ID);
  else showFailingToast();
}

export default function SWRProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // Pindah halaman: key halaman lama tidak akan di-request lagi, jadi jangan
  // biarkan toast tertahan karenanya. Halaman baru mendaftarkan ulang kalau masih gagal.
  useEffect(() => {
    failingKeys.clear();
    toast.dismiss(TOAST_ID);
  }, [pathname]);

  return (
    <SWRConfig
      value={{
        onError: (err, key) => {
          // 404 = data memang kosong (mis. tidak ada sesi aktif), bukan error —
          // dan berarti server sudah terjangkau lagi kalau sebelumnya gagal.
          // 401 sudah ditangani api-client (logout + redirect ke login).
          if (isApiStatus(err, 404) || isApiStatus(err, 401)) {
            markRecovered(String(key));
            return;
          }
          failingKeys.add(String(key));
          showFailingToast();
        },
        onSuccess: (_data, key) => markRecovered(String(key)),
      }}
    >
      {children}
    </SWRConfig>
  );
}

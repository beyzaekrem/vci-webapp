# VCI WebApp – Geliştirici & Mimari Kılavuzu 🚀

Bu doküman, projeyi devralan yazılımcıların sayfa düzenlerini, bileşen (component) hiyerarşisini, tema motorunu ve ağ katmanını hızlıca anlaması için hazırlanmıştır.

---

## 📁 1. Dizin ve Klasör Yapısı

```
src/
├── Components/
│   ├── features/              # Sayfalara özel gelişmiş modüller
│   │   ├── PreviewStreams/   # 2D Stage Spatial Map, Canlı Yayın & Kamera Önizleme
│   │   │   ├── PreviewStreamsPage.tsx
│   │   │   ├── StageSpatialMap.tsx
│   │   │   ├── CameraPreview.tsx
│   │   │   ├── ServerFilters.tsx
│   │   │   └── previewStreams.css
│   │   ├── VCIAutomation/     # Script seçimi, form parametreleri & canlı loglar
│   │   │   ├── ScriptList.tsx
│   │   │   ├── VCIAutomationScript.tsx
│   │   │   ├── ScriptArgumentsForm.tsx
│   │   │   ├── ScriptOutput.tsx
│   │   │   └── vciAutomation.css
│   │   └── Config/            # Sistem konfigürasyonu & ortam presetleri
│   │       └── Settings.tsx
│   ├── shared/                # Tüm uygulamada ortak kullanılan bileşenler
│   │   ├── Sidebar/           # Sol navigasyon çubuğu & Mobil Offcanvas çekmecesi
│   │   │   ├── Sidebar.tsx
│   │   │   └── sidebar.css
│   │   └── ServerStatusModal/ # Bağlantı durumu modalı & Header aksiyon butonları
│   │       ├── ServerStatusModal.tsx
│   │       └── ServerStatusModal.css
├── pages/                     # Ana sayfa görünümleri ve yönlendirme kapıları
│   ├── Dashboard.tsx          # Sistem durum özeti & Dark/Light mode anahtarı
│   ├── Start.tsx              # Capture Server Genel Durumu (Server Overview)
│   ├── VCIAutomation.tsx      # Otomasyon ve script çalıştırma sayfası
│   ├── Config.tsx             # Ayarlar yönlendirme sayfası
│   └── index.ts
├── Utility/
│   ├── Theme/                 # Dark / Light Mode Context ve persistence
│   │   └── ThemeContext.tsx
│   ├── Storage/               # LocalStorage yönetimi
│   └── UI/                    # Ortak UI rozetleri ve bildirim pencereleri
├── network/                   # WebSocket ve API bağlantı katmanı
│   ├── capture-server/        # Kamera sunucuları ağı
│   ├── control-server/        # Kontrol sunucusu bağlantısı
│   └── vci-automation/        # Otomasyon servis yöneticisi
├── router.tsx                 # React Router (Sayfa yolları)
├── index.css                  # Global tasarım CSS token'ları & Bootstrap override'ları
└── main.tsx                   # React giriş noktası
```

---

## 🎨 2. Tema ve CSS Değişkenleri Motoru

Uygulama tam uyumlu **Dark Mode** ve **Light Mode** renk mimarisine sahiptir.
Renk değişkenleri `index.css` içerisinde tanımlanmıştır ve `ThemeContext.tsx` üzerinden `<html>` elementine `data-theme="dark"` / `data-theme="light"` özniteliği atanarak kontrol edilir.

- **Ana Renk Değişkenleri:**
  - `var(--vci-bg)`: Sayfa genel arka planı.
  - `var(--vci-card-bg)`: Kartlar ve panellerin arka planı.
  - `var(--vci-text-main)`: Ana okunabilir metin rengi.
  - `var(--vci-text-muted)`: İkincil / soluk açıklama metinleri.
  - `var(--vci-primary)`: Vurgulu mavi tonu (`#0284c7`).
  - `var(--vci-surface-2)`: İç içe geçmiş eleman arka planları.

> **Önemli Not:** Bootstrap bileşenlerinin varsayılan beyaz arka plan basmasını engellemek için `index.css` dosyasında kapsamlı Bootstrap Override kuralları yer almaktadır. Yeni bileşen eklerken `var(--vci-*)` değişkenlerini tercih ediniz.

---

## 📱 3. Mobil ve Responsive Tasarım Prensipleri

Tüm sayfalar (Preview, VCI Automation, Server Status, Settings) mobilde (`<= 768px`) özel olarak optimize edilmiştir:
- **Offcanvas Sidebar:** Mobilde sol üstteki hamburger butonuna tıklandığında yumuşatılmış animasyonla açılır.
- **Segmented Tab Bar:** Sayfalarda (Preview'da *2D Map / Live Stream*, Settings'te *Control / Automation / Capture*) mobilde sekmeli kolay geçiş sağlar.
- **Zorunlu Alanlar (Mandatory Fields):** VCI Automation formlarındaki zorunlu parametreler kırmızılı yıldız (`*`) ve rozetler ile belirtilir.

---

## 🔧 4. Yaygın İşlemler ve Geliştirici İpuçları

1. **Yeni Bir Sayfa / Rota Eklemek:**
   - Sayfanızı `src/pages/` dizinine ekleyin.
   - `src/router.tsx` dosyasında rotayı tanımlayın.
   - `src/Components/shared/Sidebar/Sidebar.tsx` dosyasına `NavLink` ikon ve bağlantısını ekleyin.

2. **Sunucu Ortamı Değiştirmek:**
   - **Settings** sayfasındaki **Quick Environment Presets** butonlarını kullanarak tek tıkla *Simulated (Local 127.0.0.1)* veya *Real Production Rig (10.3.10.x)* modları arasında geçiş yapabilirsiniz.

3. **Kısayollar ve Yardım Modalı:**
   - Klavyeden `h` tuşuna basarak veya sayfa header'larındaki `Help & Shortcuts (h)` butonuna tıklayarak kısayol ve yardım modalını tetikleyebilirsiniz.

---

*VCI WebApp Ekibi tarafından hazırlanmıştır.*

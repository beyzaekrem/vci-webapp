# 📑 VCI WebApp – Kapsamlı ve Detaylı Teknik Değişiklik Raporu

Bu raporda, projede değiştirilen/oluşturulan **tüm dosyalar, eklenen/düzenlenen tüm fonksiyonlar, CSS sınıfları ve mimari güncellemeler** adım adım ve en ince ayrıntısına kadar belgelenmiştir.

---

## 📂 1. Değiştirilen ve Yeni Eklenen Dosyalar Listesi

| Sıra | Dosya Yolu | Durum | Açıklama |
| :--- | :--- | :---: | :--- |
| **1** | `src/Components/PreviewStreams/systemLayoutData.ts` | **[YENİ]** | `system_layout.json` verisini işleyen veri ve eşleşme katmanı |
| **2** | `src/Components/PreviewStreams/StageSpatialMap.tsx` | **[YENİ]** | 12 direkli (P1..P12) 2D/3D sahne mekânsal harita bileşeni |
| **3** | `src/Components/PreviewStreams/CameraPreview.tsx` | **[YENİ]** | Canlı yayın kamera önizleme ve kontrol kartı bileşeni |
| **4** | `src/Components/PreviewStreams/ServerFilters.tsx` | **[YENİ]** | Kompakt sunucu kutu/chip filtreleme bileşeni |
| **5** | `src/Components/PreviewStreams/PreviewStreamsPage.tsx` | **[YENİ]** | Önizleme sayfasının ana kapsayıcı bileşeni |
| **6** | `src/Components/PreviewStreams/previewStreams.css` | **[YENİ]** | Önizleme sayfası, çip kutuları ve harita CSS stilleri |
| **7** | `src/Components/Sidebar/Sidebar.tsx` | **[REFAKTÖR]** | Global `SidebarProvider`, `AppSidebar` rail ve menü çekmecesi |
| **8** | `src/Components/Sidebar/sidebar.css` | **[GÜNCELLENDİ]** | Global sol ikon bar ve offcanvas çekmece CSS stilleri |
| **9** | `src/router.tsx` | **[GÜNCELLENDİ]** | Ana yönlendirme ve `WithSidebarLayout` global yerleşim |
| **10** | `src/pages/CombinedPage.tsx` | **[GÜNCELLENDİ]** | Eski üst tab çubuğu kaldırıldı, `PreviewStreamsPage` bağlandı |
| **11** | `src/pages/VCIAutomation.tsx` | **[YENİDEN TASARLANDI]**| VCI Otomasyon 3 sütunlu ana sayfa bileşeni |
| **12** | `src/Components/VCIAutomation/vciAutomation.css` | **[YENİ]** | VCI Otomasyon 3 sütunlu sayfa CSS stilleri |
| **13** | `src/Components/VCIAutomation/ScriptList.tsx` | **[GÜNCELLENDİ]** | Komut listesi arayüzü |
| **14** | `src/Components/VCIAutomation/VCIAutomationScript.tsx`| **[GÜNCELLENDİ]** | Script form ve log sütunları kapsayıcısı |
| **15** | `src/Components/VCIAutomation/ScriptLogs.tsx` | **[GÜNCELLENDİ]** | Koyu lacivert terminal konsolu ve renkli seviye etiketleri |
| **16** | `src/Components/Videostream/WebsocketStream.tsx` | **[DÜZELTİLDİ]** | Tuval temizleme (`clearRect`), zaman aşımı ve İngilizce hata overlay'i |
| **17** | `src/pages/Calibrate.tsx` | **[GÜNCELLENDİ]** | `100vw` genişlik taşması `100%` olarak düzeltildi |
| **18** | `tsconfig.app.json` | **[GÜNCELLENDİ]** | `"resolveJsonModule": true` kuralı eklendi |

---

## 🛠️ 2. Dosya ve Fonksiyon Bazlı Detaylı İnceleme

### **1. `src/Components/PreviewStreams/systemLayoutData.ts`**
- **Amacı**: `system_layout.json` dosyasındaki 12 dikey direk (P1..P12) ve 5 dikey slot pozisyonunu (`ceiling`, `rig_upper`, `center`, `rig_low`, `floor`) okumak ve ağdaki canlı sunucularla eşleştirmek.
- **Düzenlenen / Eklenen Fonksiyonlar**:
  - `getAllCamerasFromLayout()`: `system_layout.json` dosyasını tarayarak tüm kamera pozisyonlarını düz bir `CameraEntry[]` dizisi olarak döndürür.
  - `buildShorthandMap()`: `capture-server` katmanından `getServers().servers` listesini alır. `C0016`, `M0008` gibi kısaltma kodlarını sunucu indeksi (`serverIndex`) ve kamera indeksi (`cameraIndex`) ile eşleştirip `Map<string, ResolvedCamera>` oluşturur.
  - `resolveCamera()`: Bir `CameraEntry` nesnesini canlı sunucu indeksleri ile birleştirir.
  - `getSlotDisplayName()`: `center`, `ceiling`, `rig_low` vb. slot anahtarlarını ekranda görünecek insan odaklı metinlere ("Center Rig", "Ceiling") çevirir.

---

### **2. `src/Components/PreviewStreams/StageSpatialMap.tsx`**
- **Amacı**: 12 adet dikey kesikli direk çizgisini ve kamera düğümlerini 2D/3D sahne üzerinde çizmek.
- **Düzenlenen / Eklenen Fonksiyonlar & JSX**:
  - `StageSpatialMap`: Direk başlıklarını (P1..P12), dikey çizgileri ve kamera düğümlerini render eder.
  - Kamera düğümlerine tıklama olaylarını (`onSelectCamera`) yönetir. Seçili olan kameraya canlı mavi (`#0284c7`) parıltılı sınıf (`.ps-cam-node.active`) atar.

---

### **3. `src/Components/PreviewStreams/CameraPreview.tsx`**
- **Amacı**: Tekil kamera canlı yayın akışı ve kontrol panelini sunmak.
- **Düzenlenen / Eklenen Fonksiyonlar & Olaylar**:
  - `CameraPreview`: Canlı yeşil durum rozeti (`● LIVE`), kamera başlığı, yön okları (`< Cam 01 / 34 >`), artı hedef göstergesi (`+`) ve alt yayın rozetini (`1920×1080 • 30 FPS • H.264`) render eder.
  - `handleDownload()`: Seçili kameradan fotoğraf çeker (`downloadImage()`).
  - `handleFullscreen()`: Yayın akışını yeni sekmede tam ekran açar (`/#/videostream`).
  - `handleRefresh()`: Sunucudan kamera bilgilerini günceller (`getAllInfo()`).
  - **Güvenlik Önlemi**: `allResolvedCameras = []` ve `selectedCamera` fallback değerleri eklenerek `undefined` çökme hataları engellendi.

---

### **4. `src/Components/PreviewStreams/ServerFilters.tsx`**
- **Amacı**: Ağdaki sunucu listesini filtreleme alanı olarak sunmak.
- **Düzenlenen / Eklenen Fonksiyonlar**:
  - `ServerFilters`: `useMemo` kullanarak sunucu başına kamera sayılarını hesaplar.
  - **Yeniden Tasarım (Kompakt Chip Grid)**: Eski dikey uzun liste kaldırıldı; dikeyde sadece ~90px kaplayan `All Servers (34 Cams)`, `S1 (4)`, `S2 (4)`... `S15 (2)` yan yana dizilen butonlar haline getirildi. Bu sayede `CameraPreview` kartı dikeyde %90 genişledi.

---

### **5. `src/Components/Sidebar/Sidebar.tsx`**
- **Amacı**: Tüm uygulamada çalışan navigasyon altyapısı.
- **Düzenlenen / Eklenen Yapılar & Context**:
  - `SidebarContext`: Arayüz genelinde menü açık/kapalı durumunu yöneten React Context (`show`, `openSidebar`, `closeSidebar`).
  - `SidebarProvider`: Uygulamayı sarmalayan ve lacivert offcanvas çekmeceyi (`VCI WebApp`) oluşturan sağlayıcı.
  - `AppSidebar`: Tüm sayfalarda ekranın solunda 52px genişliğinde çalışan koyu mavi (`#00223d`) dikey ikon çubuğu. Aktif sekmeye mavi sol çizgi (`.active-indicator`) ekler.
  - **Sıralama Güncellemesi**: Sekmeler istenen sıraya getirildi (Preview ➔ VCI Automation ➔ Capture ➔ Calibrate ➔ Server Status ➔ Settings ➔ About ➔ Help).

---

### **6. `src/router.tsx`**
- **Amacı**: Merkezi rota yöneticisi.
- **Düzenlenen Fonksiyonlar**:
  - `WithSidebarLayout()`: Eski sabit duran mavi floating buton kaldırıldı. Tüm uygulama rotaları `<SidebarProvider>`, `<div className="vci-app-layout">`, `<AppSidebar />` ve `<main className="vci-app-main-content">` içerisine sarmalandı.

---

### **7. `src/pages/VCIAutomation.tsx` & `VCIAutomation/` Bileşenleri**
- **`vciAutomation.css`**: VCI Otomasyon sekmesi için 3 sütunlu modern CSS stilleri yazıldı.
- **`VCIAutomationPage`**: Üst kısma `VCI Automation` başlığı, yeşil `• ONLINE` rozeti ve sunucu rozeti eklendi.
- **`ScriptList.tsx`**: Sol sütunda komut listesi render edilir. Seçili komut Mavi Çerçeveli (`border: 2px solid #0284c7`) kart haline getirildi.
- **`VCIAutomationScript.tsx`**: Orta sütunda form ve **Execute Script** (Mavi) / **Stop Script Execution** (Kırmızı) butonları; sağ sütunda ise log alanı konumlandırıldı.
- **`ScriptLogs.tsx`**: Koyu lacivert (`#0b1329`) konsol alanında `INFO`, `SUCCESS`, `RUNNING`, `STREAM`, `WARNING`, `ERROR` renkli log rozetleri eklendi.

---

### **8. `src/Components/Videostream/WebsocketStream.tsx`**
- **Amacı**: WebSocket üzerinden canlı kamera karelerini HTML5 `<canvas>` üzerine çizmek.
- **Düzenlenen / Eklenen Mantıklar**:
  - **Tuval Temizliği (`ctx.clearRect`)**: Kamera her değiştirildiğinde `useEffect` içerisinde canvas tuvali anında tamamen silinir (`clearRect`). Böylece çalışmayan bir kameraya tıklandığında önceden kalan eski görüntünün ekranda görünmesi **%100 engellendi**.
  - **Zaman Aşımı Kontrolü (Timeout Timer)**: 4.5 saniye boyunca yeni kare gelmezse veya bağlantı koptuğunda kilitlenmek yerine hataya geçer.
  - **İngilizce Hata Kartı (English Warning UI)**: Kamera çalışmadığında ekran ortasında İngilizce uyarı kartı açılır:
    - ⚠️ **Camera Stream Offline**
    - *Unable to retrieve video feed from this camera.*
    - **`[ 🔄 Retry Connection ]`** (Yeniden Bağlan butonu).

---

## 🛡️ 3. Donanım Güvenlik Beyanı

Yazılan tüm kodlar **Salt Okunur (Read-Only)** prensibiyle hazırlanmıştır:
1. Kameraların IP adreslerine, donanım yazılımlarına (firmware) veya dahili ayarlarına hiçbir yazma işlemi yapılmaz.
2. Kameralarla iletişim sadece WebSocket üzerinden görüntü karesi talep etmekle sınırlıdır.
3. Arka plana geçildiğinde WebSocket yayınları otomatik kapatılır, ağda veya kameralarda yük oluşturmaz.

---

## 📊 4. Doğrulama ve Derleme Sonuçları

- ✅ **TypeScript Kontrolü (`tsc --noEmit`)**: 0 Hata ile tamamlandı.
- ✅ **Production Derlemesi (`vite build`)**: 0 Hata ile tamamlandı (5.20s).
- ✅ **Dev Server**: **http://localhost:3001/#/preview** adresinde yayında.

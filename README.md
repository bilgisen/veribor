# veribor

BIST canlı fiyat verisi **alternatif kaynağı** — FastAPI Cloud üzerinde çalışır.

İş Yatırım, Cloudflare Worker IP adreslerini engellediği için mevcut /finveri (tekapi.jetborsa.com) doğrudan veri çekemiyor. veribor, FastAPI Cloud (engellenmeyen altyapı) üzerinde çalışıp aynı veriyi `/finveri`, `/hono` ve `/tanstack` için servis eder.

## Kaynaklar

| Kaynak | Ad | Veri | Açıklama |
|---|---|---|---|
| Anadolu Ajansı | `ajans` | bist_stocks, market_summary | `sektorId=1` detay uç noktası **~624 hisseyi tek istekte** döner; endeksler ayrı uç noktada |
| İş Yatırım | `iyi` | market_summary, enrichment | `OneEndeks?endeks=A,B,C` virgüllü batch; bid/ask + haftalık/aylık/yıllık kapanışlar içerir |
| Oyak Yatırım | `oya` | instruments | `GetAllInstruments` enstrüman kataloğu (~13.5k kayıt) |

Bellek içi / Redis cache'e yazan arka plan senkronizasyon döngüsü (~60s) — hesaplama yok, sadece normalizasyon + cache + servis.

## Uç Noktalar

```
GET /health                → durum, kaynak status, son güncelleme
GET /stocks                 → {total, last_updated, data:[StockQuote]}
GET /stocks/{code}          → tek hisse
GET /stocks/gainers?limit   → en çok yükselenler
GET /stocks/losers?limit    → düşenler
GET /summary                → navbar endeksleri (XU100, XU030, XBANK...)
GET /indices                → endeksler (alias)
GET /indices/{code}         → tek endeks
GET /instruments?type=&q=   → Oyak kataloğu (IMKB/VIOP/FON...)
GET /quote/{code}           → İş Yatırım ham veri passthrough (30s cache)
POST /admin/refresh         → manuel tazeleme
```

`StockQuote` şeması `/finveri/src/app/models/instrument.py` ile **birebir uyumludur**:

```json
{
  "code": "ASELS", "name": "ASELSAN", "type": "IMKB",
  "last_price": 359, "diff_price": 12.25, "diff_percent": 3.53,
  "volume": 30404516, "record_date": "2026-08-06T...", "source": "ajans",
  "week_close": 337.5, "month_close": 383, "year_close": 181.36,
  "change_week_pct": ..., "bid": 358, "ask": 358.25
}
```

## Ortam Değişkenleri

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `REDIS_URL` | (boş) | FastAPI Cloud Redis entegrasyonu otomatik enjekte eder |
| `SYNC_INTERVAL_SECONDS` | 60 | Arka plan tazeleme aralığı |
| `STALE_AFTER_SECONDS` | 120 | Cache bu süre sonra bayatsa istek anında refresh |
| `ENABLE_ISY_ENRICHMENT` | true | AA hisselerini İşY batch ile zenginleştir (bid/ask + periyodik kapanışlar) |
| `ISY_CHUNK_SIZE` | 100 | İşY batch parça boyutu |
| `CORS_ORIGINS` | jetborsa.com + localhost:3000 | Virgüllü liste |

## Yerel Çalıştırma

```bash
uv sync
uv run pytest                  # canlı kaynak testleri
uv run fastapi dev main.py     # geliştirme sunucusu (http://localhost:8000)
```

## Deploy (FastAPI Cloud)

```bash
fastapi login
fastapi deploy
```

Dashbor'dan Redis Cloud entegrasyonu bağlanırsa `REDIS_URL` otomatik enjekte edilir.
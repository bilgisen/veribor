"""Ayarlar — ortam değişkenleriyle yapılandırma."""

import os
from dataclasses import dataclass, field


def _csv(name: str, default: str) -> list[str]:
    return [o.strip() for o in os.getenv(name, default).split(",") if o.strip()]


@dataclass
class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "veribor")
    APP_VERSION: str = os.getenv("APP_VERSION", "0.1.0")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    PORT: int = int(os.getenv("PORT", "8000"))

    # Redis (FastAPI Cloud Redis entegrasyonu REDIS_URL'i otomatik enjekte eder)
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    # Upstash Redis (REST API) — REDIS_URL yoksa kullanılır
    UPSTASH_REDIS_REST_URL: str = os.getenv("UPSTASH_REDIS_REST_URL", "")
    UPSTASH_REDIS_REST_TOKEN: str = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

    # Senkronizasyon
    SYNC_INTERVAL_SECONDS: int = int(os.getenv("SYNC_INTERVAL_SECONDS", "60"))
    STALE_AFTER_SECONDS: int = int(os.getenv("STALE_AFTER_SECONDS", "120"))
    HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))

    # CORS
    CORS_ORIGINS: list[str] = field(
        default_factory=lambda: _csv(
            "CORS_ORIGINS",
            "https://jetborsa.com,http://localhost:3000,http://127.0.0.1:3000",
        )
    )

    # Kaynak URL'leri
    AA_STOCKS_URL: str = os.getenv(
        "AA_STOCKS_URL",
        "https://aafinans.com/Veri/SektorEndeksineAitTradeStatistics3leriVerDetay?sektorId=1",
    )
    AA_INDICES_URL: str = os.getenv(
        "AA_INDICES_URL",
        "https://aafinans.com/Veri/SektorEndeksleriniGetir",
    )
    ISYATIRIM_ONE_ENDEKS_URL: str = os.getenv(
        "ISYATIRIM_ONE_ENDEKS_URL",
        "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/OneEndeks",
    )
    OYAK_INSTRUMENTS_URL: str = os.getenv(
        "OYAK_INSTRUMENTS_URL",
        "https://www.oyakyatirim.com.tr/Home/GetAllInstruments",
    )

    # İş Yatırım batch ayarları
    # Not: İşY batch isteği başına ~20 sembol limitlidir (25+ kod boş yanıt döner).
    ISY_CHUNK_SIZE: int = int(os.getenv("ISY_CHUNK_SIZE", "20"))
    # True ise AA hisseleri İş Yatırım batch istekleriyle zenginleştirilir
    # (bid/ask, weekClose/monthClose/yearClose gibi AA'da olmayan alanlar).
    ENABLE_ISY_ENRICHMENT: bool = os.getenv("ENABLE_ISY_ENRICHMENT", "true").lower() == "true"
    # Zenginleştirme baz senkronizasyondan daha seyrek çalışır (istek hacmini düşürür)
    ENRICH_INTERVAL_SECONDS: int = int(os.getenv("ENRICH_INTERVAL_SECONDS", "300"))

    # TA motoru fiyat geçmişi — tapi2 (D1 finveri-db) üzerinden
    TAPI2_HISTORY_URL: str = os.getenv("TAPI2_HISTORY_URL", "https://tapi2.jetborsa.workers.dev")

    # Navbar/endeks listesi (AA SektorEndeksleriniGetir ile uyumlu)
    INDEX_CODES: list[tuple[str, str]] = field(
        default_factory=lambda: [
            ("XU100", "BIST 100"),
            ("XU030", "BIST 30"),
            ("XU050", "BIST 50"),
            ("XU500", "BIST 500"),
            ("XUTUM", "BIST TUM"),
            ("XTUMY", "BIST TUM-100"),
            ("XBANK", "BIST Banka"),
            ("XUSIN", "BIST Sinai"),
            ("XHOLD", "BIST Holding ve Yatirim"),
            ("XUMAL", "BIST Mali"),
            ("XUTEK", "BIST Teknoloji"),
            ("XUHIZ", "BIST Hizmetler"),
            ("XUSRD", "BIST Surdurulebilirlik"),
            ("XULAS", "BIST Ulastirma"),
            ("XK100", "BIST Katilim 100"),
            ("TLREF", "TL Referans Faiz"),
        ]
    )

    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )


settings = Settings()

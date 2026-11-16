-- Hukupedia şeması — ilk açılışta otomatik uygulanır
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS belgeler (
  id         BIGSERIAL PRIMARY KEY,
  belge_id   TEXT UNIQUE NOT NULL,      -- 'yargitay_1206338400' gibi
  kaynak     TEXT NOT NULL,             -- yargitay | danistay | aym | mevzuat
  daire      TEXT,
  konu_grubu TEXT,                      -- AILE | IS_HUKUKU | VERGI | ...
  esas_no    TEXT,
  karar_no   TEXT,
  tarih      TEXT,
  metin      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parcalar (
  id        BIGSERIAL PRIMARY KEY,
  belge_id  BIGINT NOT NULL REFERENCES belgeler(id) ON DELETE CASCADE,
  sira      INT NOT NULL,
  metin     TEXT NOT NULL,
  embedding vector(1024)               -- bge-m3 çıktısı
);

CREATE INDEX IF NOT EXISTS ix_belgeler_kaynak ON belgeler (kaynak);
CREATE INDEX IF NOT EXISTS ix_belgeler_konu   ON belgeler (konu_grubu);
-- HNSW indeksi toplu yüklemeden SONRA kurulur (pipeline sonunda) — yükleme 10x hızlı olur

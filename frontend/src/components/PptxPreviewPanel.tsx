import { useState, useEffect, useRef, useCallback } from 'react'
import {
  ChevronLeft, ChevronRight, Maximize2, Minimize2,
  Loader2, AlertCircle, Download, BarChart2, Table,
  Columns, FileText, Star, TrendingUp, Keyboard,
  RefreshCw, Play, Pause
} from 'lucide-react'
import { apiClient, downloadPptx } from '../services/api'

interface SlideMeta {
  title: string
  type: string
  slide_number: number
}

interface PptxPreviewPanelProps {
  presentationId: string
  inline?: boolean
  onClose?: () => void
  onReady?: () => void
}

const TYPE_CONFIG: Record<string, { icon: any; label: string; color: string; bg: string }> = {
  title:      { icon: Star,      label: 'Title',      color: '#818cf8', bg: '#1e1b4b' },
  content:    { icon: FileText,  label: 'Content',    color: '#60a5fa', bg: '#1e3a5f' },
  chart:      { icon: BarChart2, label: 'Chart',      color: '#34d399', bg: '#064e3b' },
  table:      { icon: Table,     label: 'Table',      color: '#fbbf24', bg: '#451a03' },
  comparison: { icon: Columns,   label: 'Comparison', color: '#f472b6', bg: '#500724' },
  metric:     { icon: TrendingUp,label: 'Metric',     color: '#a78bfa', bg: '#2e1065' },
}

function SlideTypeIcon({ type, size = 14 }: { type: string; size?: number }) {
  const cfg = TYPE_CONFIG[type] || TYPE_CONFIG.content
  const Icon = cfg.icon
  return <Icon style={{ width: size, height: size, color: cfg.color }} />
}

function TypeBadge({ type }: { type: string }) {
  const cfg = TYPE_CONFIG[type] || TYPE_CONFIG.content
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold"
      style={{ backgroundColor: cfg.bg, color: cfg.color, border: `1px solid ${cfg.color}30` }}
    >
      <SlideTypeIcon type={type} size={10} />
      {cfg.label}
    </span>
  )
}

export default function PptxPreviewPanel({
  presentationId,
  inline = false,
  onClose,
  onReady,
}: PptxPreviewPanelProps) {
  const [images, setImages] = useState<string[]>([])
  const [slideMeta, setSlideMeta] = useState<SlideMeta[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [current, setCurrent] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)
  const [showKeys, setShowKeys] = useState(false)
  const [autoPlay, setAutoPlay] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [imgLoaded, setImgLoaded] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const autoPlayRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load preview images + metadata
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setImgLoaded(false)

    apiClient
      .post(`/presentations/${presentationId}/export/pptx/preview-images`)
      .then((res) => {
        if (!cancelled) {
          setImages(res.data.images || [])
          setSlideMeta(res.data.slide_meta || [])
          setCurrent(0)
          setLoading(false)
          onReady?.()
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || err?.message || 'Preview generation failed')
          setLoading(false)
          // Still signal ready on error so progress bar doesn't stay stuck
          onReady?.()
        }
      })

    return () => { cancelled = true }
  }, [presentationId])

  const goTo = useCallback((idx: number) => {
    if (idx < 0 || idx >= images.length) return
    setImgLoaded(false)
    setCurrent(idx)
  }, [images.length])

  const prev = useCallback(() => goTo(current - 1), [goTo, current])
  const next = useCallback(() => goTo(current + 1), [goTo, current])

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); prev() }
      else if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') { e.preventDefault(); next() }
      else if (e.key === 'f' || e.key === 'F') setFullscreen((v) => !v)
      else if (e.key === 'Escape') { setFullscreen(false); setAutoPlay(false); onClose?.() }
      else if (e.key === 'p' || e.key === 'P') setAutoPlay((v) => !v)
      else if (e.key === '?') setShowKeys((v) => !v)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [prev, next, onClose])

  // Auto-play
  useEffect(() => {
    if (autoPlay && images.length > 1) {
      autoPlayRef.current = setInterval(() => {
        setCurrent((c) => {
          if (c >= images.length - 1) { setAutoPlay(false); return c }
          setImgLoaded(false)
          return c + 1
        })
      }, 3000)
    }
    return () => { if (autoPlayRef.current) clearInterval(autoPlayRef.current) }
  }, [autoPlay, images.length])

  // Fullscreen API
  useEffect(() => {
    if (fullscreen && containerRef.current) {
      containerRef.current.requestFullscreen?.().catch(() => {})
    } else if (!fullscreen && document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {})
    }
  }, [fullscreen])

  useEffect(() => {
    const onFsChange = () => { if (!document.fullscreenElement) setFullscreen(false) }
    document.addEventListener('fullscreenchange', onFsChange)
    return () => document.removeEventListener('fullscreenchange', onFsChange)
  }, [])

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const response = await downloadPptx(presentationId)
      const disposition = response.headers['content-disposition'] || ''
      const match = disposition.match(/filename="?([^";\n]+)"?/)
      const filename = match ? match[1] : 'presentation.pptx'
      const url = URL.createObjectURL(new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      }))
      const a = document.createElement('a')
      a.href = url; a.download = filename
      document.body.appendChild(a); a.click()
      document.body.removeChild(a); URL.revokeObjectURL(url)
    } catch {}
    setDownloading(false)
  }

  const meta = slideMeta[current]
  const progress = images.length > 0 ? ((current + 1) / images.length) * 100 : 0

  const content = (
    <div
      ref={containerRef}
      className={`flex flex-col ${fullscreen ? 'fixed inset-0 z-50' : 'w-full max-w-6xl mx-auto rounded-2xl overflow-hidden shadow-2xl'}`}
      style={{ background: 'linear-gradient(180deg, #0f172a 0%, #1e293b 100%)', minHeight: fullscreen ? '100vh' : 560 }}
    >
      {/* ── Top bar ── */}
      <div className="flex items-center gap-3 px-5 py-3 flex-shrink-0" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        {/* Slide counter + progress */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 bg-white/5 rounded-lg px-3 py-1.5">
            <span className="text-white font-bold text-sm tabular-nums">
              {loading ? '—' : current + 1}
            </span>
            <span className="text-white/30 text-sm">/</span>
            <span className="text-white/50 text-sm tabular-nums">
              {loading ? '—' : images.length}
            </span>
          </div>
        </div>

        {/* Slide title + type badge */}
        <div className="flex-1 flex items-center gap-2 min-w-0">
          {meta && (
            <>
              <TypeBadge type={meta.type} />
              <span className="text-white/80 text-sm font-medium truncate">{meta.title}</span>
            </>
          )}
          {loading && (
            <span className="text-white/30 text-sm italic">Rendering slides…</span>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {/* Auto-play */}
          {!loading && images.length > 1 && (
            <button
              onClick={() => setAutoPlay((v) => !v)}
              title={autoPlay ? 'Pause (P)' : 'Auto-play (P)'}
              className={`p-1.5 rounded-lg transition-all text-sm ${autoPlay ? 'bg-blue-500/20 text-blue-400' : 'text-white/40 hover:text-white hover:bg-white/10'}`}
            >
              {autoPlay ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
          )}

          {/* Keyboard shortcuts */}
          <button
            onClick={() => setShowKeys((v) => !v)}
            title="Keyboard shortcuts (?)"
            className={`p-1.5 rounded-lg transition-all ${showKeys ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white hover:bg-white/10'}`}
          >
            <Keyboard className="w-4 h-4" />
          </button>

          {/* Download */}
          {!loading && (
            <button
              onClick={handleDownload}
              disabled={downloading}
              title="Download PPTX"
              className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-all disabled:opacity-30"
            >
              {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            </button>
          )}

          {/* Fullscreen */}
          <button
            onClick={() => setFullscreen((v) => !v)}
            title="Fullscreen (F)"
            className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-all"
          >
            {fullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>

          {/* Prev / Next */}
          <div className="flex items-center gap-0.5 ml-1">
            <button
              onClick={prev}
              disabled={current === 0 || loading}
              className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/10 disabled:opacity-20 transition-all"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={next}
              disabled={current >= images.length - 1 || loading}
              className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/10 disabled:opacity-20 transition-all"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Progress bar */}
      {!loading && images.length > 0 && (
        <div className="h-0.5 flex-shrink-0" style={{ background: 'rgba(255,255,255,0.05)' }}>
          <div
            className="h-full transition-all duration-300"
            style={{ width: `${progress}%`, background: 'linear-gradient(90deg, #3b82f6, #8b5cf6)' }}
          />
        </div>
      )}

      {/* ── Main area ── */}
      <div className="flex flex-1 overflow-hidden flex-col">
        {/* Slide panel */}
        <div className="flex-1 flex flex-col items-center justify-center p-6 relative overflow-hidden">
          {/* Loading state */}
          {loading && (
            <div className="flex flex-col items-center gap-4">
              <div className="relative">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center" style={{ background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)' }}>
                  <Loader2 className="w-7 h-7 text-blue-400 animate-spin" />
                </div>
              </div>
              <div className="text-center">
                <p className="text-white/80 font-semibold text-base">Rendering presentation…</p>
                <p className="text-white/40 text-sm mt-1">Converting to high-quality images</p>
                <p className="text-white/25 text-xs mt-0.5">This takes 10–20 seconds</p>
              </div>
              {/* Animated dots */}
              <div className="flex gap-1.5 mt-2">
                {[0,1,2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 rounded-full bg-blue-400/60 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="flex flex-col items-center gap-4 max-w-sm text-center">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)' }}>
                <AlertCircle className="w-6 h-6 text-red-400" />
              </div>
              <div>
                <p className="text-white/80 font-semibold">Preview unavailable</p>
                <p className="text-white/40 text-sm mt-1">{error}</p>
              </div>
              <button
                onClick={() => { setError(null); setLoading(true); apiClient.post(`/presentations/${presentationId}/export/pptx/preview-images`).then(r => { setImages(r.data.images||[]); setSlideMeta(r.data.slide_meta||[]); setLoading(false) }).catch(e => { setError(e?.response?.data?.detail||e?.message||'Failed'); setLoading(false) }) }}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white/70 hover:text-white transition-colors"
                style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)' }}
              >
                <RefreshCw className="w-3.5 h-3.5" /> Retry
              </button>
            </div>
          )}

          {/* Slide image */}
          {!loading && !error && images[current] && (
            <div className="relative w-full flex items-center justify-center">
              {/* Glow effect behind slide */}
              <div
                className="absolute inset-0 rounded-xl opacity-20 blur-3xl"
                style={{ background: 'radial-gradient(ellipse at center, #3b82f6 0%, transparent 70%)' }}
              />
              <img
                key={current}
                src={images[current]}
                alt={meta?.title || `Slide ${current + 1}`}
                onLoad={() => setImgLoaded(true)}
                className={`relative rounded-xl shadow-2xl transition-opacity duration-300 ${imgLoaded ? 'opacity-100' : 'opacity-0'}`}
                style={{
                  maxWidth: '100%',
                  maxHeight: fullscreen ? 'calc(100vh - 220px)' : 460,
                  objectFit: 'contain',
                  boxShadow: '0 25px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.06)',
                }}
              />
              {!imgLoaded && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <Loader2 className="w-5 h-5 text-white/30 animate-spin" />
                </div>
              )}

              {/* Click zones for navigation */}
              <button
                onClick={prev}
                disabled={current === 0}
                className="absolute left-0 top-0 bottom-0 w-16 flex items-center justify-start pl-2 opacity-0 hover:opacity-100 transition-opacity disabled:hidden"
                aria-label="Previous slide"
              >
                <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)' }}>
                  <ChevronLeft className="w-4 h-4 text-white" />
                </div>
              </button>
              <button
                onClick={next}
                disabled={current >= images.length - 1}
                className="absolute right-0 top-0 bottom-0 w-16 flex items-center justify-end pr-2 opacity-0 hover:opacity-100 transition-opacity disabled:hidden"
                aria-label="Next slide"
              >
                <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)' }}>
                  <ChevronRight className="w-4 h-4 text-white" />
                </div>
              </button>
            </div>
          )}
        </div>

        {/* ── Bottom filmstrip — thumbnail strip ── */}
        {!fullscreen && !loading && !error && images.length > 0 && (
          <div
            className="flex-shrink-0 flex flex-col overflow-hidden"
            style={{ borderTop: '1px solid rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.25)' }}
          >
            <div className="flex items-center gap-3 overflow-x-auto px-4 py-3 scrollbar-thin">
              {images.map((img, i) => {
                const m = slideMeta[i]
                const cfg = TYPE_CONFIG[m?.type || 'content'] || TYPE_CONFIG.content
                const isActive = i === current
                return (
                  <button
                    key={i}
                    onClick={() => goTo(i)}
                    title={m?.title || `Slide ${i + 1}`}
                    className="flex-shrink-0 flex flex-col items-center gap-1 group transition-all"
                  >
                    {/* Thumbnail */}
                    <div
                      className="relative rounded-lg overflow-hidden transition-all"
                      style={{
                        width: 96,
                        height: 54,
                        outline: isActive ? `2px solid ${cfg.color}` : '1px solid rgba(255,255,255,0.08)',
                        opacity: isActive ? 1 : 0.55,
                        transform: isActive ? 'scale(1.05)' : 'scale(1)',
                      }}
                    >
                      <img src={img} alt={m?.title || `Slide ${i + 1}`} className="w-full h-full object-cover" />
                      {/* Slide number */}
                      <div
                        className="absolute bottom-0.5 left-0.5 w-4 h-4 rounded flex items-center justify-center text-white font-bold"
                        style={{ background: 'rgba(0,0,0,0.65)', fontSize: 9 }}
                      >
                        {i + 1}
                      </div>
                      {/* Type icon */}
                      <div className="absolute top-0.5 right-0.5">
                        <SlideTypeIcon type={m?.type || 'content'} size={9} />
                      </div>
                      {/* Active indicator bar */}
                      {isActive && (
                        <div
                          className="absolute bottom-0 left-0 right-0 h-0.5"
                          style={{ background: cfg.color }}
                        />
                      )}
                    </div>
                    {/* Slide title below thumbnail */}
                    <p
                      className="text-center leading-tight max-w-[96px] truncate"
                      style={{ fontSize: 9, color: isActive ? cfg.color : 'rgba(255,255,255,0.3)' }}
                    >
                      {m?.title || `Slide ${i + 1}`}
                    </p>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── Keyboard shortcuts overlay ── */}
      {showKeys && (
        <div
          className="absolute inset-0 flex items-center justify-center z-10"
          style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)' }}
          onClick={() => setShowKeys(false)}
        >
          <div className="rounded-2xl p-6 max-w-xs w-full" style={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)' }}>
            <h3 className="text-white font-semibold mb-4 text-center">Keyboard Shortcuts</h3>
            <div className="space-y-2">
              {[
                ['← / →', 'Navigate slides'],
                ['F', 'Toggle fullscreen'],
                ['P', 'Toggle auto-play'],
                ['?', 'Show shortcuts'],
                ['ESC', 'Close'],
              ].map(([key, desc]) => (
                <div key={key} className="flex items-center justify-between">
                  <kbd className="px-2 py-0.5 rounded text-xs font-mono text-white/80" style={{ background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.15)' }}>{key}</kbd>
                  <span className="text-white/50 text-sm">{desc}</span>
                </div>
              ))}
            </div>
            <p className="text-white/25 text-xs text-center mt-4">Click anywhere to close</p>
          </div>
        </div>
      )}

      {/* ── Bottom bar (fullscreen only) ── */}
      {fullscreen && !loading && images.length > 0 && (
        <div className="flex items-center justify-between px-6 py-2 flex-shrink-0" style={{ background: 'rgba(0,0,0,0.6)', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="flex items-center gap-3 overflow-x-auto">
            {images.map((img, i) => (
              <button
                key={i}
                onClick={() => goTo(i)}
                className={`flex-shrink-0 rounded overflow-hidden transition-all ${i === current ? 'ring-2 ring-blue-400 opacity-100' : 'opacity-40 hover:opacity-70'}`}
                style={{ width: 64, height: 36 }}
              >
                <img src={img} alt="" className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
          <p className="text-white/30 text-xs ml-4 flex-shrink-0">← → · F · ESC · ?</p>
        </div>
      )}
    </div>
  )

  if (inline) {
    return (
      <div className="w-full max-w-6xl mx-auto px-4 relative">
        {content}
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" style={{ backdropFilter: 'blur(4px)' }}>
      <div className="w-full max-w-6xl relative">
        {content}
      </div>
    </div>
  )
}

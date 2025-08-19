'use client'

import { useEffect, useState } from 'react'
import { AuthGuard } from '@/components/AuthGuard'
import { Navigation } from '@/components/Navigation'

export default function SearchPage() {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState<any[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [limit, setLimit] = useState(10)
    const [semanticRatio, setSemanticRatio] = useState(0)
    const [threshold, setThreshold] = useState(0)

    useEffect(() => {
        if (!query.trim()) {
            setResults([])
            setError(null)
            return
        }

        const controller = new AbortController()
        const timeout = setTimeout(async () => {
            setIsLoading(true)
            setError(null)
            try {
                const params = new URLSearchParams({
                    query,
                    limit: String(limit),
                    semantic_ratio: String(semanticRatio),
                    threshold: String(threshold),
                })
                const res = await fetch(`/api/rag/search?${params.toString()}`, {
                    method: 'GET',
                    signal: controller.signal,
                })

                if (!res.ok) {
                    const data = await res.json().catch(() => null)
                    throw new Error(data?.error || `Ошибка (${res.status})`)
                }

                const data = await res.json()
                setResults(Array.isArray(data.products) ? data.products : [])
            } catch (e: any) {
                if (e.name !== 'AbortError') {
                    setError(e.message || 'Ошибка запроса')
                }
            } finally {
                setIsLoading(false)
            }
        }, 300)

        return () => {
            controller.abort()
            clearTimeout(timeout)
        }
    }, [query, limit, semanticRatio, threshold])

    return (
        <AuthGuard>
            <Navigation />
            <main className="min-h-screen max-w-5xl mx-auto p-4">
                <h1 className="text-2xl font-semibold mb-4">Поиск товаров</h1>
                <div className="mb-4">
                    <input
                        type="text"
                        placeholder="Введите запрос..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="w-full rounded-md border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                </div>

                <details className="mb-4">
                    <summary className="cursor-pointer text-sm text-indigo-600">Настройки</summary>
                    <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <label className="text-sm text-gray-700">
                            Лимит
                            <input
                                type="number"
                                min={1}
                                max={50}
                                value={limit}
                                onChange={(e) => setLimit(Math.min(50, Math.max(1, Number(e.target.value) || 10)))}
                                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2"
                            />
                        </label>
                        <label className="text-sm text-gray-700">
                            semantic_ratio ({semanticRatio})
                            <input
                                type="range"
                                min={0}
                                max={1}
                                step={0.1}
                                value={semanticRatio}
                                onChange={(e) => setSemanticRatio(Number(e.target.value))}
                                className="mt-1 w-full"
                            />
                        </label>
                        <label className="text-sm text-gray-700">
                            threshold ({threshold})
                            <input
                                type="range"
                                min={0}
                                max={1}
                                step={0.05}
                                value={threshold}
                                onChange={(e) => setThreshold(Number(e.target.value))}
                                className="mt-1 w-full"
                            />
                        </label>
                    </div>
                    <p className="mt-2 text-xs text-gray-500">Для коротких артикулов (например, GX12M) рекомендую semantic_ratio = 0 и threshold = 0.</p>
                </details>

                {isLoading && <div className="text-sm text-gray-500">Загрузка...</div>}
                {error && <div className="text-sm text-red-600">{error}</div>}

                <div className="grid grid-cols-1 gap-3">
                    {results.map((p) => (
                        <div key={`${p.id}-${p.ext_id ?? ''}`} className="rounded-lg border p-4 bg-white">
                            <div className="flex items-center justify-between">
                                <h2 className="text-lg font-medium">{p.name ?? p.complex_name}</h2>
                                {typeof p.relevance === 'number' && (
                                    <span className="text-xs text-gray-500">rel: {p.relevance.toFixed(2)}</span>
                                )}
                            </div>
                            {p.brand && <div className="text-sm text-gray-600">Бренд: {p.brand}</div>}
                            {p.group && <div className="text-sm text-gray-600">Группа: {p.group}</div>}
                            {p.description && <div className="text-sm text-gray-700 mt-2 line-clamp-3">{p.description}</div>}
                            {p.tech_params && (
                                <details className="mt-2">
                                    <summary className="cursor-pointer text-sm text-indigo-600">Параметры</summary>
                                    <pre className="mt-1 whitespace-pre-wrap break-words text-xs bg-gray-50 p-2 rounded">
                                        {JSON.stringify(p.tech_params, null, 2)}
                                    </pre>
                                </details>
                            )}
                        </div>
                    ))}

                    {!isLoading && !error && query.trim() && results.length === 0 && (
                        <div className="text-sm text-gray-500">Ничего не найдено</div>
                    )}
                </div>
            </main>
        </AuthGuard>
    )
}



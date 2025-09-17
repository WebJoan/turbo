'use client';

import { useCallback, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { ProductSelector } from '@/features/rfqs/components/rfq-product-selector';
import { CompetitorProductSelector } from './competitor-product-selector';
import { createCompetitorProductMatchClient, updateCompetitorProductClient } from '@/lib/stock-client';
import { CompetitorProductMatch } from '@/types/stock';

type MatchType = CompetitorProductMatch['match_type'];

const MATCH_TYPES: { value: MatchType; label: string }[] = [
    { value: 'exact', label: 'Точный' },
    { value: 'equivalent', label: 'Эквивалент' },
    { value: 'analog', label: 'Аналог' },
    { value: 'similar', label: 'Похожий' },
];

export function CompetitorMappingView() {
    const [ourProductId, setOurProductId] = useState<number | undefined>(undefined);
    const [competitorProductId, setCompetitorProductId] = useState<number | undefined>(undefined);
    const [matchType, setMatchType] = useState<MatchType>('similar');
    const [confidence, setConfidence] = useState<number>(0.8);
    const [notes, setNotes] = useState<string>('');
    const [saving, setSaving] = useState(false);

    const canSave = useMemo(() => Boolean(ourProductId && competitorProductId), [ourProductId, competitorProductId]);

    const handleCreateMatch = useCallback(async () => {
        if (!ourProductId || !competitorProductId) return;
        setSaving(true);
        try {
            await createCompetitorProductMatchClient({
                competitor_product: competitorProductId as unknown as any, // API ожидает id внутри сериализатора read-only? у нас serializer read_only; backend принимает body с numeric id через ModelViewSet
                product: ourProductId,
                match_type: matchType,
                confidence,
                notes: notes || undefined,
            } as any);
            toast.success('Сопоставление создано');
        } catch (e: any) {
            toast.error('Не удалось создать сопоставление');
        } finally {
            setSaving(false);
        }
    }, [ourProductId, competitorProductId, matchType, confidence, notes]);

    const handleMapDirectly = useCallback(async () => {
        if (!ourProductId || !competitorProductId) return;
        setSaving(true);
        try {
            await updateCompetitorProductClient(competitorProductId, { mapped_product: ourProductId } as any);
            toast.success('Товар конкурента привязан к нашему');
        } catch (e: any) {
            toast.error('Не удалось привязать товар');
        } finally {
            setSaving(false);
        }
    }, [ourProductId, competitorProductId]);

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Сопоставление товара конкурента с нашим</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="space-y-2">
                            <Label>Наш товар</Label>
                            <ProductSelector value={ourProductId} onValueChange={setOurProductId} placeholder="Выберите наш товар..." />
                        </div>
                        <div className="space-y-2">
                            <Label>Товар конкурента</Label>
                            <CompetitorProductSelector value={competitorProductId} onValueChange={(v) => setCompetitorProductId(v)} placeholder="Выберите товар конкурента..." />
                        </div>
                    </div>

                    <Separator />

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                        <div className="space-y-2">
                            <Label>Тип соответствия</Label>
                            <div className="flex flex-wrap gap-2">
                                {MATCH_TYPES.map((t) => (
                                    <Button key={t.value} type="button" variant={matchType === t.value ? 'default' : 'outline'} size="sm" onClick={() => setMatchType(t.value)}>
                                        {t.label}
                                    </Button>
                                ))}
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label>Уверенность (0–1)</Label>
                            <Input type="number" min={0} max={1} step={0.05} value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} />
                        </div>
                        <div className="space-y-2 sm:col-span-2 lg:col-span-1">
                            <Label>Заметки</Label>
                            <Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Опционально" />
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <Button onClick={handleCreateMatch} disabled={!canSave || saving}>Создать сопоставление</Button>
                        <Button onClick={handleMapDirectly} variant="secondary" disabled={!canSave || saving}>Привязать напрямую (mapped_product)</Button>
                    </div>

                    {!canSave && (
                        <div className="text-sm text-muted-foreground">Выберите наш товар и товар конкурента для продолжения</div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}



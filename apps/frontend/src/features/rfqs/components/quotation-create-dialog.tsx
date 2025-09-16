"use client";

import React from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { fetchRFQItemLastPrices, createQuotationForRFQItem, uploadFilesForQuotationItem } from "@/lib/rfqs";
import type { RFQItemLastPrices, CreateQuotationInput } from "@/types/rfqs";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { ProductSelector } from "./rfq-product-selector";

interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    rfqItemId: number;
    onCreated?: () => void;
}

export function QuotationCreateDialog({ open, onOpenChange, rfqItemId, onCreated }: Props) {
    const [loading, setLoading] = React.useState(false);
    const [submitting, setSubmitting] = React.useState(false);
    const [lastPrices, setLastPrices] = React.useState<RFQItemLastPrices | null>(null);

    const [form, setForm] = React.useState<CreateQuotationInput>({
        unit_cost_price: "",
        cost_expense_percent: 10,
        cost_markup_percent: 20,
        quantity: undefined,
        delivery_time: "",
        notes: "",
    });
    const [useExistingProduct, setUseExistingProduct] = React.useState(true);
    const [selectedProductId, setSelectedProductId] = React.useState<number | undefined>(undefined);
    const [proposed, setProposed] = React.useState({ name: "", manufacturer: "", partnumber: "" });
    const fileInputRef = React.useRef<HTMLInputElement | null>(null);
    const [files, setFiles] = React.useState<File[]>([]);
    const [dragOver, setDragOver] = React.useState(false);

    React.useEffect(() => {
        if (!open) return;
        setLoading(true);
        fetchRFQItemLastPrices(rfqItemId)
            .then(setLastPrices)
            .catch(() => setLastPrices(null))
            .finally(() => setLoading(false));
    }, [open, rfqItemId]);

    const handleTextChange = (key: keyof CreateQuotationInput) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        setForm((prev) => ({ ...prev, [key]: e.target.value }));
    };

    const handleNumberChange = (key: keyof CreateQuotationInput) => (e: React.ChangeEvent<HTMLInputElement>) => {
        const raw = e.target.value;
        setForm((prev) => ({ ...prev, [key]: raw === "" ? "" : Number(raw) }));
    };

    // Вычисления цены в реальном времени (повторяют формулу на бэке)
    const { expenseAmount, totalCost, markupAmount, unitPrice, totalPrice } = React.useMemo(() => {
        const unitCost = Number(form.unit_cost_price) || 0;
        const expensePercent = Number(form.cost_expense_percent) || 0;
        const markupPercent = Number(form.cost_markup_percent) || 0;
        const qty = Number(form.quantity) || 0;
        const expense = unitCost * (expensePercent / 100);
        const costWithExpense = unitCost + expense;
        const markup = costWithExpense * (markupPercent / 100);
        const uPrice = costWithExpense + markup;
        const tPrice = uPrice * (qty || 0);
        return {
            expenseAmount: expense,
            totalCost: costWithExpense,
            markupAmount: markup,
            unitPrice: uPrice,
            totalPrice: tPrice,
        };
    }, [form.unit_cost_price, form.cost_expense_percent, form.cost_markup_percent, form.quantity]);

    const handleSubmit = async () => {
        try {
            setSubmitting(true);
            if (!form.unit_cost_price || Number(form.unit_cost_price) <= 0) {
                toast.error("Укажите закупочную цену");
                return;
            }
            const payload: CreateQuotationInput & { product?: number } = { ...form } as any;
            if (useExistingProduct) {
                if (!selectedProductId) {
                    toast.error("Выберите товар из базы или переключитесь на 'Новый'");
                    return;
                }
                payload.product = selectedProductId;
                delete (payload as any).proposed_product_name;
                delete (payload as any).proposed_manufacturer;
                delete (payload as any).proposed_part_number;
            } else {
                (payload as any).proposed_product_name = proposed.name;
                (payload as any).proposed_manufacturer = proposed.manufacturer;
                (payload as any).proposed_part_number = proposed.partnumber;
            }

            const created = await createQuotationForRFQItem(rfqItemId, payload);
            try {
                if (files && files.length > 0) {
                    const quotationItemId = created?.items?.[0]?.id;
                    if (quotationItemId) {
                        await uploadFilesForQuotationItem(quotationItemId, files);
                    }
                }
            } catch (e) {
                toast.error("Файлы не удалось загрузить");
            }
            toast.success("Предложение создано");
            onOpenChange(false);
            onCreated?.();
        } catch (e) {
            toast.error("Не удалось создать предложение");
        } finally {
            setSubmitting(false);
            setFiles([]);
        }
    };

    const renderLastPrice = (title: string, entry: RFQItemLastPrices["last_price_any"]) => (
        <div className="text-sm">
            <div className="text-muted-foreground mb-1">{title}</div>
            {entry ? (
                <div className="font-mono">
                    {parseFloat(entry.price).toLocaleString("ru-RU", { minimumFractionDigits: 2 })} {entry.currency}
                    {entry.invoice_date ? ` · ${new Date(entry.invoice_date).toLocaleDateString("ru-RU")}` : ""}
                    {entry.invoice_number ? ` · ${entry.invoice_number}` : ""}
                </div>
            ) : (
                <div className="text-muted-foreground">нет данных</div>
            )}
        </div>
    );

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Дать предложение по позиции</DialogTitle>
                    <DialogDescription>Укажите ключевые параметры. Прошлые цены помогут сориентироваться.</DialogDescription>
                </DialogHeader>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-4">
                        <div className="flex items-center justify-between rounded-md border p-3">
                            <div className="text-sm">
                                <div className="font-medium">Товар из базы</div>
                                <div className="text-muted-foreground">Выберите товар или переключитесь на новый</div>
                            </div>
                            <Switch checked={useExistingProduct} onCheckedChange={setUseExistingProduct} />
                        </div>

                        {useExistingProduct ? (
                            <div className="grid gap-2">
                                <Label>Товар из базы</Label>
                                <ProductSelector value={selectedProductId} onValueChange={setSelectedProductId} />
                            </div>
                        ) : (
                            <div className="grid grid-cols-2 gap-3">
                                <div className="grid gap-2">
                                    <Label>Наименование</Label>
                                    <Input value={proposed.name} onChange={(e) => setProposed((p) => ({ ...p, name: e.target.value }))} />
                                </div>
                                <div className="grid gap-2">
                                    <Label>Производитель</Label>
                                    <Input value={proposed.manufacturer} onChange={(e) => setProposed((p) => ({ ...p, manufacturer: e.target.value }))} />
                                </div>
                                <div className="grid gap-2 col-span-2">
                                    <Label>Артикул</Label>
                                    <Input value={proposed.partnumber} onChange={(e) => setProposed((p) => ({ ...p, partnumber: e.target.value }))} />
                                </div>
                            </div>
                        )}

                        <div className="grid gap-2">
                            <Label>Закупочная цена *</Label>
                            <Input type="number" inputMode="decimal" step="0.0001" min="0" value={String(form.unit_cost_price)} onChange={handleNumberChange("unit_cost_price")} />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="grid gap-2">
                                <Label>% расходов</Label>
                                <Input type="number" inputMode="decimal" step="0.01" min="0" max="100" value={String(form.cost_expense_percent ?? "")} onChange={handleNumberChange("cost_expense_percent")} />
                            </div>
                            <div className="grid gap-2">
                                <Label>% наценки</Label>
                                <Input type="number" inputMode="decimal" step="0.01" min="0" max="100" value={String(form.cost_markup_percent ?? "")} onChange={handleNumberChange("cost_markup_percent")} />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="grid gap-2">
                                <Label>Кол-во</Label>
                                <Input type="number" inputMode="numeric" step="1" min="1" value={String(form.quantity ?? "")} onChange={handleNumberChange("quantity")} />
                            </div>
                            <div className="grid gap-2">
                                <Label>Срок поставки</Label>
                                <Input value={String(form.delivery_time ?? "")} onChange={handleTextChange("delivery_time")} />
                            </div>
                        </div>
                        <div className="grid gap-2">
                            <Label>Заметки</Label>
                            <Textarea value={String(form.notes ?? "")} onChange={handleTextChange("notes")} rows={3} />
                        </div>

                        {/* Вычисленные значения */}
                        <div className="grid grid-cols-2 gap-3">
                            <div className="grid gap-2">
                                <Label>Итоговая цена за ед.</Label>
                                <Input value={unitPrice > 0 ? unitPrice.toFixed(4) : ""} readOnly />
                            </div>
                            <div className="grid gap-2">
                                <Label>Общая цена</Label>
                                <Input value={totalPrice > 0 ? totalPrice.toFixed(2) : ""} readOnly />
                            </div>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <div className="text-sm font-medium">Прошлые цены</div>
                        <div className="rounded-md border p-3 space-y-3">
                            {loading ? (
                                <div className="text-sm text-muted-foreground">Загрузка...</div>
                            ) : (
                                <>
                                    {renderLastPrice("Для этой компании", lastPrices?.last_price_for_company || null)}
                                    {renderLastPrice("Для любых клиентов", lastPrices?.last_price_any || null)}
                                </>
                            )}
                        </div>
                        <div className="rounded-md border p-3 text-xs space-y-1">
                            <div className="text-muted-foreground">Расчёт:</div>
                            <div>Затраты: {expenseAmount.toFixed(4)}</div>
                            <div>Себестоимость с затратами: {totalCost.toFixed(4)}</div>
                            <div>Наценка: {markupAmount.toFixed(4)}</div>
                        </div>
                        <div className="text-xs text-muted-foreground">Итоговая цена вычисляется автоматически из закупочной цены, % расходов и % наценки.</div>

                        {/* Файлы к предложению */}
                        <div className="grid gap-2">
                            <Label>Файлы (необязательно)</Label>
                            <input
                                ref={fileInputRef}
                                type="file"
                                multiple
                                className="hidden"
                                onChange={(e) => {
                                    const list = e.target.files;
                                    if (!list) return;
                                    setFiles((prev) => [...prev, ...Array.from(list)]);
                                    e.currentTarget.value = "";
                                }}
                            />
                            <div
                                role="button"
                                tabIndex={0}
                                onClick={() => fileInputRef.current?.click()}
                                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
                                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                                onDragEnter={() => setDragOver(true)}
                                onDragLeave={() => setDragOver(false)}
                                onDrop={(e) => {
                                    e.preventDefault();
                                    setDragOver(false);
                                    const dtFiles = e.dataTransfer?.files;
                                    if (!dtFiles || dtFiles.length === 0) return;
                                    setFiles((prev) => [...prev, ...Array.from(dtFiles)]);
                                }}
                                className={`flex items-center gap-2 justify-center rounded-md border border-dashed p-3 text-xs cursor-pointer transition-colors w-full overflow-hidden ${dragOver ? 'bg-primary/10 border-primary' : 'hover:bg-muted/50'}`}
                            >
                                <span className="truncate min-w-0">Перетащите файлы или нажмите, чтобы выбрать</span>
                            </div>
                            {files.length > 0 && (
                                <div className="rounded-md border p-2 text-xs space-y-1 max-h-32 overflow-auto">
                                    {files.map((f, idx) => (
                                        <div key={`${f.name}-${idx}`} className="flex items-center justify-between gap-2">
                                            <div className="min-w-0 truncate">{f.name}</div>
                                            <Button variant="ghost" size="sm" onClick={() => setFiles((prev) => prev.filter((_, i) => i !== idx))}>Удалить</Button>
                                        </div>
                                    ))}
                                    <div className="flex justify-end">
                                        <Button variant="ghost" size="sm" onClick={() => setFiles([])}>Очистить</Button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>Отмена</Button>
                    <Button onClick={handleSubmit} disabled={submitting}>Сохранить</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

"use client";

import React, { useEffect, useState } from "react";
import { Accessibility, Armchair } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Input, Select, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { FormModal, StatusBadge, useToast } from "@/components/dashboard";
import {
  ActivityRecord,
  ActivitySlotRecord,
  DiningTableRecord,
  EventRecord,
  EventTicketTypeRecord,
  MenuItemRecord,
  MovieSummary,
  ScreenRecord,
  SeatRecord,
  SportsVenueRecord,
} from "./partnerTypes";

/* -------------------------------------------------------------------------- */
/* 1. RESTAURANT: Menu Dish Modal                                             */
/* -------------------------------------------------------------------------- */
export function MenuItemModal({
  isOpen,
  onClose,
  initialItem,
  onSaved,
}: {
  isOpen: boolean;
  onClose: () => void;
  initialItem?: MenuItemRecord | null;
  onSaved: () => Promise<void>;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    category: "Main Course",
    item_name: "",
    price: "350",
    description: "",
    is_veg: true,
    is_bestseller: false,
    is_available: true,
    image_url: "",
  });

  useEffect(() => {
    if (isOpen) {
      setError(null);
      if (initialItem) {
        setForm({
          category: initialItem.category || "Main Course",
          item_name: initialItem.item_name || "",
          price: String(initialItem.price ?? 0),
          description: initialItem.description || "",
          is_veg: Boolean(initialItem.is_veg),
          is_bestseller: Boolean(initialItem.is_bestseller),
          is_available: Boolean(initialItem.is_available),
          image_url: initialItem.image_url || "",
        });
      } else {
        setForm({
          category: "Main Course",
          item_name: "",
          price: "350",
          description: "",
          is_veg: true,
          is_bestseller: false,
          is_available: true,
          image_url: "",
        });
      }
    }
  }, [isOpen, initialItem]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const numericPrice = Number(form.price);
    if (!Number.isFinite(numericPrice) || numericPrice <= 0) {
      setError("Price must be greater than ₹0.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = {
        category: form.category.trim(),
        item_name: form.item_name.trim(),
        price: numericPrice,
        description: form.description.trim() || null,
        is_veg: form.is_veg,
        is_bestseller: form.is_bestseller,
        is_available: form.is_available,
        image_url: form.image_url.trim() || null,
      };
      if (initialItem) {
        await apiRequest(`/partners/restaurant/menus/${initialItem.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast.success("Dish updated", payload.item_name);
      } else {
        await apiRequest("/partners/restaurant/menus", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.success("Dish added to menu", payload.item_name);
      }
      await onSaved();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to save dish.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <FormModal
      isOpen={isOpen}
      onClose={onClose}
      onSubmit={handleSubmit}
      title={initialItem ? "Edit Menu Dish" : "Add New Dish"}
      description="Changes go live immediately on the public dining storefront."
      submitLabel={initialItem ? "Update Dish" : "Add Dish"}
      loading={loading}
      error={error}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Category"
          required
          placeholder="Starters, Main Course, Desserts..."
          value={form.category}
          onChange={(e) => setForm({ ...form, category: e.target.value })}
        />
        <Input
          label="Price (₹)"
          type="number"
          step="1"
          min="1"
          required
          value={form.price}
          onChange={(e) => setForm({ ...form, price: e.target.value })}
        />
      </div>

      <Input
        label="Dish Name"
        required
        placeholder="e.g. Hyderabadi Dum Biryani"
        value={form.item_name}
        onChange={(e) => setForm({ ...form, item_name: e.target.value })}
      />

      <Textarea
        label="Description"
        placeholder="Ingredients, portion size, spice notes..."
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
      />

      <Input
        label="Dish Image URL (Optional)"
        placeholder="https://..."
        value={form.image_url}
        onChange={(e) => setForm({ ...form, image_url: e.target.value })}
      />

      <div className="flex flex-wrap items-center gap-5 pt-1 text-xs text-primary">
        <label className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_veg}
            onChange={(e) => setForm({ ...form, is_veg: e.target.checked })}
            className="w-4 h-4 accent-emerald-500 rounded"
          />
          <span>Vegetarian</span>
        </label>
        <label className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_bestseller}
            onChange={(e) =>
              setForm({ ...form, is_bestseller: e.target.checked })
            }
            className="w-4 h-4 accent-gold-500 rounded"
          />
          <span>Chef Bestseller</span>
        </label>
        <label className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_available}
            onChange={(e) =>
              setForm({ ...form, is_available: e.target.checked })
            }
            className="w-4 h-4 accent-console-500 rounded"
          />
          <span>In Stock / Available</span>
        </label>
      </div>
    </FormModal>
  );
}

/* -------------------------------------------------------------------------- */
/* 2. RESTAURANT: Dining Table Modal                                          */
/* -------------------------------------------------------------------------- */
export function DiningTableModal({
  isOpen,
  onClose,
  initialTable,
  onSaved,
}: {
  isOpen: boolean;
  onClose: () => void;
  initialTable?: DiningTableRecord | null;
  onSaved: () => Promise<void>;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    table_number: "",
    capacity: "4",
    zone: "Indoor",
    is_active: true,
  });

  useEffect(() => {
    if (isOpen) {
      setError(null);
      if (initialTable) {
        setForm({
          table_number: initialTable.table_number,
          capacity: String(initialTable.capacity),
          zone: initialTable.zone || "Indoor",
          is_active: Boolean(initialTable.is_active),
        });
      } else {
        setForm({
          table_number: "",
          capacity: "4",
          zone: "Indoor",
          is_active: true,
        });
      }
    }
  }, [isOpen, initialTable]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cap = Number(form.capacity);
    if (!Number.isFinite(cap) || cap <= 0) {
      setError("Capacity must be at least 1 guest.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = {
        table_number: form.table_number.trim(),
        capacity: cap,
        zone: form.zone,
        is_active: form.is_active,
      };
      if (initialTable) {
        await apiRequest(`/partners/restaurant/tables/${initialTable.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast.success("Table updated", `Table ${payload.table_number}`);
      } else {
        await apiRequest("/partners/restaurant/tables", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.success("Dining table created", `Table ${payload.table_number}`);
      }
      await onSaved();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to save table.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <FormModal
      isOpen={isOpen}
      onClose={onClose}
      onSubmit={handleSubmit}
      title={initialTable ? "Edit Dining Table" : "Add Dining Table"}
      submitLabel={initialTable ? "Save Table" : "Create Table"}
      loading={loading}
      error={error}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Table Number / Label"
          required
          placeholder="e.g. T-12, Booth-4"
          value={form.table_number}
          onChange={(e) => setForm({ ...form, table_number: e.target.value })}
        />
        <Input
          label="Guest Capacity"
          type="number"
          min="1"
          max="30"
          required
          value={form.capacity}
          onChange={(e) => setForm({ ...form, capacity: e.target.value })}
        />
      </div>

      <Select
        label="Floor Zone"
        value={form.zone}
        onChange={(e) => setForm({ ...form, zone: e.target.value })}
      >
        <option value="Indoor">Indoor Dining</option>
        <option value="Outdoor">Outdoor / Patio</option>
        <option value="Rooftop">Rooftop Terrace</option>
        <option value="VIP Lounge">Private / VIP Lounge</option>
      </Select>

      <label className="inline-flex items-center gap-2 text-xs text-primary cursor-pointer">
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
          className="w-4 h-4 accent-console-500 rounded"
        />
        <span>Table active for online reservations</span>
      </label>
    </FormModal>
  );
}

/* -------------------------------------------------------------------------- */
/* 3. CINEMA: Add Screen Modal                                                */
/* -------------------------------------------------------------------------- */
export function CinemaScreenModal({
  isOpen,
  onClose,
  onSaved,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    screen_type: "2D",
    rows: "6",
    seats_per_row: "10",
    default_price: "280",
  });

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setForm({
        name: "",
        screen_type: "2D",
        rows: "6",
        seats_per_row: "10",
        default_price: "280",
      });
    }
  }, [isOpen]);

  const rowsNum = Math.min(15, Math.max(1, Number(form.rows) || 1));
  const seatsNum = Math.min(30, Math.max(1, Number(form.seats_per_row) || 1));
  const calculatedSeats = rowsNum * seatsNum;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiRequest("/partners/cinema/screens", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.trim(),
          screen_type: form.screen_type,
          rows: rowsNum,
          seats_per_row: seatsNum,
          total_seats: calculatedSeats,
          default_price: Number(form.default_price) || 250,
        }),
      });
      toast.success(
        "Auditorium screen created",
        `${form.name} provisioned with ${calculatedSeats} auto-mapped seats.`
      );
      await onSaved();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to create screen.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <FormModal
      isOpen={isOpen}
      onClose={onClose}
      onSubmit={handleSubmit}
      title="Create Cinema Screen"
      description="Auto-generates Recliner, Premium, and Classic rows mapped for customer seat selection."
      submitLabel="Create Screen"
      loading={loading}
      error={error}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Screen Name"
          required
          placeholder="e.g. Audi 4 — Laser IMAX"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <Select
          label="Projection Format"
          value={form.screen_type}
          onChange={(e) => setForm({ ...form, screen_type: e.target.value })}
        >
          <option value="2D">2D Standard</option>
          <option value="3D">3D Dolby Atmos</option>
          <option value="IMAX 3D">IMAX 3D</option>
          <option value="4DX">4DX Motion</option>
        </Select>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Input
          label="Rows (Max 15)"
          type="number"
          min="1"
          max="15"
          required
          value={form.rows}
          onChange={(e) => setForm({ ...form, rows: e.target.value })}
        />
        <Input
          label="Seats Per Row"
          type="number"
          min="1"
          max="30"
          required
          value={form.seats_per_row}
          onChange={(e) => setForm({ ...form, seats_per_row: e.target.value })}
        />
        <Input
          label="Base Seat Price (₹)"
          type="number"
          min="50"
          required
          value={form.default_price}
          onChange={(e) => setForm({ ...form, default_price: e.target.value })}
        />
      </div>

      <div className="rounded-xl bg-surface-2 border border-subtle p-3.5 text-xs text-secondary flex items-center justify-between">
        <span>Auto-generated seat capacity:</span>
        <strong className="font-mono text-console-300">
          {calculatedSeats} seats ({rowsNum} × {seatsNum})
        </strong>
      </div>
    </FormModal>
  );
}

/* -------------------------------------------------------------------------- */
/* 4. CINEMA: Interactive Seat Map Tier / Price Editor Modal                  */
/* -------------------------------------------------------------------------- */
export function CinemaSeatMapModal({
  isOpen,
  onClose,
  screen,
}: {
  isOpen: boolean;
  onClose: () => void;
  screen: ScreenRecord | null;
}) {
  const toast = useToast();
  const [seats, setSeats] = useState<SeatRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedSeat, setSelectedSeat] = useState<SeatRecord | null>(null);
  const [savingSeat, setSavingSeat] = useState(false);
  const [seatForm, setSeatForm] = useState({
    tier: "CLASSIC",
    base_price: "250",
    is_accessible: false,
  });

  useEffect(() => {
    if (!isOpen || !screen) return;
    setSelectedSeat(null);
    setLoading(true);
    apiRequest<SeatRecord[]>(`/partners/cinema/screens/${screen.id}/seats`)
      .then((res) => setSeats(res || []))
      .catch((err: any) =>
        toast.error("Unable to load seat map", err.message || "")
      )
      .finally(() => setLoading(false));
  }, [isOpen, screen, toast]);

  const handleSelectSeat = (seat: SeatRecord) => {
    setSelectedSeat(seat);
    setSeatForm({
      tier: seat.tier,
      base_price: String(seat.base_price),
      is_accessible: seat.is_accessible,
    });
  };

  const handleUpdateSeat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!screen || !selectedSeat) return;
    setSavingSeat(true);
    try {
      const updated = await apiRequest<SeatRecord>(
        `/partners/cinema/screens/${screen.id}/seats/${selectedSeat.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            tier: seatForm.tier,
            base_price: Number(seatForm.base_price) || 200,
            is_accessible: seatForm.is_accessible,
          }),
        }
      );
      setSeats((prev) =>
        prev.map((s) => (s.id === updated.id ? updated : s))
      );
      setSelectedSeat(updated);
      toast.success(
        "Seat updated",
        `${updated.row_code}${updated.seat_number} set to ${updated.tier} (₹${updated.base_price})`
      );
    } catch (err: any) {
      toast.error("Failed to update seat", err.message || "");
    } finally {
      setSavingSeat(false);
    }
  };

  const rows = React.useMemo(() => {
    const grouped: Record<string, SeatRecord[]> = {};
    for (const seat of seats) {
      grouped[seat.row_code] = grouped[seat.row_code] || [];
      grouped[seat.row_code].push(seat);
    }
    return Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b));
  }, [seats]);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="xl"
      title={screen ? `${screen.name} — Seat Tier & Pricing Map` : "Seat Map"}
      description="Select any seat in the auditorium grid to adjust its tier, price, or wheelchair accessibility."
    >
      {loading ? (
        <div className="py-12 text-center text-xs text-muted">
          Loading auditorium seat layout...
        </div>
      ) : (
        <div className="space-y-5">
          <div className="flex items-center justify-between flex-wrap gap-2 text-[11px] text-secondary">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="inline-flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-gold-500/40 border border-gold-400" />
                <span>Recliner</span>
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-console-500/40 border border-console-400" />
                <span>Premium</span>
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-surface-3 border border-strong" />
                <span>Classic</span>
              </span>
            </div>
            <span className="font-mono text-muted">
              {seats.length} total mapped seats
            </span>
          </div>

          <div className="p-4 rounded-2xl bg-surface-2/60 border border-subtle overflow-x-auto space-y-2">
            <div className="text-center text-[10px] font-bold tracking-[0.25em] uppercase text-muted pb-2 border-b border-subtle mb-3">
              Projection Screen This Side
            </div>

            {rows.map(([rowCode, rowSeats]) => (
              <div key={rowCode} className="flex items-center gap-2 min-w-max">
                <span className="w-6 text-xs font-mono font-bold text-muted">
                  {rowCode}
                </span>
                <div className="flex items-center gap-1.5">
                  {rowSeats.map((s) => {
                    const isSelected = selectedSeat?.id === s.id;
                    const tone =
                      s.tier === "RECLINER"
                        ? "bg-gold-500/20 border-gold-500/50 text-gold-300"
                        : s.tier === "PREMIUM"
                        ? "bg-console-500/20 border-console-500/50 text-console-200"
                        : "bg-surface border-strong text-secondary";
                    return (
                      <button
                        key={s.id}
                        type="button"
                        onClick={() => handleSelectSeat(s)}
                        title={`Seat ${s.row_code}${s.seat_number} · ${s.tier} · ₹${s.base_price}`}
                        className={`w-8 h-8 rounded-lg border text-[10px] font-mono font-bold flex items-center justify-center transition-all ${tone} ${
                          isSelected
                            ? "ring-2 ring-brand-500 scale-105"
                            : "hover:border-primary"
                        }`}
                      >
                        {s.is_accessible ? (
                          <Accessibility className="w-3.5 h-3.5" />
                        ) : (
                          s.seat_number
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {selectedSeat ? (
            <form
              onSubmit={handleUpdateSeat}
              className="rounded-xl bg-surface-2 border border-strong p-4 space-y-3"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs font-bold text-primary">
                  <Armchair className="w-4 h-4 text-console-400" />
                  <span>
                    Editing Seat {selectedSeat.row_code}
                    {selectedSeat.seat_number}
                  </span>
                  <StatusBadge status={selectedSeat.tier} dot={false} />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
                <Select
                  label="Seat Tier"
                  value={seatForm.tier}
                  onChange={(e) =>
                    setSeatForm({ ...seatForm, tier: e.target.value })
                  }
                >
                  <option value="RECLINER">RECLINER</option>
                  <option value="PREMIUM">PREMIUM</option>
                  <option value="CLASSIC">CLASSIC</option>
                </Select>
                <Input
                  label="Base Price (₹)"
                  type="number"
                  min="50"
                  value={seatForm.base_price}
                  onChange={(e) =>
                    setSeatForm({ ...seatForm, base_price: e.target.value })
                  }
                />
                <div className="flex items-center justify-between gap-2 pb-1">
                  <label className="inline-flex items-center gap-2 text-xs text-primary cursor-pointer">
                    <input
                      type="checkbox"
                      checked={seatForm.is_accessible}
                      onChange={(e) =>
                        setSeatForm({
                          ...seatForm,
                          is_accessible: e.target.checked,
                        })
                      }
                      className="w-4 h-4 accent-console-500 rounded"
                    />
                    <span>Accessible</span>
                  </label>
                  <Button
                    type="submit"
                    variant="console"
                    size="sm"
                    isLoading={savingSeat}
                  >
                    Save Seat
                  </Button>
                </div>
              </div>
            </form>
          ) : (
            <div className="text-xs text-muted text-center">
              Click any seat box above to inspect or customize its tier &amp; base fare.
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

/* -------------------------------------------------------------------------- */
/* 5. CINEMA: Schedule Show Modal                                             */
/* -------------------------------------------------------------------------- */
export function ScheduleShowModal({
  isOpen,
  onClose,
  screens,
  movies,
  onSaved,
}: {
  isOpen: boolean;
  onClose: () => void;
  screens: ScreenRecord[];
  movies: MovieSummary[];
  onSaved: () => Promise<void>;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    movie_id: "",
    screen_id: "",
    show_date: new Date().toISOString().split("T")[0],
    start_time: "18:30",
    end_time: "21:15",
    price_multiplier: "1.0",
  });

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setForm({
        movie_id: movies[0] ? String(movies[0].id) : "",
        screen_id: screens[0] ? String(screens[0].id) : "",
        show_date: new Date().toISOString().split("T")[0],
        start_time: "18:30",
        end_time: "21:15",
        price_multiplier: "1.0",
      });
    }
  }, [isOpen, movies, screens]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.movie_id || !form.screen_id) {
      setError("Please select both a movie and an auditorium screen.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiRequest("/partners/cinema/shows", {
        method: "POST",
        body: JSON.stringify({
          movie_id: Number(form.movie_id),
          screen_id: Number(form.screen_id),
          show_date: form.show_date,
          start_time: form.start_time,
          end_time: form.end_time,
          price_multiplier: Number(form.price_multiplier) || 1.0,
        }),
      });
      toast.success("Movie showtime scheduled");
      await onSaved();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to schedule showtime.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <FormModal
      isOpen={isOpen}
      onClose={onClose}
      onSubmit={handleSubmit}
      title="Schedule Movie Showtime"
      submitLabel="Publish Showtime"
      loading={loading}
      error={error}
    >
      <Select
        label="Movie Title"
        value={form.movie_id}
        onChange={(e) => setForm({ ...form, movie_id: e.target.value })}
      >
        {movies.map((m) => (
          <option key={m.id} value={m.id}>
            {m.title} {m.language ? `(${m.language})` : ""}
          </option>
        ))}
      </Select>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Select
          label="Auditorium Screen"
          value={form.screen_id}
          onChange={(e) => setForm({ ...form, screen_id: e.target.value })}
        >
          {screens.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.screen_type})
            </option>
          ))}
        </Select>
        <Input
          label="Price Multiplier (1.0x Standard)"
          type="number"
          step="0.1"
          min="0.5"
          max="4"
          value={form.price_multiplier}
          onChange={(e) =>
            setForm({ ...form, price_multiplier: e.target.value })
          }
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Input
          label="Show Date"
          type="date"
          required
          value={form.show_date}
          onChange={(e) => setForm({ ...form, show_date: e.target.value })}
        />
        <Input
          label="Start Time"
          type="time"
          required
          value={form.start_time}
          onChange={(e) => setForm({ ...form, start_time: e.target.value })}
        />
        <Input
          label="End Time"
          type="time"
          required
          value={form.end_time}
          onChange={(e) => setForm({ ...form, end_time: e.target.value })}
        />
      </div>
    </FormModal>
  );
}

/* -------------------------------------------------------------------------- */
/* 6. EVENT: Create / Edit Event Modal                                        */
/* -------------------------------------------------------------------------- */
export function EventFormModal({
  isOpen,
  onClose,
  initialEvent,
  onSaved,
}: {
  isOpen: boolean;
  onClose: () => void;
  initialEvent?: EventRecord | null;
  onSaved: () => Promise<void>;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    category: "CONCERT",
    venue_name: "",
    venue_address: "",
    start_datetime: "",
    end_datetime: "",
    artist_names: "",
    banner_url: "",
    description: "",
    is_featured: false,
    is_active: true,
  });

  useEffect(() => {
    if (isOpen) {
      setError(null);
      if (initialEvent) {
        setForm({
          title: initialEvent.title || "",
          category: initialEvent.category || "CONCERT",
          venue_name: initialEvent.venue_name || "",
          venue_address: initialEvent.venue_address || "",
          start_datetime: initialEvent.start_datetime.slice(0, 16),
          end_datetime: initialEvent.end_datetime.slice(0, 16),
          artist_names: initialEvent.artist_names || "",
          banner_url: initialEvent.banner_url || "",
          description: initialEvent.description || "",
          is_featured: Boolean(initialEvent.is_featured),
          is_active: Boolean(initialEvent.is_active),
        });
      } else {
        const start = new Date(Date.now() + 7 * 86400000);
        const end = new Date(start.getTime() + 4 * 3600000);
        setForm({
          title: "",
          category: "CONCERT",
          venue_name: "",
          venue_address: "",
          start_datetime: start.toISOString().slice(0, 16),
          end_datetime: end.toISOString().slice(0, 16),
          artist_names: "",
          banner_url: "",
          description: "",
          is_featured: false,
          is_active: true,
        });
      }
    }
  }, [isOpen, initialEvent]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        title: form.title.trim(),
        category: form.category,
        venue_name: form.venue_name.trim(),
        venue_address: form.venue_address.trim(),
        start_datetime: form.start_datetime,
        end_datetime: form.end_datetime,
        artist_names: form.artist_names.trim() || null,
        banner_url: form.banner_url.trim() || null,
        description: form.description.trim() || null,
        is_featured: form.is_featured,
        is_active: form.is_active,
      };
      if (initialEvent) {
        await apiRequest(`/partners/events/${initialEvent.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast.success("Event updated", payload.title);
      } else {
        await apiRequest("/partners/events", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.success("Event published", payload.title);
      }
      await onSaved();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to save event.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <FormModal
      isOpen={isOpen}
      onClose={onClose}
      onSubmit={handleSubmit}
      size="lg"
      title={initialEvent ? "Edit Live Event" : "Create New Live Event"}
      submitLabel={initialEvent ? "Update Event" : "Publish Event"}
      loading={loading}
      error={error}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Event Title"
          required
          placeholder="e.g. Sunburn Arena Hyderabad"
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
        <Select
          label="Event Category"
          value={form.category}
          onChange={(e) => setForm({ ...form, category: e.target.value })}
        >
          <option value="CONCERT">Concert / Live Music</option>
          <option value="COMEDY">Comedy Special</option>
          <option value="FESTIVAL">Festival</option>
          <option value="THEATRE">Theatre &amp; Performing Arts</option>
          <option value="WORKSHOP">Workshop</option>
        </Select>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Venue Name"
          required
          placeholder="HITEX Exhibition Center"
          value={form.venue_name}
          onChange={(e) => setForm({ ...form, venue_name: e.target.value })}
        />
        <Input
          label="Artist / Lineup Names"
          placeholder="Alan Walker, KSHMR..."
          value={form.artist_names}
          onChange={(e) => setForm({ ...form, artist_names: e.target.value })}
        />
      </div>

      <Input
        label="Venue Street Address"
        required
        value={form.venue_address}
        onChange={(e) => setForm({ ...form, venue_address: e.target.value })}
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Start Date &amp; Time"
          type="datetime-local"
          required
          value={form.start_datetime}
          onChange={(e) => setForm({ ...form, start_datetime: e.target.value })}
        />
        <Input
          label="End Date &amp; Time"
          type="datetime-local"
          required
          value={form.end_datetime}
          onChange={(e) => setForm({ ...form, end_datetime: e.target.value })}
        />
      </div>

      <Textarea
        label="Event Description"
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
      />

      <Input
        label="Banner Image URL (Optional)"
        placeholder="https://..."
        value={form.banner_url}
        onChange={(e) => setForm({ ...form, banner_url: e.target.value })}
      />

      <div className="flex flex-wrap items-center gap-5 text-xs text-primary">
        <label className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_featured}
            onChange={(e) => setForm({ ...form, is_featured: e.target.checked })}
            className="w-4 h-4 accent-gold-500 rounded"
          />
          <span>Feature in discovery highlights</span>
        </label>
        {initialEvent && (
          <label className="inline-flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) =>
                setForm({ ...form, is_active: e.target.checked })
              }
              className="w-4 h-4 accent-console-500 rounded"
            />
            <span>Event Active / Bookable</span>
          </label>
        )}
      </div>
    </FormModal>
  );
}

/* -------------------------------------------------------------------------- */
/* 7. EVENT: Add / Edit Ticket Tier Modal                                     */
/* -------------------------------------------------------------------------- */
export function EventTicketTierModal({
  isOpen,
  onClose,
  eventId,
  initialTier,
  onSaved,
}: {
  isOpen: boolean;
  onClose: () => void;
  eventId: number;
  initialTier?: EventTicketTypeRecord | null;
  onSaved: () => Promise<void>;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    price: "1499",
    total_quantity: "250",
    max_per_booking: "6",
  });

  useEffect(() => {
    if (isOpen) {
      setError(null);
      if (initialTier) {
        setForm({
          name: initialTier.name,
          description: initialTier.description || "",
          price: String(initialTier.price),
          total_quantity: String(initialTier.total_quantity),
          max_per_booking: String(initialTier.max_per_booking || 10),
        });
      } else {
        setForm({
          name: "",
          description: "",
          price: "1499",
          total_quantity: "250",
          max_per_booking: "6",
        });
      }
    }
  }, [isOpen, initialTier]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const totalQty = Number(form.total_quantity);
    if (!Number.isFinite(totalQty) || totalQty <= 0) {
      setError("Total quantity must be greater than zero.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim() || null,
        price: Number(form.price) || 0,
        total_quantity: totalQty,
        max_per_booking: Number(form.max_per_booking) || 10,
      };
      if (initialTier) {
        await apiRequest(`/partners/events/tickets/${initialTier.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast.success("Ticket tier updated", payload.name);
      } else {
        await apiRequest(`/partners/events/${eventId}/tickets`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.success("Ticket tier added", payload.name);
      }
      await onSaved();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to save ticket tier.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <FormModal
      isOpen={isOpen}
      onClose={onClose}
      onSubmit={handleSubmit}
      title={initialTier ? "Edit Ticket Tier" : "Add Event Ticket Tier"}
      submitLabel={initialTier ? "Save Tier" : "Create Ticket Tier"}
      loading={loading}
      error={error}
    >
      <Input
        label="Tier Name"
        required
        placeholder="e.g. Early Bird, Fanpit, VIP Lounge"
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Input
          label="Ticket Price (₹)"
          type="number"
          min="0"
          step="1"
          required
          value={form.price}
          onChange={(e) => setForm({ ...form, price: e.target.value })}
        />
        <Input
          label="Total Capacity"
          type="number"
          min="1"
          required
          value={form.total_quantity}
          onChange={(e) => setForm({ ...form, total_quantity: e.target.value })}
        />
        <Input
          label="Max Per Booking"
          type="number"
          min="1"
          max="20"
          required
          value={form.max_per_booking}
          onChange={(e) =>
            setForm({ ...form, max_per_booking: e.target.value })
          }
        />
      </div>

      <Textarea
        label="Pass Inclusions / Perks"
        placeholder="Dedicated fast-track entry, stage-front standing zone..."
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
      />
    </FormModal>
  );
}

/* -------------------------------------------------------------------------- */
/* 8. SPORTS: Create / Edit Venue Modal                                       */
/* -------------------------------------------------------------------------- */
export function SportsVenueModal({
  isOpen,
  onClose,
  initialVenue,
  onSaved,
}: {
  isOpen: boolean;
  onClose: () => void;
  initialVenue?: SportsVenueRecord | null;
  onSaved: () => Promise<void>;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    address: "",
    sport_types: "Football, Badminton, Cricket",
    amenities: "Floodlights, Parking, Drinking Water",
    is_active: true,
  });

  useEffect(() => {
    if (isOpen) {
      setError(null);
      if (initialVenue) {
        setForm({
          name: initialVenue.name,
          address: initialVenue.address || "",
          sport_types: (initialVenue.sport_types || []).join(", "),
          amenities: (initialVenue.amenities || []).join(", "),
          is_active: Boolean(initialVenue.is_active),
        });
      } else {
        setForm({
          name: "",
          address: "",
          sport_types: "Football, Badminton, Cricket",
          amenities: "Floodlights, Parking, Drinking Water",
          is_active: true,
        });
      }
    }
  }, [isOpen, initialVenue]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        address: form.address.trim(),
        sport_types: form.sport_types
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        amenities: form.amenities
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        is_active: form.is_active,
      };
      if (initialVenue) {
        await apiRequest(`/partners/sports/venues/${initialVenue.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast.success("Sports venue updated", payload.name);
      } else {
        await apiRequest("/partners/sports/venues", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.success("Sports venue created", payload.name);
      }
      await onSaved();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to save sports venue.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <FormModal
      isOpen={isOpen}
      onClose={onClose}
      onSubmit={handleSubmit}
      title={initialVenue ? "Edit Sports Arena / Turf" : "Add Sports Arena / Turf"}
      submitLabel={initialVenue ? "Save Arena" : "Create Arena"}
      loading={loading}
      error={error}
    >
      <Input
        label="Arena / Complex Name"
        required
        placeholder="e.g. Gachibowli Smash Arena"
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
      />
      <Input
        label="Street Address"
        required
        value={form.address}
        onChange={(e) => setForm({ ...form, address: e.target.value })}
      />
      <Input
        label="Sport Disciplines (comma-separated)"
        placeholder="Badminton, Turf Football, Box Cricket"
        value={form.sport_types}
        onChange={(e) => setForm({ ...form, sport_types: e.target.value })}
      />
      <Input
        label="Facility Amenities (comma-separated)"
        placeholder="Floodlights, Shower Rooms, Lockers"
        value={form.amenities}
        onChange={(e) => setForm({ ...form, amenities: e.target.value })}
      />
      {initialVenue && (
        <label className="inline-flex items-center gap-2 text-xs text-primary cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            className="w-4 h-4 accent-console-500 rounded"
          />
          <span>Venue Active</span>
        </label>
      )}
    </FormModal>
  );
}

/* -------------------------------------------------------------------------- */
/* 9. SPORTS & ACTIVITIES: Create / Edit Activity Modal                       */
/* -------------------------------------------------------------------------- */
export function ActivityFormModal({
  isOpen,
  onClose,
  initialActivity,
  venues,
  onSaved,
}: {
  isOpen: boolean;
  onClose: () => void;
  initialActivity?: ActivityRecord | null;
  venues: SportsVenueRecord[];
  onSaved: () => Promise<void>;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    category: "SPORTS",
    venue_id: "",
    base_price: "800",
    duration_minutes: "60",
    min_age: "5",
    description: "",
    image_url: "",
    is_active: true,
  });

  useEffect(() => {
    if (isOpen) {
      setError(null);
      if (initialActivity) {
        setForm({
          title: initialActivity.title,
          category: initialActivity.category || "SPORTS",
          venue_id: initialActivity.venue_id ? String(initialActivity.venue_id) : "",
          base_price: String(initialActivity.base_price),
          duration_minutes: String(initialActivity.duration_minutes || 60),
          min_age: String(initialActivity.min_age || 5),
          description: initialActivity.description || "",
          image_url: initialActivity.image_url || "",
          is_active: Boolean(initialActivity.is_active),
        });
      } else {
        setForm({
          title: "",
          category: "SPORTS",
          venue_id: venues[0] ? String(venues[0].id) : "",
          base_price: "800",
          duration_minutes: "60",
          min_age: "5",
          description: "",
          image_url: "",
          is_active: true,
        });
      }
    }
  }, [isOpen, initialActivity, venues]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        title: form.title.trim(),
        category: form.category,
        venue_id: form.venue_id ? Number(form.venue_id) : null,
        base_price: Number(form.base_price) || 0,
        duration_minutes: Number(form.duration_minutes) || 60,
        min_age: Number(form.min_age) || 5,
        description: form.description.trim() || null,
        image_url: form.image_url.trim() || null,
        is_active: form.is_active,
      };
      if (initialActivity) {
        await apiRequest(`/partners/activities/${initialActivity.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast.success("Activity updated", payload.title);
      } else {
        await apiRequest("/partners/activities", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.success("Activity created", payload.title);
      }
      await onSaved();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to save activity.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <FormModal
      isOpen={isOpen}
      onClose={onClose}
      onSubmit={handleSubmit}
      title={initialActivity ? "Edit Activity / Court" : "Add Activity / Court Listing"}
      submitLabel={initialActivity ? "Update Listing" : "Create Activity"}
      loading={loading}
      error={error}
    >
      <Input
        label="Listing Title"
        required
        placeholder="e.g. Court 1 — Synthetic Badminton"
        value={form.title}
        onChange={(e) => setForm({ ...form, title: e.target.value })}
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Select
          label="Category"
          value={form.category}
          onChange={(e) => setForm({ ...form, category: e.target.value })}
        >
          <option value="SPORTS">Sports &amp; Turf</option>
          <option value="GAMING_ZONE">Gaming Zone</option>
          <option value="AMUSEMENT">Amusement Park</option>
          <option value="ADVENTURE">Adventure Experience</option>
        </Select>

        <Select
          label="Linked Sports Venue (Optional)"
          value={form.venue_id}
          onChange={(e) => setForm({ ...form, venue_id: e.target.value })}
        >
          <option value="">Standalone Experience</option>
          {venues.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </Select>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Input
          label="Base Price (₹)"
          type="number"
          min="0"
          required
          value={form.base_price}
          onChange={(e) => setForm({ ...form, base_price: e.target.value })}
        />
        <Input
          label="Duration (Mins)"
          type="number"
          min="15"
          required
          value={form.duration_minutes}
          onChange={(e) =>
            setForm({ ...form, duration_minutes: e.target.value })
          }
        />
        <Input
          label="Min Age"
          type="number"
          min="1"
          required
          value={form.min_age}
          onChange={(e) => setForm({ ...form, min_age: e.target.value })}
        />
      </div>

      <Textarea
        label="Description &amp; Rules"
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
      />

      {initialActivity && (
        <label className="inline-flex items-center gap-2 text-xs text-primary cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            className="w-4 h-4 accent-console-500 rounded"
          />
          <span>Listing Active</span>
        </label>
      )}
    </FormModal>
  );
}

/* -------------------------------------------------------------------------- */
/* 10. SPORTS & ACTIVITIES: Create / Edit Activity Slot Modal                 */
/* -------------------------------------------------------------------------- */
export function ActivitySlotModal({
  isOpen,
  onClose,
  activityId,
  initialSlot,
  onSaved,
}: {
  isOpen: boolean;
  onClose: () => void;
  activityId: number;
  initialSlot?: ActivitySlotRecord | null;
  onSaved: () => Promise<void>;
}) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    slot_date: new Date().toISOString().split("T")[0],
    start_time: "07:00",
    end_time: "08:00",
    capacity: "10",
    price_override: "",
    is_available: true,
  });

  useEffect(() => {
    if (isOpen) {
      setError(null);
      if (initialSlot) {
        setForm({
          slot_date: initialSlot.slot_date,
          start_time: initialSlot.start_time,
          end_time: initialSlot.end_time,
          capacity: String(initialSlot.capacity),
          price_override:
            initialSlot.price_override !== null &&
            initialSlot.price_override !== undefined
              ? String(initialSlot.price_override)
              : "",
          is_available: Boolean(initialSlot.is_available),
        });
      } else {
        setForm({
          slot_date: new Date().toISOString().split("T")[0],
          start_time: "07:00",
          end_time: "08:00",
          capacity: "10",
          price_override: "",
          is_available: true,
        });
      }
    }
  }, [isOpen, initialSlot]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cap = Number(form.capacity);
    if (!Number.isFinite(cap) || cap <= 0) {
      setError("Slot capacity must be greater than zero.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      if (initialSlot) {
        await apiRequest(`/partners/activities/slots/${initialSlot.id}`, {
          method: "PUT",
          body: JSON.stringify({
            capacity: cap,
            price_override:
              form.price_override.trim() !== ""
                ? Number(form.price_override)
                : null,
            is_available: form.is_available,
          }),
        });
        toast.success("Time slot updated");
      } else {
        await apiRequest(`/partners/activities/${activityId}/slots`, {
          method: "POST",
          body: JSON.stringify({
            slot_date: form.slot_date,
            start_time: form.start_time,
            end_time: form.end_time,
            capacity: cap,
            price_override:
              form.price_override.trim() !== ""
                ? Number(form.price_override)
                : null,
            is_available: form.is_available,
          }),
        });
        toast.success("Time slot scheduled");
      }
      await onSaved();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to save time slot.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <FormModal
      isOpen={isOpen}
      onClose={onClose}
      onSubmit={handleSubmit}
      title={initialSlot ? "Edit Slot Capacity & Pricing" : "Schedule New Slot"}
      submitLabel={initialSlot ? "Save Slot" : "Create Slot"}
      loading={loading}
      error={error}
    >
      {!initialSlot && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Input
            label="Slot Date"
            type="date"
            required
            value={form.slot_date}
            onChange={(e) => setForm({ ...form, slot_date: e.target.value })}
          />
          <Input
            label="Start Time"
            type="time"
            required
            value={form.start_time}
            onChange={(e) => setForm({ ...form, start_time: e.target.value })}
          />
          <Input
            label="End Time"
            type="time"
            required
            value={form.end_time}
            onChange={(e) => setForm({ ...form, end_time: e.target.value })}
          />
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Slot Capacity"
          type="number"
          min="1"
          required
          value={form.capacity}
          onChange={(e) => setForm({ ...form, capacity: e.target.value })}
        />
        <Input
          label="Price Override ₹ (Optional)"
          type="number"
          min="0"
          placeholder="Leave empty to use base price"
          value={form.price_override}
          onChange={(e) => setForm({ ...form, price_override: e.target.value })}
        />
      </div>

      <label className="inline-flex items-center gap-2 text-xs text-primary cursor-pointer">
        <input
          type="checkbox"
          checked={form.is_available}
          onChange={(e) => setForm({ ...form, is_available: e.target.checked })}
          className="w-4 h-4 accent-console-500 rounded"
        />
        <span>Available for customer booking</span>
      </label>
    </FormModal>
  );
}


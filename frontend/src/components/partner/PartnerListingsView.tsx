"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Armchair,
  CalendarPlus,
  Clock,
  Edit3,
  Film,
  MapPin,
  Plus,
  Search,
  Sparkles,
  Ticket,
  Trash2,
  Trophy,
  Utensils,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import {
  ConfirmationModal,
  StatusBadge,
  useToast,
} from "@/components/dashboard";
import { formatRupees } from "@/lib/pricing";
import {
  ActivityRecord,
  CinemaProfile,
  DiningTableRecord,
  EventDetailRecord,
  EventRecord,
  EventTicketTypeRecord,
  MenuItemRecord,
  MovieShowRecord,
  MovieSummary,
  PartnerProfile,
  PartnerTabId,
  RestaurantProfile,
  ScreenRecord,
  SportsVenueRecord,
} from "./partnerTypes";
import {
  ActivityFormModal,
  CinemaScreenModal,
  CinemaSeatMapModal,
  DiningTableModal,
  EventFormModal,
  EventTicketTierModal,
  MenuItemModal,
  ScheduleShowModal,
  SportsVenueModal,
} from "./PartnerModals";

export function PartnerListingsView({
  partnerProfile,
  onNavigate,
  restaurantProfile,
  menus,
  tables,
  cinemaProfile,
  screens,
  shows,
  movies,
  events,
  venues,
  activities,
  onReloadVertical,
}: {
  partnerProfile: PartnerProfile;
  onNavigate: (tab: PartnerTabId) => void;
  restaurantProfile: RestaurantProfile | null;
  menus: MenuItemRecord[];
  tables: DiningTableRecord[];
  cinemaProfile: CinemaProfile | null;
  screens: ScreenRecord[];
  shows: MovieShowRecord[];
  movies: MovieSummary[];
  events: EventRecord[];
  venues: SportsVenueRecord[];
  activities: ActivityRecord[];
  onReloadVertical: () => Promise<void>;
}) {
  const toast = useToast();
  const pType = partnerProfile.partner_type;

  // Restaurant profile edit state
  const [restForm, setRestForm] = useState({
    name: "",
    cuisines: "",
    cost_for_two: "1200",
    timings: "",
    address: "",
    phone: "",
    has_buffet: false,
    has_alcohol: false,
    is_pure_veg: false,
    is_active: true,
  });
  const [savingRest, setSavingRest] = useState(false);

  // Menu filter state
  const [menuSearch, setMenuSearch] = useState("");
  const [menuCategory, setMenuCategory] = useState("ALL");

  // Cinema profile edit state
  const [cinemaForm, setCinemaForm] = useState({
    name: "",
    address: "",
    amenities: "",
    is_active: true,
  });
  const [savingCinema, setSavingCinema] = useState(false);

  // Active modals
  const [menuModalOpen, setMenuModalOpen] = useState(false);
  const [editingMenu, setEditingMenu] = useState<MenuItemRecord | null>(null);
  const [tableModalOpen, setTableModalOpen] = useState(false);
  const [editingTable, setEditingTable] = useState<DiningTableRecord | null>(null);

  const [screenModalOpen, setScreenModalOpen] = useState(false);
  const [seatMapScreen, setSeatMapScreen] = useState<ScreenRecord | null>(null);
  const [showModalOpen, setShowModalOpen] = useState(false);

  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<EventRecord | null>(null);
  const [selectedEventDetail, setSelectedEventDetail] =
    useState<EventDetailRecord | null>(null);
  const [tierModalOpen, setTierModalOpen] = useState(false);
  const [editingTier, setEditingTier] =
    useState<EventTicketTypeRecord | null>(null);

  const [venueModalOpen, setVenueModalOpen] = useState(false);
  const [editingVenue, setEditingVenue] = useState<SportsVenueRecord | null>(null);
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [editingActivity, setEditingActivity] = useState<ActivityRecord | null>(
    null
  );

  // Confirmation dialog state
  const [confirmState, setConfirmState] = useState<{
    title: string;
    description: string;
    confirmLabel: string;
    onConfirm: () => Promise<void>;
  } | null>(null);

  useEffect(() => {
    if (restaurantProfile) {
      setRestForm({
        name: restaurantProfile.name || "",
        cuisines: (restaurantProfile.cuisines || []).join(", "),
        cost_for_two: String(restaurantProfile.cost_for_two || 1000),
        timings: restaurantProfile.timings || "",
        address: restaurantProfile.address || "",
        phone: restaurantProfile.phone || "",
        has_buffet: Boolean(restaurantProfile.has_buffet),
        has_alcohol: Boolean(restaurantProfile.has_alcohol),
        is_pure_veg: Boolean(restaurantProfile.is_pure_veg),
        is_active: Boolean(restaurantProfile.is_active),
      });
    }
  }, [restaurantProfile]);

  useEffect(() => {
    if (cinemaProfile) {
      setCinemaForm({
        name: cinemaProfile.name || "",
        address: cinemaProfile.address || "",
        amenities: (cinemaProfile.amenities || []).join(", "),
        is_active: Boolean(cinemaProfile.is_active),
      });
    }
  }, [cinemaProfile]);

  const loadEventDetail = async (eventId: number) => {
    try {
      const detail = await apiRequest<EventDetailRecord>(
        `/partners/events/${eventId}`
      );
      setSelectedEventDetail(detail);
    } catch (err: any) {
      toast.error("Unable to inspect event", err.message || "");
    }
  };

  useEffect(() => {
    if (pType === "EVENT" && events.length > 0 && !selectedEventDetail) {
      loadEventDetail(events[0].id);
    }
  }, [pType, events]); // eslint-disable-line react-hooks/exhaustive-deps

  const menuCategories = useMemo(() => {
    const set = new Set(menus.map((m) => m.category).filter(Boolean));
    return ["ALL", ...Array.from(set)];
  }, [menus]);

  const filteredMenus = useMemo(() => {
    return menus.filter((m) => {
      if (menuCategory !== "ALL" && m.category !== menuCategory) return false;
      if (
        menuSearch.trim() &&
        !m.item_name.toLowerCase().includes(menuSearch.trim().toLowerCase()) &&
        !(m.description || "")
          .toLowerCase()
          .includes(menuSearch.trim().toLowerCase())
      ) {
        return false;
      }
      return true;
    });
  }, [menus, menuCategory, menuSearch]);

  const handleSaveRestaurantProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingRest(true);
    try {
      await apiRequest("/partners/restaurant/profile", {
        method: "PUT",
        body: JSON.stringify({
          name: restForm.name.trim(),
          cuisines: restForm.cuisines
            .split(",")
            .map((c) => c.trim())
            .filter(Boolean),
          cost_for_two: Number(restForm.cost_for_two) || 1000,
          timings: restForm.timings.trim(),
          address: restForm.address.trim(),
          phone: restForm.phone.trim(),
          has_buffet: restForm.has_buffet,
          has_alcohol: restForm.has_alcohol,
          is_pure_veg: restForm.is_pure_veg,
          is_active: restForm.is_active,
        }),
      });
      toast.success("Restaurant profile saved");
      await onReloadVertical();
    } catch (err: any) {
      toast.error("Failed to update restaurant", err.message || "");
    } finally {
      setSavingRest(false);
    }
  };

  const handleToggleDishAvailability = async (dish: MenuItemRecord) => {
    try {
      await apiRequest(`/partners/restaurant/menus/${dish.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_available: !dish.is_available }),
      });
      toast.success(
        dish.is_available ? "Marked out of stock" : "Marked available",
        dish.item_name
      );
      await onReloadVertical();
    } catch (err: any) {
      toast.error("Failed to update dish", err.message || "");
    }
  };

  const handleSaveCinemaProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingCinema(true);
    try {
      await apiRequest("/partners/cinema/profile", {
        method: "PUT",
        body: JSON.stringify({
          name: cinemaForm.name.trim(),
          address: cinemaForm.address.trim(),
          amenities: cinemaForm.amenities
            .split(",")
            .map((a) => a.trim())
            .filter(Boolean),
          is_active: cinemaForm.is_active,
        }),
      });
      toast.success("Multiplex profile saved");
      await onReloadVertical();
    } catch (err: any) {
      toast.error("Failed to save cinema profile", err.message || "");
    } finally {
      setSavingCinema(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* ------------------------------------------------------------------ */}
      {/* VERTICAL 1: RESTAURANT MANAGEMENT                                  */}
      {/* ------------------------------------------------------------------ */}
      {pType === "RESTAURANT" && (
        <>
          <form
            onSubmit={handleSaveRestaurantProfile}
            className="rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-subtle">
              <div className="flex items-center gap-2.5">
                <Utensils className="w-5 h-5 text-gold-400" />
                <div>
                  <h2 className="font-display text-base sm:text-lg font-bold text-primary">
                    Restaurant Venue Settings
                  </h2>
                  <p className="text-xs text-muted">
                    Update storefront details, dining cost, cuisines, and dietary flags.
                  </p>
                </div>
              </div>
              <Button type="submit" variant="console" size="sm" isLoading={savingRest}>
                Save Restaurant Info
              </Button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Input
                label="Restaurant Name"
                value={restForm.name}
                onChange={(e) => setRestForm({ ...restForm, name: e.target.value })}
              />
              <Input
                label="Cuisines (comma-separated)"
                value={restForm.cuisines}
                onChange={(e) =>
                  setRestForm({ ...restForm, cuisines: e.target.value })
                }
              />
              <Input
                label="Avg Cost For Two (₹)"
                type="number"
                value={restForm.cost_for_two}
                onChange={(e) =>
                  setRestForm({ ...restForm, cost_for_two: e.target.value })
                }
              />
              <Input
                label="Opening Hours"
                value={restForm.timings}
                onChange={(e) =>
                  setRestForm({ ...restForm, timings: e.target.value })
                }
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-center">
              <Input
                label="Address"
                containerClassName="sm:col-span-2"
                value={restForm.address}
                onChange={(e) =>
                  setRestForm({ ...restForm, address: e.target.value })
                }
              />
              <Input
                label="Booking Desk Phone"
                value={restForm.phone}
                onChange={(e) =>
                  setRestForm({ ...restForm, phone: e.target.value })
                }
              />
            </div>

            <div className="flex flex-wrap items-center gap-5 text-xs text-primary">
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={restForm.is_pure_veg}
                  onChange={(e) =>
                    setRestForm({ ...restForm, is_pure_veg: e.target.checked })
                  }
                  className="w-4 h-4 accent-emerald-500 rounded"
                />
                <span>Pure Veg</span>
              </label>
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={restForm.has_buffet}
                  onChange={(e) =>
                    setRestForm({ ...restForm, has_buffet: e.target.checked })
                  }
                  className="w-4 h-4 accent-console-500 rounded"
                />
                <span>Buffet Available</span>
              </label>
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={restForm.has_alcohol}
                  onChange={(e) =>
                    setRestForm({ ...restForm, has_alcohol: e.target.checked })
                  }
                  className="w-4 h-4 accent-console-500 rounded"
                />
                <span>Serves Beverages / Bar</span>
              </label>
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={restForm.is_active}
                  onChange={(e) =>
                    setRestForm({ ...restForm, is_active: e.target.checked })
                  }
                  className="w-4 h-4 accent-console-500 rounded"
                />
                <span>Storefront Active</span>
              </label>
            </div>
          </form>

          {/* Menu Catalog */}
          <div className="rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="font-display text-base sm:text-lg font-bold text-primary">
                  Menu Catalog ({menus.length} Dishes)
                </h3>
                <p className="text-xs text-muted">
                  Toggle dish stock, filter by course, or add new signature plates.
                </p>
              </div>
              <Button
                variant="console"
                size="sm"
                leftIcon={<Plus className="w-4 h-4" />}
                onClick={() => {
                  setEditingMenu(null);
                  setMenuModalOpen(true);
                }}
              >
                Add Dish
              </Button>
            </div>

            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-1">
                {menuCategories.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setMenuCategory(cat)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap border transition-colors ${
                      menuCategory === cat
                        ? "bg-console-600 border-console-500 text-white"
                        : "bg-surface-2 border-subtle text-secondary hover:text-primary"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
              <div className="relative w-full md:w-64 shrink-0">
                <Search className="w-3.5 h-3.5 text-muted absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Filter dishes..."
                  value={menuSearch}
                  onChange={(e) => setMenuSearch(e.target.value)}
                  className="w-full h-9 pl-9 pr-3 rounded-lg bg-surface-2 border border-subtle text-xs text-primary placeholder:text-muted focus:outline-none focus:border-console-500"
                />
              </div>
            </div>

            {filteredMenus.length === 0 ? (
              <div className="rounded-xl border border-dashed border-subtle p-8 text-center text-xs text-muted">
                No dishes match the active filter.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5">
                {filteredMenus.map((dish) => (
                  <div
                    key={dish.id}
                    className="rounded-xl bg-surface-2/80 border border-subtle hover:border-strong p-4 flex flex-col justify-between gap-3"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className={`w-2.5 h-2.5 rounded-sm border shrink-0 ${
                                dish.is_veg
                                  ? "border-emerald-400 bg-emerald-500/30"
                                  : "border-red-400 bg-red-500/30"
                              }`}
                              title={dish.is_veg ? "Veg" : "Non-Veg"}
                            />
                            <h4 className="font-semibold text-sm text-primary truncate">
                              {dish.item_name}
                            </h4>
                          </div>
                          <span className="text-[11px] text-muted">
                            {dish.category}
                            {dish.is_bestseller ? " · ★ Bestseller" : ""}
                          </span>
                        </div>
                        <span className="font-display font-bold text-sm text-primary tabular-nums-lining shrink-0">
                          {formatRupees(dish.price)}
                        </span>
                      </div>
                      {dish.description ? (
                        <p className="text-xs text-secondary line-clamp-2">
                          {dish.description}
                        </p>
                      ) : null}
                    </div>

                    <div className="pt-2.5 border-t border-subtle flex items-center justify-between gap-2">
                      <button
                        type="button"
                        onClick={() => handleToggleDishAvailability(dish)}
                        className={`text-[11px] font-semibold px-2.5 py-1 rounded-md border transition-colors ${
                          dish.is_available
                            ? "bg-emerald-500/12 border-emerald-500/30 text-emerald-300"
                            : "bg-red-500/12 border-red-500/30 text-red-300"
                        }`}
                      >
                        {dish.is_available ? "Available" : "Out of Stock"}
                      </button>

                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          aria-label={`Edit ${dish.item_name}`}
                          onClick={() => {
                            setEditingMenu(dish);
                            setMenuModalOpen(true);
                          }}
                          className="p-1.5 rounded-lg text-secondary hover:text-primary hover:bg-surface-3 transition-colors"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          aria-label={`Delete ${dish.item_name}`}
                          onClick={() =>
                            setConfirmState({
                              title: "Delete Menu Item",
                              description: `Permanently remove "${dish.item_name}" from your menu catalog?`,
                              confirmLabel: "Delete Dish",
                              onConfirm: async () => {
                                await apiRequest(
                                  `/partners/restaurant/menus/${dish.id}`,
                                  { method: "DELETE" }
                                );
                                toast.success("Dish removed", dish.item_name);
                                await onReloadVertical();
                              },
                            })
                          }
                          className="p-1.5 rounded-lg text-secondary hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Dining Floor Tables */}
          <div className="rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="font-display text-base sm:text-lg font-bold text-primary">
                  Dining Floor Tables ({tables.length})
                </h3>
                <p className="text-xs text-muted">
                  Configure seating capacity &amp; zones for automated reservation matching.
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                leftIcon={<Plus className="w-4 h-4" />}
                onClick={() => {
                  setEditingTable(null);
                  setTableModalOpen(true);
                }}
              >
                Add Table
              </Button>
            </div>

            {tables.length === 0 ? (
              <div className="rounded-xl border border-dashed border-subtle p-8 text-center text-xs text-muted">
                No dining tables configured yet.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                {tables.map((tbl) => (
                  <div
                    key={tbl.id}
                    className="rounded-xl bg-surface-2/80 border border-subtle p-4 flex flex-col justify-between gap-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-display font-bold text-sm text-primary">
                          Table {tbl.table_number}
                        </div>
                        <div className="text-xs text-secondary mt-0.5">
                          {tbl.capacity} Guests · {tbl.zone}
                        </div>
                      </div>
                      <StatusBadge
                        status={tbl.is_active ? "ACTIVE" : "DISABLED"}
                      />
                    </div>
                    <div className="flex items-center justify-end gap-1.5 pt-2 border-t border-subtle">
                      <Button
                        variant="ghost"
                        size="xs"
                        leftIcon={<Edit3 className="w-3.5 h-3.5" />}
                        onClick={() => {
                          setEditingTable(tbl);
                          setTableModalOpen(true);
                        }}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="danger"
                        size="xs"
                        onClick={() =>
                          setConfirmState({
                            title: "Remove Dining Table",
                            description: `Delete Table ${tbl.table_number} (${tbl.zone})?`,
                            confirmLabel: "Remove Table",
                            onConfirm: async () => {
                              await apiRequest(
                                `/partners/restaurant/tables/${tbl.id}`,
                                { method: "DELETE" }
                              );
                              toast.success("Table removed");
                              await onReloadVertical();
                            },
                          })
                        }
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* VERTICAL 2: CINEMA MANAGEMENT                                      */}
      {/* ------------------------------------------------------------------ */}
      {pType === "CINEMA" && (
        <>
          <form
            onSubmit={handleSaveCinemaProfile}
            className="rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-subtle">
              <div className="flex items-center gap-2.5">
                <Film className="w-5 h-5 text-console-400" />
                <div>
                  <h2 className="font-display text-base sm:text-lg font-bold text-primary">
                    Cinema Multiplex Configuration
                  </h2>
                  <p className="text-xs text-muted">
                    Update multiplex name, address, and customer amenities.
                  </p>
                </div>
              </div>
              <Button type="submit" variant="console" size="sm" isLoading={savingCinema}>
                Save Multiplex Info
              </Button>
            </div>

            <div className="space-y-4">
              <Input
                label="Multiplex Name"
                value={cinemaForm.name}
                onChange={(e) =>
                  setCinemaForm({ ...cinemaForm, name: e.target.value })
                }
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Textarea
                  label="Address"
                  rows={2}
                  value={cinemaForm.address}
                  onChange={(e) =>
                    setCinemaForm({ ...cinemaForm, address: e.target.value })
                  }
                />
                <Textarea
                  label="Amenities (comma-separated)"
                  rows={2}
                  value={cinemaForm.amenities}
                  onChange={(e) =>
                    setCinemaForm({ ...cinemaForm, amenities: e.target.value })
                  }
                />
              </div>
            </div>

            <label className="inline-flex items-center gap-2 text-xs text-primary cursor-pointer">
              <input
                type="checkbox"
                checked={cinemaForm.is_active}
                onChange={(e) =>
                  setCinemaForm({ ...cinemaForm, is_active: e.target.checked })
                }
                className="w-4 h-4 accent-console-500 rounded"
              />
              <span>Multiplex Active for Ticketing</span>
            </label>
          </form>

          {/* Auditorium Screens + Interactive Seat Map */}
          <div className="rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="font-display text-base sm:text-lg font-bold text-primary">
                  Auditorium Screens ({screens.length})
                </h3>
                <p className="text-xs text-muted">
                  Provision screens or customize per-seat tier &amp; base pricing maps.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  leftIcon={<Plus className="w-4 h-4" />}
                  onClick={() => setScreenModalOpen(true)}
                >
                  Add Screen
                </Button>
                <Button
                  variant="console"
                  size="sm"
                  leftIcon={<CalendarPlus className="w-4 h-4" />}
                  onClick={() => setShowModalOpen(true)}
                >
                  Schedule Show
                </Button>
              </div>
            </div>

            {screens.length === 0 ? (
              <div className="rounded-xl border border-dashed border-subtle p-8 text-center text-xs text-muted">
                No auditorium screens found. Click &ldquo;Add Screen&rdquo; to auto-generate your seating layout.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {screens.map((scr) => (
                  <div
                    key={scr.id}
                    className="rounded-xl bg-surface-2/80 border border-subtle p-4 flex flex-col justify-between gap-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-display font-bold text-sm text-primary">
                          {scr.name}
                        </div>
                        <div className="text-xs text-secondary mt-0.5 tabular-nums-lining">
                          {scr.total_seats} seats configured
                        </div>
                      </div>
                      <StatusBadge status={scr.screen_type} dot={false} />
                    </div>

                    <Button
                      variant="secondary"
                      size="xs"
                      fullWidth
                      leftIcon={<Armchair className="w-3.5 h-3.5" />}
                      onClick={() => setSeatMapScreen(scr)}
                    >
                      Configure Seat Map &amp; Pricing
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Shows Quick Summary */}
          <div className="rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="font-display text-base sm:text-lg font-bold text-primary">
                  Active Scheduled Shows ({shows.length})
                </h3>
                <p className="text-xs text-muted">
                  Recent showtimes published across your multiplex screens.
                </p>
              </div>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => onNavigate("schedules")}
              >
                Manage All Showtimes
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {shows.slice(0, 6).map((sh) => (
                <div
                  key={sh.id}
                  className="rounded-xl bg-surface-2/70 border border-subtle p-3.5 space-y-2 text-xs"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-semibold text-primary leading-snug">
                      {sh.movie_title}
                    </div>
                    <StatusBadge status={sh.status} />
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-1.5 text-secondary">
                    <span>{sh.screen_name}</span>
                    <span className="font-mono font-semibold text-primary whitespace-nowrap tabular-nums-lining">
                      {sh.show_date} · {sh.start_time?.slice(0, 5)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* VERTICAL 3: EVENTS & CONCERTS                                      */}
      {/* ------------------------------------------------------------------ */}
      {pType === "EVENT" && (
        <div className="space-y-6">
          <div className="rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <Sparkles className="w-5 h-5 text-console-400" />
                <div>
                  <h2 className="font-display text-base sm:text-lg font-bold text-primary">
                    Live Events Portfolio ({events.length})
                  </h2>
                  <p className="text-xs text-muted">
                    Select any event below to configure ticket tiers and pricing slabs.
                  </p>
                </div>
              </div>
              <Button
                variant="console"
                size="sm"
                leftIcon={<Plus className="w-4 h-4" />}
                onClick={() => {
                  setEditingEvent(null);
                  setEventModalOpen(true);
                }}
              >
                Create Event
              </Button>
            </div>

            {events.length === 0 ? (
              <div className="rounded-xl border border-dashed border-subtle p-8 text-center text-xs text-muted">
                No events created yet. Launch your first concert, comedy show, or festival!
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {events.map((ev) => {
                  const isSelected = selectedEventDetail?.id === ev.id;
                  return (
                    <div
                      key={ev.id}
                      onClick={() => loadEventDetail(ev.id)}
                      className={`rounded-xl border p-4 cursor-pointer transition-all flex flex-col justify-between gap-3 ${
                        isSelected
                          ? "bg-console-500/10 border-console-500/45 shadow-console-sm"
                          : "bg-surface-2/70 border-subtle hover:border-strong"
                      }`}
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-start justify-between gap-2">
                          <StatusBadge status={ev.category} dot={false} />
                          <StatusBadge
                            status={ev.is_active ? "ACTIVE" : "DISABLED"}
                          />
                        </div>
                        <h3 className="font-display font-bold text-base text-primary">
                          {ev.title}
                        </h3>
                        <p className="text-xs text-secondary flex items-center gap-1.5">
                          <MapPin className="w-3.5 h-3.5 text-muted shrink-0" />
                          <span className="truncate">{ev.venue_name}</span>
                        </p>
                        <p className="text-[11px] text-muted flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 shrink-0" />
                          <span>
                            {ev.start_datetime.slice(0, 16).replace("T", " ")}
                          </span>
                        </p>
                      </div>

                      <div
                        className="pt-2.5 border-t border-subtle flex items-center justify-between gap-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Button
                          variant="ghost"
                          size="xs"
                          leftIcon={<Edit3 className="w-3.5 h-3.5" />}
                          onClick={() => {
                            setEditingEvent(ev);
                            setEventModalOpen(true);
                          }}
                        >
                          Edit
                        </Button>
                        {ev.is_active && (
                          <Button
                            variant="danger"
                            size="xs"
                            onClick={() =>
                              setConfirmState({
                                title: "Deactivate Event",
                                description: `Hide "${ev.title}" from customer ticket sales?`,
                                confirmLabel: "Deactivate Event",
                                onConfirm: async () => {
                                  await apiRequest(`/partners/events/${ev.id}`, {
                                    method: "DELETE",
                                  });
                                  toast.success("Event deactivated", ev.title);
                                  await onReloadVertical();
                                },
                              })
                            }
                          >
                            Deactivate
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Ticket Tiers Inspector for Selected Event */}
          {selectedEventDetail && (
            <div className="rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-console-300">
                    Ticket Inventory Inspector
                  </span>
                  <h3 className="font-display text-base sm:text-lg font-bold text-primary">
                    {selectedEventDetail.title} — Pass Categories
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => onNavigate("schedules")}
                  >
                    View Attendees
                  </Button>
                  <Button
                    variant="console"
                    size="sm"
                    leftIcon={<Plus className="w-4 h-4" />}
                    onClick={() => {
                      setEditingTier(null);
                      setTierModalOpen(true);
                    }}
                  >
                    Add Ticket Tier
                  </Button>
                </div>
              </div>

              {selectedEventDetail.ticket_types.length === 0 ? (
                <div className="rounded-xl border border-dashed border-subtle p-8 text-center text-xs text-muted">
                  No ticket tiers created yet. Click &ldquo;Add Ticket Tier&rdquo; to enable ticket sales.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {selectedEventDetail.ticket_types.map((tier) => {
                    const sold =
                      tier.sold_quantity ??
                      Math.max(0, tier.total_quantity - tier.available_quantity);
                    const pct =
                      tier.total_quantity > 0
                        ? Math.round((sold / tier.total_quantity) * 100)
                        : 0;
                    return (
                      <div
                        key={tier.id}
                        className="rounded-xl bg-surface-2/80 border border-subtle p-4 space-y-3"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="flex items-center gap-1.5 font-semibold text-sm text-primary">
                              <Ticket className="w-3.5 h-3.5 text-console-400" />
                              <span>{tier.name}</span>
                            </div>
                            {tier.description ? (
                              <p className="text-[11px] text-secondary mt-0.5 line-clamp-2">
                                {tier.description}
                              </p>
                            ) : null}
                          </div>
                          <span className="font-display font-bold text-sm text-primary tabular-nums-lining">
                            {formatRupees(tier.price)}
                          </span>
                        </div>

                        <div className="space-y-1">
                          <div className="flex items-center justify-between text-[11px] text-secondary tabular-nums-lining">
                            <span>
                              Sold: <strong className="text-primary">{sold}</strong> /{" "}
                              {tier.total_quantity}
                            </span>
                            <span>{tier.available_quantity} left</span>
                          </div>
                          <div className="h-1.5 w-full rounded-full bg-surface overflow-hidden">
                            <div
                              className="h-full bg-console-500 rounded-full"
                              style={{ width: `${Math.min(100, pct)}%` }}
                            />
                          </div>
                        </div>

                        <div className="pt-2 border-t border-subtle flex items-center justify-between gap-2">
                          <span className="text-[11px] text-muted">
                            Max {tier.max_per_booking} / order
                          </span>
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              aria-label={`Edit tier ${tier.name}`}
                              onClick={() => {
                                setEditingTier(tier);
                                setTierModalOpen(true);
                              }}
                              className="p-1.5 rounded-lg text-secondary hover:text-primary hover:bg-surface-3"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              aria-label={`Delete tier ${tier.name}`}
                              onClick={() =>
                                setConfirmState({
                                  title: "Delete Ticket Tier",
                                  description: `Delete "${tier.name}" pass category from ${selectedEventDetail.title}?`,
                                  confirmLabel: "Delete Tier",
                                  onConfirm: async () => {
                                    await apiRequest(
                                      `/partners/events/tickets/${tier.id}`,
                                      { method: "DELETE" }
                                    );
                                    toast.success("Ticket tier deleted");
                                    await loadEventDetail(selectedEventDetail.id);
                                  },
                                })
                              }
                              className="p-1.5 rounded-lg text-secondary hover:text-red-400 hover:bg-red-500/10"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* VERTICAL 4 & 5: SPORTS & ACTIVITIES                                */}
      {/* ------------------------------------------------------------------ */}
      {(pType === "SPORTS" || pType === "ACTIVITIES") && (
        <div className="space-y-6">
          {/* Sports Venues Section */}
          <div className="rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <Trophy className="w-5 h-5 text-emerald-400" />
                <div>
                  <h2 className="font-display text-base sm:text-lg font-bold text-primary">
                    Sports Venues &amp; Complexes ({venues.length})
                  </h2>
                  <p className="text-xs text-muted">
                    Manage arenas, turf complexes, and facility amenities.
                  </p>
                </div>
              </div>
              <Button
                variant="secondary"
                size="sm"
                leftIcon={<Plus className="w-4 h-4" />}
                onClick={() => {
                  setEditingVenue(null);
                  setVenueModalOpen(true);
                }}
              >
                Add Sports Venue
              </Button>
            </div>

            {venues.length === 0 ? (
              <div className="rounded-xl border border-dashed border-subtle p-8 text-center text-xs text-muted">
                No sports venues registered yet.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {venues.map((venue) => (
                  <div
                    key={venue.id}
                    className="rounded-xl bg-surface-2/80 border border-subtle p-4 flex flex-col justify-between gap-3"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="font-display font-bold text-base text-primary">
                          {venue.name}
                        </h3>
                        <StatusBadge
                          status={venue.is_active ? "ACTIVE" : "DISABLED"}
                        />
                      </div>
                      <p className="text-xs text-secondary">{venue.address}</p>
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {venue.sport_types.map((st) => (
                          <span
                            key={st}
                            className="px-2 py-0.5 rounded-md bg-surface border border-subtle text-[11px] text-secondary"
                          >
                            {st}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="pt-2.5 border-t border-subtle flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="xs"
                        leftIcon={<Edit3 className="w-3.5 h-3.5" />}
                        onClick={() => {
                          setEditingVenue(venue);
                          setVenueModalOpen(true);
                        }}
                      >
                        Edit Venue
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Activities / Courts Catalog */}
          <div className="rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="font-display text-base sm:text-lg font-bold text-primary">
                  Courts, Turfs &amp; Activities ({activities.length})
                </h3>
                <p className="text-xs text-muted">
                  Configure hourly bookings, gaming arenas, or recreational activities.
                </p>
              </div>
              <Button
                variant="console"
                size="sm"
                leftIcon={<Plus className="w-4 h-4" />}
                onClick={() => {
                  setEditingActivity(null);
                  setActivityModalOpen(true);
                }}
              >
                Add Activity
              </Button>
            </div>

            {activities.length === 0 ? (
              <div className="rounded-xl border border-dashed border-subtle p-8 text-center text-xs text-muted">
                No activities or courts created yet.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {activities.map((act) => (
                  <div
                    key={act.id}
                    className="rounded-xl bg-surface-2/80 border border-subtle p-4 flex flex-col justify-between gap-3"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <StatusBadge status={act.category} dot={false} />
                        <StatusBadge
                          status={act.is_active ? "ACTIVE" : "DISABLED"}
                        />
                      </div>
                      <h4 className="font-display font-bold text-base text-primary">
                        {act.title}
                      </h4>
                      <div className="flex items-center justify-between text-xs text-secondary tabular-nums-lining">
                        <span>{act.duration_minutes} mins · Min {act.min_age}+ yrs</span>
                        <strong className="text-primary font-display text-sm">
                          {formatRupees(act.base_price)}
                        </strong>
                      </div>
                    </div>

                    <div className="pt-2.5 border-t border-subtle flex items-center justify-between gap-2">
                      <Button
                        variant="secondary"
                        size="xs"
                        onClick={() => onNavigate("schedules")}
                      >
                        Manage Slots
                      </Button>

                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="xs"
                          leftIcon={<Edit3 className="w-3.5 h-3.5" />}
                          onClick={() => {
                            setEditingActivity(act);
                            setActivityModalOpen(true);
                          }}
                        >
                          Edit
                        </Button>
                        {act.is_active && (
                          <Button
                            variant="danger"
                            size="xs"
                            onClick={() =>
                              setConfirmState({
                                title: "Deactivate Activity",
                                description: `Disable "${act.title}" from new customer slot bookings?`,
                                confirmLabel: "Deactivate",
                                onConfirm: async () => {
                                  await apiRequest(
                                    `/partners/activities/${act.id}`,
                                    { method: "DELETE" }
                                  );
                                  toast.success("Activity deactivated");
                                  await onReloadVertical();
                                },
                              })
                            }
                          >
                            Disable
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Wired CRUD Modals */}
      <MenuItemModal
        isOpen={menuModalOpen}
        onClose={() => setMenuModalOpen(false)}
        initialItem={editingMenu}
        onSaved={onReloadVertical}
      />

      <DiningTableModal
        isOpen={tableModalOpen}
        onClose={() => setTableModalOpen(false)}
        initialTable={editingTable}
        onSaved={onReloadVertical}
      />

      <CinemaScreenModal
        isOpen={screenModalOpen}
        onClose={() => setScreenModalOpen(false)}
        onSaved={onReloadVertical}
      />

      <CinemaSeatMapModal
        isOpen={Boolean(seatMapScreen)}
        onClose={() => setSeatMapScreen(null)}
        screen={seatMapScreen}
      />

      <ScheduleShowModal
        isOpen={showModalOpen}
        onClose={() => setShowModalOpen(false)}
        screens={screens}
        movies={movies}
        onSaved={onReloadVertical}
      />

      <EventFormModal
        isOpen={eventModalOpen}
        onClose={() => setEventModalOpen(false)}
        initialEvent={editingEvent}
        onSaved={async () => {
          await onReloadVertical();
          if (selectedEventDetail) {
            await loadEventDetail(selectedEventDetail.id);
          }
        }}
      />

      {selectedEventDetail && (
        <EventTicketTierModal
          isOpen={tierModalOpen}
          onClose={() => setTierModalOpen(false)}
          eventId={selectedEventDetail.id}
          initialTier={editingTier}
          onSaved={() => loadEventDetail(selectedEventDetail.id)}
        />
      )}

      <SportsVenueModal
        isOpen={venueModalOpen}
        onClose={() => setVenueModalOpen(false)}
        initialVenue={editingVenue}
        onSaved={onReloadVertical}
      />

      <ActivityFormModal
        isOpen={activityModalOpen}
        onClose={() => setActivityModalOpen(false)}
        initialActivity={editingActivity}
        venues={venues}
        onSaved={onReloadVertical}
      />

      <ConfirmationModal
        isOpen={Boolean(confirmState)}
        onClose={() => setConfirmState(null)}
        title={confirmState?.title || ""}
        description={confirmState?.description || ""}
        confirmLabel={confirmState?.confirmLabel || "Confirm"}
        onConfirm={async () => {
          if (confirmState) {
            await confirmState.onConfirm();
            setConfirmState(null);
          }
        }}
      />
    </div>
  );
}


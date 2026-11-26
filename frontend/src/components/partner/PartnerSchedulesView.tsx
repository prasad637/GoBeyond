"use client";

import React, { useEffect, useState } from "react";
import {
  Calendar,
  CalendarPlus,
  CheckCircle2,
  Clock,
  Copy,
  Edit3,
  Plus,
  Trash2,
  Users,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Input";
import {
  ConfirmationModal,
  DataTable,
  DataTableColumn,
  FilterDropdown,
  StatusBadge,
  useToast,
} from "@/components/dashboard";
import { formatRupees } from "@/lib/pricing";
import {
  ActivityRecord,
  ActivitySlotRecord,
  EventAttendeeRecord,
  EventRecord,
  MovieShowRecord,
  MovieSummary,
  PartnerProfile,
  ReservationRecord,
  ScreenRecord,
} from "./partnerTypes";
import { ActivitySlotModal, ScheduleShowModal } from "./PartnerModals";

export function PartnerSchedulesView({
  partnerProfile,
  reservations,
  shows,
  screens,
  movies,
  events,
  activities,
  onReloadVertical,
}: {
  partnerProfile: PartnerProfile;
  reservations: ReservationRecord[];
  shows: MovieShowRecord[];
  screens: ScreenRecord[];
  movies: MovieSummary[];
  events: EventRecord[];
  activities: ActivityRecord[];
  onReloadVertical: () => Promise<void>;
}) {
  const toast = useToast();
  const pType = partnerProfile.partner_type;

  // Restaurant reservation filters
  const [resDateFilter, setResDateFilter] = useState("");
  const [resStatusFilter, setResStatusFilter] = useState("");
  const [filteredReservations, setFilteredReservations] =
    useState<ReservationRecord[]>(reservations);

  // Cinema showtime filters + modal
  const [showDateFilter, setShowDateFilter] = useState("");
  const [filteredShows, setFilteredShows] = useState<MovieShowRecord[]>(shows);
  const [scheduleShowModalOpen, setScheduleShowModalOpen] = useState(false);

  // Event attendees state
  const [selectedEventId, setSelectedEventId] = useState<string>(
    events[0] ? String(events[0].id) : ""
  );
  const [attendees, setAttendees] = useState<EventAttendeeRecord[]>([]);
  const [loadingAttendees, setLoadingAttendees] = useState(false);

  // Sports / Activity slots state
  const [selectedActivityId, setSelectedActivityId] = useState<string>(
    activities[0] ? String(activities[0].id) : ""
  );
  const [slotDateFilter, setSlotDateFilter] = useState("");
  const [slots, setSlots] = useState<ActivitySlotRecord[]>([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [slotModalOpen, setSlotModalOpen] = useState(false);
  const [editingSlot, setEditingSlot] = useState<ActivitySlotRecord | null>(
    null
  );

  const [confirmState, setConfirmState] = useState<{
    title: string;
    description: string;
    confirmLabel: string;
    onConfirm: () => Promise<void>;
  } | null>(null);

  useEffect(() => {
    setFilteredReservations(reservations);
  }, [reservations]);

  useEffect(() => {
    setFilteredShows(shows);
  }, [shows]);

  useEffect(() => {
    if (pType === "EVENT" && events.length > 0 && !selectedEventId) {
      setSelectedEventId(String(events[0].id));
    }
  }, [pType, events, selectedEventId]);

  useEffect(() => {
    if (
      (pType === "SPORTS" || pType === "ACTIVITIES") &&
      activities.length > 0 &&
      !selectedActivityId
    ) {
      setSelectedActivityId(String(activities[0].id));
    }
  }, [pType, activities, selectedActivityId]);

  // Fetch filtered restaurant reservations
  useEffect(() => {
    if (pType !== "RESTAURANT") return;
    const params = new URLSearchParams();
    if (resStatusFilter) params.set("status", resStatusFilter);
    if (resDateFilter) params.set("date", resDateFilter);
    apiRequest<ReservationRecord[]>(
      `/partners/restaurant/reservations${
        params.toString() ? `?${params.toString()}` : ""
      }`
    )
      .then((res) => setFilteredReservations(res || []))
      .catch(() => {});
  }, [pType, resStatusFilter, resDateFilter]);

  // Fetch filtered cinema shows
  useEffect(() => {
    if (pType !== "CINEMA") return;
    const params = new URLSearchParams();
    if (showDateFilter) params.set("show_date", showDateFilter);
    apiRequest<MovieShowRecord[]>(
      `/partners/cinema/shows${params.toString() ? `?${params.toString()}` : ""}`
    )
      .then((res) => setFilteredShows(res || []))
      .catch(() => {});
  }, [pType, showDateFilter]);

  // Fetch event attendees
  useEffect(() => {
    if (pType !== "EVENT" || !selectedEventId) return;
    setLoadingAttendees(true);
    apiRequest<EventAttendeeRecord[]>(
      `/partners/events/${selectedEventId}/attendees`
    )
      .then((res) => setAttendees(res || []))
      .catch(() => setAttendees([]))
      .finally(() => setLoadingAttendees(false));
  }, [pType, selectedEventId]);

  // Fetch activity slots
  const fetchSlots = async () => {
    if (!selectedActivityId) return;
    setLoadingSlots(true);
    try {
      const params = new URLSearchParams();
      if (slotDateFilter) params.set("slot_date", slotDateFilter);
      const res = await apiRequest<ActivitySlotRecord[]>(
        `/partners/activities/${selectedActivityId}/slots${
          params.toString() ? `?${params.toString()}` : ""
        }`
      );
      setSlots(res || []);
    } catch {
      setSlots([]);
    } finally {
      setLoadingSlots(false);
    }
  };

  useEffect(() => {
    if ((pType === "SPORTS" || pType === "ACTIVITIES") && selectedActivityId) {
      fetchSlots();
    }
  }, [pType, selectedActivityId, slotDateFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleUpdateReservationStatus = async (id: number, status: string) => {
    try {
      await apiRequest(`/partners/restaurant/reservations/${id}/status`, {
        method: "PUT",
        body: JSON.stringify({ status }),
      });
      toast.success("Reservation updated", `Marked as ${status}`);
      await onReloadVertical();
    } catch (err: any) {
      toast.error("Failed to update reservation", err.message || "");
    }
  };

  const handleUpdateShowStatus = async (showId: number, status: string) => {
    try {
      await apiRequest(`/partners/cinema/shows/${showId}`, {
        method: "PUT",
        body: JSON.stringify({ status }),
      });
      toast.success("Show status updated", `Show #${showId} -> ${status}`);
      await onReloadVertical();
    } catch (err: any) {
      toast.error("Failed to update show", err.message || "");
    }
  };

  /* -------------------- Columns Definitions -------------------- */
  const resColumns: DataTableColumn<ReservationRecord>[] = [
    {
      key: "guest",
      header: "Guest & Contact",
      render: (r) => (
        <div>
          <div className="font-semibold text-primary">{r.customer_name}</div>
          <div className="text-[11px] text-muted">{r.customer_phone}</div>
        </div>
      ),
    },
    {
      key: "table",
      header: "Assigned Table",
      render: (r) => (
        <div>
          <span className="font-medium text-primary">
            Table {r.table_number}
          </span>
          <span className="block text-[11px] text-muted">
            {r.guest_count} Guests · {r.table_zone}
          </span>
        </div>
      ),
    },
    {
      key: "datetime",
      header: "Schedule",
      render: (r) => (
        <div className="font-mono text-xs text-secondary">
          <div>{r.reservation_date}</div>
          <div className="text-muted">{r.reservation_time}</div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: "actions",
      header: "Host Actions",
      align: "right",
      render: (r) => (
        <div className="flex items-center justify-end gap-1.5">
          {r.status === "CONFIRMED" && (
            <>
              <Button
                variant="console"
                size="xs"
                onClick={() => handleUpdateReservationStatus(r.id, "SEATED")}
              >
                Seat Guest
              </Button>
              <Button
                variant="secondary"
                size="xs"
                onClick={() => handleUpdateReservationStatus(r.id, "NO_SHOW")}
              >
                No-Show
              </Button>
              <Button
                variant="danger"
                size="xs"
                onClick={() =>
                  setConfirmState({
                    title: "Cancel Reservation",
                    description: `Cancel dining reservation for ${r.customer_name} (${r.reservation_date} ${r.reservation_time})?`,
                    confirmLabel: "Cancel Reservation",
                    onConfirm: async () => {
                      await handleUpdateReservationStatus(r.id, "CANCELLED");
                    },
                  })
                }
              >
                Cancel
              </Button>
            </>
          )}
        </div>
      ),
    },
  ];

  const attendeeColumns: DataTableColumn<EventAttendeeRecord>[] = [
    {
      key: "attendee",
      header: "Attendee",
      render: (a) => (
        <div>
          <div className="font-semibold text-primary">{a.attendee_name}</div>
          <div className="text-[11px] text-muted">{a.attendee_email}</div>
        </div>
      ),
    },
    {
      key: "ref",
      header: "Reference",
      render: (a) => (
        <span className="font-mono text-xs font-bold text-console-300">
          {a.booking_reference}
        </span>
      ),
    },
    {
      key: "tier",
      header: "Ticket Tier",
      render: (a) => (
        <span className="text-xs font-medium text-primary">
          {a.quantity}x {a.ticket_type}
        </span>
      ),
    },
    {
      key: "booked",
      header: "Purchased",
      render: (a) => (
        <span className="text-xs font-mono text-secondary">{a.booked_at}</span>
      ),
    },
    {
      key: "qr",
      header: "Gate Token",
      align: "right",
      render: (a) =>
        a.qr_token ? (
          <Button
            variant="ghost"
            size="xs"
            leftIcon={<Copy className="w-3 h-3" />}
            onClick={() => {
              navigator.clipboard?.writeText(a.qr_token || "");
              toast.info("QR token copied", a.booking_reference);
            }}
          >
            Copy Pass
          </Button>
        ) : (
          <span className="text-[11px] text-muted">—</span>
        ),
    },
  ];

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* RESTAURANT: Reservations */}
      {pType === "RESTAURANT" && (
        <div className="space-y-4">
          <div className="rounded-2xl bg-surface border border-subtle p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="font-display text-lg sm:text-xl font-bold text-primary">
                Dining Table Reservations
              </h2>
              <p className="text-xs text-muted mt-0.5">
                Track upcoming guests, confirm table seating, or mark no-shows.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2.5">
              <input
                type="date"
                aria-label="Filter by reservation date"
                value={resDateFilter}
                onChange={(e) => setResDateFilter(e.target.value)}
                className="h-9 px-3 rounded-lg bg-surface-2 border border-subtle text-xs text-primary focus:outline-none focus:border-console-500"
              />
              <FilterDropdown
                value={resStatusFilter}
                onChange={setResStatusFilter}
                placeholder="All Statuses"
                options={[
                  { label: "Confirmed", value: "CONFIRMED" },
                  { label: "Seated", value: "SEATED" },
                  { label: "No-Show", value: "NO_SHOW" },
                  { label: "Cancelled", value: "CANCELLED" },
                ]}
              />
              {(resDateFilter || resStatusFilter) && (
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => {
                    setResDateFilter("");
                    setResStatusFilter("");
                  }}
                >
                  Reset
                </Button>
              )}
            </div>
          </div>

          <DataTable
            columns={resColumns}
            data={filteredReservations}
            keyExtractor={(r) => r.id}
            emptyTitle="No dining reservations match this filter"
            emptyDescription="New table bookings will appear here automatically."
            renderMobileRow={(r) => (
              <div className="space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-semibold text-sm text-primary">
                      {r.customer_name}
                    </div>
                    <div className="text-xs text-secondary">
                      Table {r.table_number} ({r.guest_count} guests)
                    </div>
                  </div>
                  <StatusBadge status={r.status} />
                </div>
                <div className="text-xs font-mono text-muted">
                  {r.reservation_date} · {r.reservation_time}
                </div>
                {r.status === "CONFIRMED" && (
                  <div className="flex items-center gap-2 pt-1">
                    <Button
                      variant="console"
                      size="xs"
                      onClick={() =>
                        handleUpdateReservationStatus(r.id, "SEATED")
                      }
                    >
                      Seat Guest
                    </Button>
                    <Button
                      variant="secondary"
                      size="xs"
                      onClick={() =>
                        handleUpdateReservationStatus(r.id, "NO_SHOW")
                      }
                    >
                      No-Show
                    </Button>
                  </div>
                )}
              </div>
            )}
          />
        </div>
      )}

      {/* CINEMA: Showtimes Matrix */}
      {pType === "CINEMA" && (
        <div className="space-y-4">
          <div className="rounded-2xl bg-surface border border-subtle p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="font-display text-lg sm:text-xl font-bold text-primary">
                Cinema Showtimes &amp; Schedule Matrix
              </h2>
              <p className="text-xs text-muted mt-0.5">
                Control show availability (Scheduled, Housefull, Cancelled) or publish new screenings.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2.5">
              <input
                type="date"
                aria-label="Filter show date"
                value={showDateFilter}
                onChange={(e) => setShowDateFilter(e.target.value)}
                className="h-9 px-3 rounded-lg bg-surface-2 border border-subtle text-xs text-primary focus:outline-none focus:border-console-500"
              />
              {showDateFilter && (
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => setShowDateFilter("")}
                >
                  All Dates
                </Button>
              )}
              <Button
                variant="console"
                size="sm"
                leftIcon={<CalendarPlus className="w-4 h-4" />}
                onClick={() => setScheduleShowModalOpen(true)}
              >
                Schedule Show
              </Button>
            </div>
          </div>

          {filteredShows.length === 0 ? (
            <div className="rounded-2xl bg-surface border border-subtle p-10 text-center text-xs text-muted">
              No movie showtimes scheduled for this selection.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {filteredShows.map((sh) => (
                <div
                  key={sh.id}
                  className="rounded-2xl bg-surface border border-subtle p-5 space-y-4"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="font-display font-bold text-base text-primary truncate">
                        {sh.movie_title}
                      </h3>
                      <p className="text-xs text-secondary mt-0.5">
                        {sh.screen_name} ({sh.screen_type})
                      </p>
                    </div>
                    <StatusBadge status={sh.status} />
                  </div>

                  <div className="flex items-center justify-between text-xs font-mono text-secondary bg-surface-2/70 rounded-xl px-3 py-2 border border-subtle">
                    <span className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-muted" />
                      <span>{sh.show_date}</span>
                    </span>
                    <span className="flex items-center gap-1.5 text-primary font-semibold">
                      <Clock className="w-3.5 h-3.5 text-console-400" />
                      <span>
                        {sh.start_time} – {sh.end_time}
                      </span>
                    </span>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-1">
                    <select
                      aria-label={`Change status for ${sh.movie_title}`}
                      value={sh.status}
                      onChange={(e) =>
                        handleUpdateShowStatus(sh.id, e.target.value)
                      }
                      className="h-8 px-2.5 rounded-lg bg-surface-2 border border-subtle text-xs text-primary focus:outline-none focus:border-console-500"
                    >
                      <option value="SCHEDULED">SCHEDULED</option>
                      <option value="HOUSEFULL">HOUSEFULL</option>
                      <option value="COMPLETED">COMPLETED</option>
                      <option value="CANCELLED">CANCELLED</option>
                    </select>

                    <Button
                      variant="danger"
                      size="xs"
                      leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                      onClick={() =>
                        setConfirmState({
                          title: "Delete Showtime",
                          description: `Remove ${sh.movie_title} (${sh.show_date} ${sh.start_time}) on ${sh.screen_name}?`,
                          confirmLabel: "Delete Show",
                          onConfirm: async () => {
                            await apiRequest(`/partners/cinema/shows/${sh.id}`, {
                              method: "DELETE",
                            });
                            toast.success("Showtime deleted");
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

          <ScheduleShowModal
            isOpen={scheduleShowModalOpen}
            onClose={() => setScheduleShowModalOpen(false)}
            screens={screens}
            movies={movies}
            onSaved={onReloadVertical}
          />
        </div>
      )}

      {/* EVENT: Attendee Manifest */}
      {pType === "EVENT" && (
        <div className="space-y-4">
          <div className="rounded-2xl bg-surface border border-subtle p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <Users className="w-5 h-5 text-console-400" />
              <div>
                <h2 className="font-display text-lg sm:text-xl font-bold text-primary">
                  Event Attendee Manifest ({attendees.length})
                </h2>
                <p className="text-xs text-muted">
                  Confirmed ticket holders and gate pass codes per live event.
                </p>
              </div>
            </div>

            {events.length > 0 && (
              <Select
                fullWidth={false}
                containerClassName="w-full sm:w-72"
                aria-label="Select event"
                value={selectedEventId}
                onChange={(e) => setSelectedEventId(e.target.value)}
              >
                {events.map((ev) => (
                  <option key={ev.id} value={ev.id}>
                    {ev.title}
                  </option>
                ))}
              </Select>
            )}
          </div>

          <DataTable
            columns={attendeeColumns}
            data={attendees}
            keyExtractor={(a, idx) => `${a.booking_reference}-${idx}`}
            loading={loadingAttendees}
            emptyTitle="No confirmed attendees yet"
            emptyDescription="Ticket purchasers will appear here once payments capture."
            renderMobileRow={(a) => (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-sm text-primary">
                    {a.attendee_name}
                  </span>
                  <span className="font-mono text-xs text-console-300">
                    {a.booking_reference}
                  </span>
                </div>
                <div className="text-xs text-secondary">
                  {a.quantity}x {a.ticket_type} · {a.booked_at}
                </div>
              </div>
            )}
          />
        </div>
      )}

      {/* SPORTS & ACTIVITIES: Court / Activity Slot Scheduler */}
      {(pType === "SPORTS" || pType === "ACTIVITIES") && (
        <div className="space-y-4">
          <div className="rounded-2xl bg-surface border border-subtle p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <h2 className="font-display text-lg sm:text-xl font-bold text-primary">
                Court &amp; Batch Slot Inventory
              </h2>
              <p className="text-xs text-muted mt-0.5">
                Create hourly playing slots, override peak pricing, or toggle live availability.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              {activities.length > 0 && (
                <Select
                  fullWidth={false}
                  containerClassName="w-full sm:w-64"
                  aria-label="Select activity or court"
                  value={selectedActivityId}
                  onChange={(e) => setSelectedActivityId(e.target.value)}
                >
                  {activities.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.title}
                    </option>
                  ))}
                </Select>
              )}

              <input
                type="date"
                aria-label="Filter slot date"
                value={slotDateFilter}
                onChange={(e) => setSlotDateFilter(e.target.value)}
                className="h-10 px-3 rounded-lg bg-surface-2 border border-subtle text-xs text-primary focus:outline-none focus:border-console-500"
              />

              {slotDateFilter && (
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => setSlotDateFilter("")}
                >
                  All Dates
                </Button>
              )}

              {selectedActivityId && (
                <Button
                  variant="console"
                  size="sm"
                  leftIcon={<Plus className="w-4 h-4" />}
                  onClick={() => {
                    setEditingSlot(null);
                    setSlotModalOpen(true);
                  }}
                >
                  Add Slot
                </Button>
              )}
            </div>
          </div>

          {loadingSlots ? (
            <div className="rounded-2xl bg-surface border border-subtle p-10 text-center text-xs text-muted">
              Loading time slots...
            </div>
          ) : slots.length === 0 ? (
            <div className="rounded-2xl bg-surface border border-subtle p-10 text-center text-xs text-muted">
              No slots found for this selection. Click &ldquo;Add Slot&rdquo; to publish time inventory.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {slots.map((slot) => (
                <div
                  key={slot.id}
                  className="rounded-2xl bg-surface border border-subtle p-4 space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-mono text-xs text-muted">
                        {slot.slot_date}
                      </div>
                      <div className="font-display font-bold text-base text-primary mt-0.5">
                        {slot.start_time} – {slot.end_time}
                      </div>
                    </div>
                    <StatusBadge
                      status={slot.is_available ? "ACTIVE" : "DISABLED"}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs bg-surface-2/70 rounded-xl p-3 border border-subtle tabular-nums-lining">
                    <div>
                      <span className="text-muted block">Utilization</span>
                      <span className="font-bold text-primary">
                        {slot.booked_count} / {slot.capacity} booked
                      </span>
                    </div>
                    <div>
                      <span className="text-muted block">Slot Tariff</span>
                      <span className="font-bold text-emerald-300">
                        {formatRupees(slot.effective_price || 0)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-1">
                    <Button
                      variant="ghost"
                      size="xs"
                      leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                      onClick={async () => {
                        try {
                          await apiRequest(
                            `/partners/activities/slots/${slot.id}`,
                            {
                              method: "PUT",
                              body: JSON.stringify({
                                is_available: !slot.is_available,
                              }),
                            }
                          );
                          toast.success(
                            slot.is_available
                              ? "Slot paused"
                              : "Slot enabled"
                          );
                          await fetchSlots();
                        } catch (err: any) {
                          toast.error("Failed to toggle slot", err.message || "");
                        }
                      }}
                    >
                      {slot.is_available ? "Pause" : "Enable"}
                    </Button>

                    <div className="flex items-center gap-1">
                      <Button
                        variant="secondary"
                        size="xs"
                        leftIcon={<Edit3 className="w-3.5 h-3.5" />}
                        onClick={() => {
                          setEditingSlot(slot);
                          setSlotModalOpen(true);
                        }}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="danger"
                        size="xs"
                        disabled={slot.booked_count > 0}
                        title={
                          slot.booked_count > 0
                            ? "Slots with active bookings cannot be deleted"
                            : "Delete slot"
                        }
                        onClick={() =>
                          setConfirmState({
                            title: "Delete Slot",
                            description: `Delete time slot ${slot.slot_date} (${slot.start_time}–${slot.end_time})?`,
                            confirmLabel: "Delete Slot",
                            onConfirm: async () => {
                              await apiRequest(
                                `/partners/activities/slots/${slot.id}`,
                                { method: "DELETE" }
                              );
                              toast.success("Slot removed");
                              await fetchSlots();
                            },
                          })
                        }
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {selectedActivityId && (
            <ActivitySlotModal
              isOpen={slotModalOpen}
              onClose={() => setSlotModalOpen(false)}
              activityId={Number(selectedActivityId)}
              initialSlot={editingSlot}
              onSaved={fetchSlots}
            />
          )}
        </div>
      )}

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


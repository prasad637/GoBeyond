"use client";

import React, { useState } from "react";
import {
  Building2,
  CheckCircle2,
  ExternalLink,
  Eye,
  FileCheck2,
  Percent,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import {
  ConfirmationModal,
  DataTable,
  DataTableColumn,
  FilterDropdown,
  FormModal,
  StatusBadge,
  TableToolbar,
  useToast,
} from "@/components/dashboard";
import { formatRupees } from "@/lib/pricing";
import { AdminPartnerDetail, AdminPartnerItem } from "./adminTypes";

export function AdminPartnersView({
  partners,
  total,
  page,
  pageSize,
  loading,
  search,
  statusFilter,
  typeFilter,
  onSearchChange,
  onStatusChange,
  onTypeChange,
  onPageChange,
  onRefreshData,
}: {
  partners: AdminPartnerItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  search: string;
  statusFilter: string;
  typeFilter: string;
  onSearchChange: (val: string) => void;
  onStatusChange: (val: string) => void;
  onTypeChange: (val: string) => void;
  onPageChange: (nextPage: number) => void;
  onRefreshData: () => Promise<void>;
}) {
  const toast = useToast();

  // Deep Partner Inspection Modal
  const [inspectingPartner, setInspectingPartner] =
    useState<AdminPartnerDetail | null>(null);
  const [loadingInspect, setLoadingInspect] = useState(false);

  // Commission Modal
  const [commissionPartner, setCommissionPartner] =
    useState<AdminPartnerItem | null>(null);
  const [commissionRateInput, setCommissionRateInput] = useState("0.10");
  const [commissionNotes, setCommissionNotes] = useState("");
  const [savingCommission, setSavingCommission] = useState(false);
  const [commissionError, setCommissionError] = useState<string | null>(null);

  // Partner Status Confirmation Modal
  const [statusConfirm, setStatusConfirm] = useState<{
    partner: AdminPartnerItem;
    nextStatus: "APPROVED" | "REJECTED" | "SUSPENDED";
  } | null>(null);

  // KYC Doc Verification Confirmation Modal
  const [docVerifyConfirm, setDocVerifyConfirm] = useState<{
    partnerId: number;
    docId: number;
    docType: string;
    nextStatus: "VERIFIED" | "REJECTED";
  } | null>(null);

  const openPartnerInspect = async (partnerId: number) => {
    setLoadingInspect(true);
    try {
      const detail = await apiRequest<AdminPartnerDetail>(
        `/admin/partners/${partnerId}`
      );
      setInspectingPartner(detail);
    } catch (err: any) {
      toast.error("Unable to inspect partner", err.message || "");
    } finally {
      setLoadingInspect(false);
    }
  };

  const handleSaveCommission = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commissionPartner) return;
    const numeric = Number(commissionRateInput);
    if (!Number.isFinite(numeric) || numeric < 0 || numeric > 1) {
      setCommissionError("Enter a decimal take-rate between 0.00 and 1.00 (e.g. 0.125 for 12.5%).");
      return;
    }
    setSavingCommission(true);
    setCommissionError(null);
    try {
      await apiRequest(`/admin/partners/${commissionPartner.id}/commission`, {
        method: "PUT",
        body: JSON.stringify({
          commission_rate: numeric,
          notes: commissionNotes.trim() || "Super Admin commission adjustment",
        }),
      });
      toast.success(
        "Commission rate updated",
        `${commissionPartner.business_name} set to ${(numeric * 100).toFixed(2)}%`
      );
      setCommissionPartner(null);
      await onRefreshData();
      if (inspectingPartner?.id === commissionPartner.id) {
        await openPartnerInspect(commissionPartner.id);
      }
    } catch (err: any) {
      setCommissionError(err.message || "Failed to update commission.");
    } finally {
      setSavingCommission(false);
    }
  };

  const columns: DataTableColumn<AdminPartnerItem>[] = [
    {
      key: "business",
      header: "Partner Establishment",
      render: (p) => (
        <div>
          <div className="font-semibold text-primary">{p.business_name}</div>
          <div className="text-[11px] text-muted">
            {p.contact_email} · {p.contact_phone}
          </div>
        </div>
      ),
    },
    {
      key: "type",
      header: "Vertical",
      render: (p) => <StatusBadge status={p.partner_type} dot={false} />,
    },
    {
      key: "rate",
      header: "Take-Rate",
      render: (p) => (
        <span className="font-mono text-xs text-secondary tabular-nums-lining">
          {(p.commission_rate * 100).toFixed(2)}%
        </span>
      ),
    },
    {
      key: "kyc",
      header: "KYC Docs",
      render: (p) => (
        <span className="text-xs font-mono text-secondary tabular-nums-lining">
          {p.documents_count} file(s)
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (p) => <StatusBadge status={p.status} />,
    },
    {
      key: "actions",
      header: "Governance",
      align: "right",
      render: (p) => (
        <div
          className="flex items-center justify-end gap-1.5 flex-wrap"
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            variant="ghost"
            size="xs"
            leftIcon={<Eye className="w-3.5 h-3.5" />}
            onClick={() => openPartnerInspect(p.id)}
          >
            KYC
          </Button>
          <Button
            variant="secondary"
            size="xs"
            leftIcon={<Percent className="w-3.5 h-3.5" />}
            onClick={() => {
              setCommissionPartner(p);
              setCommissionRateInput(String(p.commission_rate));
              setCommissionNotes("");
              setCommissionError(null);
            }}
          >
            Fee
          </Button>
          {p.status !== "APPROVED" && (
            <Button
              variant="console"
              size="xs"
              onClick={() =>
                setStatusConfirm({ partner: p, nextStatus: "APPROVED" })
              }
            >
              Approve
            </Button>
          )}
          {p.status === "APPROVED" && (
            <Button
              variant="danger"
              size="xs"
              onClick={() =>
                setStatusConfirm({ partner: p, nextStatus: "SUSPENDED" })
              }
            >
              Suspend
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          {/* E2E expects h1:has-text("Partner Management") */}
          <h1 className="font-display text-xl sm:text-2xl font-bold text-primary">
            Partner Management
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Verify compliance KYC files, adjust partner commission rates, and enforce onboarding status.
          </p>
        </div>
        <span className="text-xs font-mono text-muted tabular-nums-lining">
          {total.toLocaleString("en-IN")} registered partners
        </span>
      </div>

      <TableToolbar
        searchValue={search}
        onSearchChange={onSearchChange}
        searchPlaceholder="Search business name, email, or phone..."
        filters={
          <>
            <FilterDropdown
              value={statusFilter}
              onChange={onStatusChange}
              placeholder="All Statuses"
              options={[
                { label: "Approved", value: "APPROVED" },
                { label: "Pending Approval", value: "PENDING_APPROVAL" },
                { label: "Pending Verification", value: "PENDING_VERIFICATION" },
                { label: "Rejected", value: "REJECTED" },
                { label: "Suspended", value: "SUSPENDED" },
              ]}
            />
            <FilterDropdown
              value={typeFilter}
              onChange={onTypeChange}
              placeholder="All Verticals"
              options={[
                { label: "Cinema", value: "CINEMA" },
                { label: "Restaurant", value: "RESTAURANT" },
                { label: "Event", value: "EVENT" },
                { label: "Sports", value: "SPORTS" },
                { label: "Activities", value: "ACTIVITIES" },
              ]}
            />
          </>
        }
      />

      <DataTable
        columns={columns}
        data={partners}
        keyExtractor={(p) => p.id}
        loading={loading || loadingInspect}
        onRowClick={(p) => openPartnerInspect(p.id)}
        emptyTitle="No matching partners"
        emptyDescription="Adjust the vertical or approval status filter."
        pagination={{ page, pageSize, total, onPageChange }}
        renderMobileRow={(p) => (
          <div className="space-y-2.5">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-semibold text-sm text-primary">
                  {p.business_name}
                </div>
                <div className="text-xs text-muted">{p.contact_email}</div>
              </div>
              <StatusBadge status={p.status} />
            </div>
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <StatusBadge status={p.partner_type} dot={false} />
                <span className="font-mono text-muted">
                  {(p.commission_rate * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    openPartnerInspect(p.id);
                  }}
                >
                  Inspect KYC
                </Button>
                {p.status !== "APPROVED" && (
                  <Button
                    variant="console"
                    size="xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      setStatusConfirm({ partner: p, nextStatus: "APPROVED" });
                    }}
                  >
                    Approve
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}
      />

      {/* Deep Partner & KYC Inspector Modal */}
      <Modal
        isOpen={Boolean(inspectingPartner)}
        onClose={() => setInspectingPartner(null)}
        size="xl"
        title={
          inspectingPartner
            ? inspectingPartner.business_name
            : "Partner Details"
        }
        description={
          inspectingPartner
            ? `${inspectingPartner.partner_type} · Registered ${
                inspectingPartner.created_at || ""
              }`
            : undefined
        }
      >
        {inspectingPartner && (
          <div className="space-y-6 text-xs sm:text-sm">
            {/* Header Status & Financial Attribution */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="rounded-xl bg-surface-2 border border-subtle p-3.5">
                <span className="text-[11px] text-muted block">Status</span>
                <div className="mt-1.5">
                  <StatusBadge status={inspectingPartner.status} />
                </div>
              </div>
              <div className="rounded-xl bg-surface-2 border border-subtle p-3.5">
                <span className="text-[11px] text-muted block">
                  Commission Take-Rate
                </span>
                <strong className="font-display text-lg text-console-300 block mt-0.5 tabular-nums-lining">
                  {(inspectingPartner.commission_rate * 100).toFixed(2)}%
                </strong>
              </div>
              <div className="rounded-xl bg-surface-2 border border-subtle p-3.5">
                <span className="text-[11px] text-muted block">
                  Isolated Gross Sales
                </span>
                <strong className="font-display text-lg text-primary block mt-0.5 tabular-nums-lining">
                  {formatRupees(inspectingPartner.gross_booking_value, {
                    decimals: 2,
                  })}
                </strong>
              </div>
              <div className="rounded-xl bg-surface-2 border border-subtle p-3.5">
                <span className="text-[11px] text-muted block">
                  Partner Payout Due
                </span>
                <strong className="font-display text-lg text-emerald-300 block mt-0.5 tabular-nums-lining">
                  {formatRupees(inspectingPartner.partner_payout, {
                    decimals: 2,
                  })}
                </strong>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 rounded-xl bg-surface-2/60 border border-subtle p-4 text-xs">
              <div className="space-y-1">
                <span className="text-muted block">Contact &amp; Ownership</span>
                <div className="font-semibold text-primary">
                  {inspectingPartner.contact_email}
                </div>
                <div className="text-secondary">
                  {inspectingPartner.contact_phone} · {inspectingPartner.total_listings} listings ·{" "}
                  {inspectingPartner.total_bookings} bookings
                </div>
              </div>
              <div className="space-y-1">
                <span className="text-muted block">Tax Identifiers</span>
                <div className="font-mono text-primary">
                  GSTIN: {inspectingPartner.gstin || "Not provided"}
                </div>
                <div className="font-mono text-secondary">
                  PAN: {inspectingPartner.pan_number || "Not provided"}
                </div>
              </div>
            </div>

            {/* Governance Actions */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-subtle">
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  variant="secondary"
                  size="sm"
                  leftIcon={<Percent className="w-4 h-4" />}
                  onClick={() => {
                    setCommissionPartner(inspectingPartner);
                    setCommissionRateInput(
                      String(inspectingPartner.commission_rate)
                    );
                    setCommissionNotes("");
                    setCommissionError(null);
                  }}
                >
                  Adjust Commission
                </Button>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                {inspectingPartner.status !== "APPROVED" && (
                  <Button
                    variant="console"
                    size="sm"
                    leftIcon={<CheckCircle2 className="w-4 h-4" />}
                    onClick={() =>
                      setStatusConfirm({
                        partner: {
                          ...inspectingPartner,
                          documents_count: inspectingPartner.documents.length,
                        },
                        nextStatus: "APPROVED",
                      })
                    }
                  >
                    Approve Partner
                  </Button>
                )}
                {inspectingPartner.status !== "REJECTED" &&
                  inspectingPartner.status !== "APPROVED" && (
                    <Button
                      variant="danger"
                      size="sm"
                      leftIcon={<XCircle className="w-4 h-4" />}
                      onClick={() =>
                        setStatusConfirm({
                          partner: {
                            ...inspectingPartner,
                            documents_count: inspectingPartner.documents.length,
                          },
                          nextStatus: "REJECTED",
                        })
                      }
                    >
                      Reject
                    </Button>
                  )}
                {inspectingPartner.status !== "SUSPENDED" && (
                  <Button
                    variant="danger"
                    size="sm"
                    leftIcon={<ShieldAlert className="w-4 h-4" />}
                    onClick={() =>
                      setStatusConfirm({
                        partner: {
                          ...inspectingPartner,
                          documents_count: inspectingPartner.documents.length,
                        },
                        nextStatus: "SUSPENDED",
                      })
                    }
                  >
                    Suspend Partner
                  </Button>
                )}
              </div>
            </div>

            {/* KYC Documents Verification List */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-2">
                <FileCheck2 className="w-4 h-4 text-console-400" />
                <span>
                  Submitted KYC &amp; Compliance Documents (
                  {inspectingPartner.documents.length})
                </span>
              </h4>

              {inspectingPartner.documents.length === 0 ? (
                <div className="rounded-xl border border-dashed border-subtle p-6 text-center text-xs text-muted">
                  No KYC documents uploaded by this partner yet.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {inspectingPartner.documents.map((doc) => {
                    const isImage = /\.(png|jpe?g|webp)$/i.test(
                      doc.document_url
                    );
                    const href = doc.document_url.startsWith("http")
                      ? doc.document_url
                      : doc.document_url;
                    return (
                      <div
                        key={doc.id}
                        className="rounded-xl bg-surface-2 border border-subtle p-3.5 space-y-2"
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <Building2 className="w-3.5 h-3.5 text-console-400 shrink-0" />
                              <span className="font-bold text-primary">
                                {doc.document_type}
                              </span>
                              <StatusBadge status={doc.status} />
                            </div>
                            <a
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-[11px] font-mono text-console-300 hover:text-console-200 mt-1 break-all"
                            >
                              <span>{doc.document_url}</span>
                              <ExternalLink className="w-3 h-3 shrink-0" />
                            </a>
                          </div>

                          <div className="flex items-center gap-1.5 shrink-0">
                            {doc.status !== "VERIFIED" && (
                              <Button
                                variant="console"
                                size="xs"
                                onClick={() =>
                                  setDocVerifyConfirm({
                                    partnerId: inspectingPartner.id,
                                    docId: doc.id,
                                    docType: doc.document_type,
                                    nextStatus: "VERIFIED",
                                  })
                                }
                              >
                                Verify
                              </Button>
                            )}
                            {doc.status !== "REJECTED" && (
                              <Button
                                variant="danger"
                                size="xs"
                                onClick={() =>
                                  setDocVerifyConfirm({
                                    partnerId: inspectingPartner.id,
                                    docId: doc.id,
                                    docType: doc.document_type,
                                    nextStatus: "REJECTED",
                                  })
                                }
                              >
                                Reject
                              </Button>
                            )}
                          </div>
                        </div>

                        {isImage && doc.document_url.startsWith("http") && (
                          <img
                            src={doc.document_url}
                            alt={`${doc.document_type} preview`}
                            className="max-h-40 rounded-lg border border-subtle object-contain bg-black/30"
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* Commission Rate Modal */}
      <FormModal
        isOpen={Boolean(commissionPartner)}
        onClose={() => setCommissionPartner(null)}
        onSubmit={handleSaveCommission}
        title={
          commissionPartner
            ? `Adjust Commission Rate — ${commissionPartner.business_name}`
            : "Adjust Commission"
        }
        description="Stored with exact Numeric(5,4) precision and audited before/after."
        submitLabel="Update Commission"
        loading={savingCommission}
        error={commissionError}
      >
        <Input
          label="Commission Take-Rate Decimal (e.g. 0.1250 = 12.50%)"
          type="number"
          step="0.0001"
          min="0"
          max="1"
          required
          value={commissionRateInput}
          onChange={(e) => setCommissionRateInput(e.target.value)}
          hint={`Equivalent platform fee: ${(
            (Number(commissionRateInput) || 0) * 100
          ).toFixed(2)}%`}
        />
        <Input
          label="Contract Adjustment Notes"
          placeholder="Quarterly enterprise volume agreement..."
          value={commissionNotes}
          onChange={(e) => setCommissionNotes(e.target.value)}
        />
      </FormModal>

      {/* Partner Status Transition Confirmation Modal */}
      <ConfirmationModal
        isOpen={Boolean(statusConfirm)}
        onClose={() => setStatusConfirm(null)}
        title={
          statusConfirm
            ? `${statusConfirm.nextStatus} — ${statusConfirm.partner.business_name}`
            : ""
        }
        description={
          statusConfirm
            ? `Transition partner account #${statusConfirm.partner.id} from ${statusConfirm.partner.status} to ${statusConfirm.nextStatus}? This triggers outbox notification and immutable audit logging.`
            : ""
        }
        confirmLabel={
          statusConfirm?.nextStatus === "APPROVED"
            ? "Approve Partner"
            : `Confirm ${statusConfirm?.nextStatus || ""}`
        }
        variant={statusConfirm?.nextStatus === "APPROVED" ? "console" : "danger"}
        requireNotes={statusConfirm?.nextStatus !== "APPROVED"}
        showNotesInput
        onConfirm={async (notes) => {
          if (!statusConfirm) return;
          await apiRequest(
            `/admin/partners/${statusConfirm.partner.id}/status`,
            {
              method: "PUT",
              body: JSON.stringify({
                status: statusConfirm.nextStatus,
                notes: notes || undefined,
              }),
            }
          );
          toast.success(
            "Partner status updated",
            `${statusConfirm.partner.business_name} -> ${statusConfirm.nextStatus}`
          );
          const pid = statusConfirm.partner.id;
          setStatusConfirm(null);
          await onRefreshData();
          if (inspectingPartner?.id === pid) {
            await openPartnerInspect(pid);
          }
        }}
      />

      {/* Document Verify/Reject Confirmation Modal */}
      <ConfirmationModal
        isOpen={Boolean(docVerifyConfirm)}
        onClose={() => setDocVerifyConfirm(null)}
        title={
          docVerifyConfirm
            ? `${docVerifyConfirm.nextStatus} KYC Document (${docVerifyConfirm.docType})`
            : ""
        }
        description="Record compliance decision for this partner document in the audit log."
        confirmLabel={
          docVerifyConfirm?.nextStatus === "VERIFIED"
            ? "Mark Verified"
            : "Reject Document"
        }
        variant={docVerifyConfirm?.nextStatus === "VERIFIED" ? "console" : "danger"}
        requireNotes={docVerifyConfirm?.nextStatus === "REJECTED"}
        showNotesInput
        onConfirm={async (notes) => {
          if (!docVerifyConfirm) return;
          await apiRequest(
            `/admin/partners/${docVerifyConfirm.partnerId}/documents/${docVerifyConfirm.docId}`,
            {
              method: "PUT",
              body: JSON.stringify({
                status: docVerifyConfirm.nextStatus,
                notes: notes || undefined,
              }),
            }
          );
          toast.success(
            "KYC document updated",
            `${docVerifyConfirm.docType} -> ${docVerifyConfirm.nextStatus}`
          );
          const pid = docVerifyConfirm.partnerId;
          setDocVerifyConfirm(null);
          await openPartnerInspect(pid);
          await onRefreshData();
        }}
      />
    </div>
  );
}


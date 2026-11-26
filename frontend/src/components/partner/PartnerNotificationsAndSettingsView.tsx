"use client";

import React, { useEffect, useState } from "react";
import {
  Bell,
  Building2,
  CheckCheck,
  FileCheck2,
  FileUp,
  Landmark,
  Link2,
  Lock,
  Upload,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Input";
import { StatusBadge, useToast } from "@/components/dashboard";
import {
  PartnerDocument,
  PartnerNotificationRecord,
  PartnerProfile,
  uploadPartnerKycFile,
} from "./partnerTypes";

export function PartnerNotificationsView({
  notifications,
  onMarkOneRead,
  onMarkAllRead,
}: {
  notifications: PartnerNotificationRecord[];
  onMarkOneRead: (id: number | string) => Promise<void>;
  onMarkAllRead: () => Promise<void>;
}) {
  const [filter, setFilter] = useState<"ALL" | "UNREAD">("ALL");
  const visible = notifications.filter((n) =>
    filter === "UNREAD" ? !n.is_read : true
  );
  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl sm:text-2xl font-bold text-primary flex items-center gap-2">
            <Bell className="w-5 h-5 text-console-400" />
            <span>Partner Notification Centre</span>
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Real-time booking alerts, compliance notices, and commission contract updates.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-lg bg-surface-2 border border-subtle p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setFilter("ALL")}
              className={`px-3 py-1.5 rounded-md font-medium ${
                filter === "ALL"
                  ? "bg-console-600 text-white"
                  : "text-secondary hover:text-primary"
              }`}
            >
              All ({notifications.length})
            </button>
            <button
              type="button"
              onClick={() => setFilter("UNREAD")}
              className={`px-3 py-1.5 rounded-md font-medium ${
                filter === "UNREAD"
                  ? "bg-console-600 text-white"
                  : "text-secondary hover:text-primary"
              }`}
            >
              Unread ({unreadCount})
            </button>
          </div>

          {unreadCount > 0 && (
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<CheckCheck className="w-4 h-4" />}
              onClick={onMarkAllRead}
            >
              Mark All Read
            </Button>
          )}
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="rounded-2xl bg-surface border border-subtle p-10 text-center text-xs text-muted">
          {filter === "UNREAD"
            ? "You are completely caught up — zero unread notifications."
            : "No notifications received yet."}
        </div>
      ) : (
        <div className="rounded-2xl bg-surface border border-subtle divide-y divide-subtle overflow-hidden">
          {visible.map((n) => (
            <div
              key={n.id}
              onClick={() => {
                if (!n.is_read) onMarkOneRead(n.id);
              }}
              className={`p-4 sm:p-5 flex flex-col sm:flex-row sm:items-start justify-between gap-3 transition-colors ${
                !n.is_read
                  ? "bg-console-500/8 hover:bg-console-500/12 cursor-pointer"
                  : "hover:bg-surface-2/50"
              }`}
            >
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  {!n.is_read && (
                    <span className="w-2 h-2 rounded-full bg-brand-500 shrink-0" />
                  )}
                  <h3 className="text-sm font-bold text-primary">{n.title}</h3>
                  <StatusBadge status={n.type || "ALERT"} dot={false} />
                </div>
                <p className="text-xs sm:text-sm text-secondary leading-relaxed">
                  {n.message}
                </p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-[11px] font-mono text-muted">
                  {n.created_at ? n.created_at.slice(0, 16).replace("T", " ") : ""}
                </span>
                {!n.is_read && (
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      onMarkOneRead(n.id);
                    }}
                  >
                    Mark Read
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function PartnerSettingsView({
  partnerProfile,
  documents,
  onReloadProfile,
}: {
  partnerProfile: PartnerProfile;
  documents: PartnerDocument[];
  onReloadProfile: () => Promise<void>;
}) {
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [profileForm, setProfileForm] = useState({
    business_name: partnerProfile.business_name || "",
    contact_email: partnerProfile.contact_email || "",
    contact_phone: partnerProfile.contact_phone || "",
    gstin: partnerProfile.gstin || "",
    pan_number: partnerProfile.pan_number || "",
    bank_name: "",
    account_holder_name: "",
    bank_account_number: "",
    bank_ifsc: "",
  });

  const [uploadMode, setUploadMode] = useState<"file" | "url">("file");
  const [docType, setDocType] = useState("GST");
  const [docUrl, setDocUrl] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    setProfileForm((prev) => ({
      ...prev,
      business_name: partnerProfile.business_name || "",
      contact_email: partnerProfile.contact_email || "",
      contact_phone: partnerProfile.contact_phone || "",
      gstin: partnerProfile.gstin || "",
      pan_number: partnerProfile.pan_number || "",
    }));
  }, [partnerProfile]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload: Record<string, string | undefined> = {
        business_name: profileForm.business_name.trim(),
        contact_email: profileForm.contact_email.trim(),
        contact_phone: profileForm.contact_phone.trim(),
        gstin: profileForm.gstin.trim() || undefined,
        pan_number: profileForm.pan_number.trim() || undefined,
      };
      if (profileForm.bank_name.trim()) {
        payload.bank_name = profileForm.bank_name.trim();
      }
      if (profileForm.account_holder_name.trim()) {
        payload.account_holder_name = profileForm.account_holder_name.trim();
      }
      if (profileForm.bank_account_number.trim()) {
        payload.bank_account_number = profileForm.bank_account_number.trim();
      }
      if (profileForm.bank_ifsc.trim()) {
        payload.bank_ifsc = profileForm.bank_ifsc.trim().toUpperCase();
      }

      await apiRequest("/partners/profile", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      toast.success(
        "Partner profile saved",
        "Business details & masked payout audit record updated."
      );
      setProfileForm((prev) => ({
        ...prev,
        bank_name: "",
        account_holder_name: "",
        bank_account_number: "",
        bank_ifsc: "",
      }));
      await onReloadProfile();
    } catch (err: any) {
      toast.error("Failed to save settings", err.message || "");
    } finally {
      setSaving(false);
    }
  };

  const handleUploadDoc = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploading(true);
    try {
      if (uploadMode === "file") {
        if (!selectedFile) {
          toast.error("Select a KYC document file first");
          setUploading(false);
          return;
        }
        await uploadPartnerKycFile(selectedFile, docType);
        setSelectedFile(null);
        toast.success("KYC file uploaded", `${docType} validated cleanly.`);
      } else {
        if (!docUrl.trim()) {
          toast.error("Enter a valid document URL");
          setUploading(false);
          return;
        }
        await apiRequest("/partners/documents", {
          method: "POST",
          body: JSON.stringify({
            document_type: docType,
            document_url: docUrl.trim(),
          }),
        });
        setDocUrl("");
        toast.success("KYC link submitted", `${docType} queued for review.`);
      }
      await onReloadProfile();
    } catch (err: any) {
      toast.error("KYC upload failed", err.message || "");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="font-display text-xl sm:text-2xl font-bold text-primary">
          Business Profile, Payout Audit &amp; KYC
        </h1>
        <p className="text-xs text-muted mt-0.5">
          Manage legal establishment details, log masked bank payout instructions, and inspect verified KYC documents.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <form
          onSubmit={handleSaveProfile}
          className="xl:col-span-2 rounded-2xl bg-surface border border-subtle p-6 space-y-6"
        >
          <div className="flex items-center justify-between gap-2 pb-3 border-b border-subtle">
            <div className="flex items-center gap-2">
              <Building2 className="w-5 h-5 text-console-400" />
              <h2 className="font-display text-base font-bold text-primary">
                Establishment Legal Information
              </h2>
            </div>
            <StatusBadge status={partnerProfile.status} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Legal Business Name"
              required
              value={profileForm.business_name}
              onChange={(e) =>
                setProfileForm({ ...profileForm, business_name: e.target.value })
              }
            />
            <Input
              label="Registered Contact Email"
              type="email"
              required
              value={profileForm.contact_email}
              onChange={(e) =>
                setProfileForm({ ...profileForm, contact_email: e.target.value })
              }
            />
            <Input
              label="Contact Phone"
              required
              value={profileForm.contact_phone}
              onChange={(e) =>
                setProfileForm({ ...profileForm, contact_phone: e.target.value })
              }
            />
            <Input
              label="GSTIN"
              value={profileForm.gstin}
              onChange={(e) =>
                setProfileForm({ ...profileForm, gstin: e.target.value })
              }
            />
            <Input
              label="PAN Number"
              value={profileForm.pan_number}
              onChange={(e) =>
                setProfileForm({ ...profileForm, pan_number: e.target.value })
              }
            />
          </div>

          <div className="pt-4 border-t border-subtle space-y-4">
            <div className="flex items-center gap-2">
              <Landmark className="w-4 h-4 text-emerald-400" />
              <h3 className="font-display text-sm font-bold text-primary">
                Payout Bank Instruction Update (Audit Logged &amp; Masked)
              </h3>
            </div>
            <p className="text-xs text-muted leading-relaxed">
              For security compliance, full bank account numbers are never returned to the browser. Submit fields below only when updating settlement bank instructions; they are masked and written directly to the immutable audit trail.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Bank Name"
                placeholder="e.g. HDFC Bank"
                value={profileForm.bank_name}
                onChange={(e) =>
                  setProfileForm({ ...profileForm, bank_name: e.target.value })
                }
              />
              <Input
                label="Account Holder Name"
                placeholder="Legal account title"
                value={profileForm.account_holder_name}
                onChange={(e) =>
                  setProfileForm({
                    ...profileForm,
                    account_holder_name: e.target.value,
                  })
                }
              />
              <Input
                label="Account Number"
                placeholder="Will be masked ****XXXX on save"
                value={profileForm.bank_account_number}
                onChange={(e) =>
                  setProfileForm({
                    ...profileForm,
                    bank_account_number: e.target.value,
                  })
                }
              />
              <Input
                label="IFSC Code"
                placeholder="e.g. HDFC0000123"
                value={profileForm.bank_ifsc}
                onChange={(e) =>
                  setProfileForm({ ...profileForm, bank_ifsc: e.target.value })
                }
              />
            </div>
          </div>

          <div className="pt-2 flex justify-end">
            <Button type="submit" variant="console" isLoading={saving}>
              Save Profile Settings
            </Button>
          </div>
        </form>

        <div className="space-y-6">
          {/* Read-only Contract Commission Card */}
          <div className="rounded-2xl bg-surface border border-subtle p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-muted">
                Platform Commission
              </span>
              <Lock className="w-4 h-4 text-console-400" />
            </div>
            <div className="font-display text-3xl font-bold text-primary tabular-nums-lining">
              {(partnerProfile.commission_rate * 100).toFixed(2)}%
            </div>
            <p className="text-xs text-secondary leading-relaxed">
              Contract take-rate applied per captured booking. Read-only for partners; managed exclusively by GO BEYOND Super Admin.
            </p>
          </div>

          {/* KYC Upload & Document Ledger */}
          <div className="rounded-2xl bg-surface border border-subtle p-5 space-y-4">
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-display text-sm font-bold text-primary flex items-center gap-2">
                <FileCheck2 className="w-4 h-4 text-console-400" />
                <span>Compliance KYC Vault</span>
              </h3>
              <div className="inline-flex rounded-lg bg-surface-2 border border-subtle p-0.5 text-[11px]">
                <button
                  type="button"
                  onClick={() => setUploadMode("file")}
                  className={`px-2 py-1 rounded ${
                    uploadMode === "file" ? "bg-console-600 text-white" : "text-secondary"
                  }`}
                >
                  File
                </button>
                <button
                  type="button"
                  onClick={() => setUploadMode("url")}
                  className={`px-2 py-1 rounded ${
                    uploadMode === "url" ? "bg-console-600 text-white" : "text-secondary"
                  }`}
                >
                  URL
                </button>
              </div>
            </div>

            <form onSubmit={handleUploadDoc} className="space-y-3">
              <Select
                label="Document Type"
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
              >
                <option value="GST">GST Certificate</option>
                <option value="PAN">Business PAN</option>
                <option value="FSSAI">FSSAI License</option>
                <option value="TRADE_LICENSE">Trade License</option>
                <option value="ID_PROOF">ID Proof</option>
              </Select>

              {uploadMode === "file" ? (
                <label className="flex flex-col items-center justify-center rounded-xl border border-dashed border-strong bg-surface-2/60 p-4 cursor-pointer text-center hover:bg-surface-2 transition-colors">
                  <Upload className="w-5 h-5 text-console-400 mb-1.5" />
                  <span className="text-xs font-medium text-primary truncate max-w-full">
                    {selectedFile ? selectedFile.name : "Choose PDF / JPG / PNG"}
                  </span>
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    className="sr-only"
                    onChange={(e) =>
                      setSelectedFile(e.target.files?.[0] || null)
                    }
                  />
                </label>
              ) : (
                <Input
                  placeholder="https://docs.gobeyond.in/..."
                  leftIcon={<Link2 className="w-3.5 h-3.5" />}
                  value={docUrl}
                  onChange={(e) => setDocUrl(e.target.value)}
                />
              )}

              <Button
                type="submit"
                variant="secondary"
                size="sm"
                fullWidth
                leftIcon={<FileUp className="w-4 h-4" />}
                isLoading={uploading}
              >
                Submit Document
              </Button>
            </form>

            <div className="space-y-2 pt-2 border-t border-subtle max-h-56 overflow-y-auto">
              {documents.length === 0 ? (
                <p className="text-xs text-muted text-center py-3">
                  No documents archived yet.
                </p>
              ) : (
                documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="rounded-lg bg-surface-2 border border-subtle px-3 py-2 flex items-center justify-between gap-2 text-xs"
                  >
                    <div className="min-w-0">
                      <div className="font-semibold text-primary">
                        {doc.document_type}
                      </div>
                      <div className="text-[10px] font-mono text-muted truncate">
                        {doc.document_url}
                      </div>
                    </div>
                    <StatusBadge status={doc.status} />
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


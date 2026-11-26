"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Clock,
  FileUp,
  Link2,
  ShieldAlert,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Input";
import {
  StatusBadge,
  useToast,
} from "@/components/dashboard";
import {
  PartnerDocument,
  PartnerProfile,
  uploadPartnerKycFile,
} from "./partnerTypes";

export function PartnerUnauthenticatedGate({
  onGoToLogin,
}: {
  onGoToLogin: () => void;
}) {
  return (
    <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center p-4">
      <div className="max-w-md w-full rounded-2xl bg-surface border border-subtle p-7 sm:p-8 text-center shadow-modal space-y-6">
        <div className="w-16 h-16 rounded-2xl bg-console-500/12 border border-console-500/30 flex items-center justify-center mx-auto text-console-300 shadow-console-sm">
          <Building2 className="w-8 h-8" />
        </div>

        <div className="space-y-2">
          <span className="inline-block px-2.5 py-0.5 rounded-full bg-console-500/12 border border-console-500/25 text-console-300 text-[11px] font-semibold uppercase tracking-wider">
            Merchant &amp; Venue Console
          </span>
          {/* E2E expects h2:has-text("Partner Portal") */}
          <h2 className="font-display text-2xl font-bold tracking-tight text-primary">
            Partner Portal
          </h2>
          <p className="text-sm text-secondary leading-relaxed">
            Sign in with your venue partner or organizer credentials to manage
            listings, bookings, gate QR admission, and settlement ledgers.
          </p>
        </div>

        {/* E2E expects button:has-text("Sign In to Business Console") */}
        <Button
          variant="console"
          size="lg"
          fullWidth
          onClick={onGoToLogin}
        >
          Sign In to Business Console
        </Button>

        <p className="text-[11px] text-muted">
          Isolated single-tenant workspace · Powered by Nocturne Console
        </p>
      </div>
    </div>
  );
}

const ONBOARDING_STEPS = [
  { id: 1, title: "Register Business", desc: "Submit establishment & GST/PAN profile" },
  { id: 2, title: "Upload KYC", desc: "Attach GST, PAN, FSSAI or Trade License" },
  { id: 3, title: "Admin Review", desc: "Compliance audit by GO BEYOND team" },
  { id: 4, title: "Console Unlocked", desc: "Publish catalog & settle bookings" },
];

export function PartnerOnboardingRegistration({
  userEmail,
  userPhone,
  onSuccess,
}: {
  userEmail?: string;
  userPhone?: string;
  onSuccess: () => Promise<void>;
}) {
  const toast = useToast();
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    business_name: "",
    partner_type: "RESTAURANT",
    contact_email: userEmail || "",
    contact_phone: userPhone || "",
    gstin: "",
    pan_number: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await apiRequest("/partners/register", {
        method: "POST",
        body: JSON.stringify(form),
      });
      toast.success(
        "Partner application submitted",
        "Proceed to upload KYC verification documents."
      );
      await onSuccess();
    } catch (err: any) {
      toast.error("Registration failed", err.message || "Unable to submit application.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-4 sm:py-6 space-y-6">
      <div className="rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-5">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-console-300">
            Step 1 of 4 · Business Onboarding
          </span>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-primary mt-1">
            Apply for a GO BEYOND Partner Account
          </h1>
          <p className="text-sm text-secondary mt-1">
            List cinemas, restaurants, concerts, sports arenas, or recreational activities on Hyderabad&apos;s flagship discovery platform.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          {ONBOARDING_STEPS.map((step) => (
            <div
              key={step.id}
              className={`rounded-xl border p-3 ${
                step.id === 1
                  ? "bg-console-500/12 border-console-500/35"
                  : "bg-surface-2/60 border-subtle"
              }`}
            >
              <div className="text-[11px] font-bold text-console-300">
                0{step.id}. {step.title}
              </div>
              <div className="text-[11px] text-muted mt-1 leading-snug">
                {step.desc}
              </div>
            </div>
          ))}
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        className="rounded-2xl bg-surface border border-subtle p-6 sm:p-7 space-y-5 shadow-surface"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Business / Venue Name"
            required
            placeholder="e.g. Minerva Fine Dine / IMAX Screen"
            value={form.business_name}
            onChange={(e) => setForm({ ...form, business_name: e.target.value })}
          />
          <Select
            label="Business Vertical"
            value={form.partner_type}
            onChange={(e) => setForm({ ...form, partner_type: e.target.value })}
          >
            <option value="RESTAURANT">Dining &amp; Restaurant</option>
            <option value="CINEMA">Cinema / Multiplex</option>
            <option value="EVENT">Live Events &amp; Concerts</option>
            <option value="SPORTS">Sports Venue &amp; Turfs</option>
            <option value="ACTIVITIES">Experiences &amp; Activities</option>
          </Select>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Business Contact Email"
            type="email"
            required
            value={form.contact_email}
            onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
          />
          <Input
            label="Business Contact Phone"
            required
            value={form.contact_phone}
            onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="GSTIN (Optional)"
            placeholder="36AAAAA0000A1Z5"
            value={form.gstin}
            onChange={(e) => setForm({ ...form, gstin: e.target.value })}
          />
          <Input
            label="PAN Number (Optional)"
            placeholder="ABCDE1234F"
            value={form.pan_number}
            onChange={(e) => setForm({ ...form, pan_number: e.target.value })}
          />
        </div>

        <div className="pt-2 flex justify-end">
          <Button type="submit" variant="console" size="lg" isLoading={submitting}>
            Submit Onboarding Application
          </Button>
        </div>
      </form>
    </div>
  );
}

export function PartnerStatusGateView({
  partnerProfile,
  documents,
  onDocumentsUpdated,
}: {
  partnerProfile: PartnerProfile;
  documents: PartnerDocument[];
  onDocumentsUpdated: () => Promise<void>;
}) {
  const toast = useToast();
  const [uploadMode, setUploadMode] = useState<"file" | "url">("file");
  const [docType, setDocType] = useState("GST");
  const [docUrl, setDocUrl] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const statusUpper = partnerProfile.status.toUpperCase();
  const isRejectedOrSuspended =
    statusUpper === "REJECTED" || statusUpper === "SUSPENDED";
  const isSuspended = statusUpper === "SUSPENDED";

  const handleSubmitKyc = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploading(true);
    try {
      if (uploadMode === "file") {
        if (!selectedFile) {
          toast.error("Select a document file", "Supported: PDF, JPG, JPEG, PNG (max 5 MB).");
          setUploading(false);
          return;
        }
        await uploadPartnerKycFile(selectedFile, docType);
        setSelectedFile(null);
        toast.success("KYC document uploaded", `${docType} file validated cleanly.`);
      } else {
        if (!docUrl.trim()) {
          toast.error("Enter a document URL");
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
        toast.success("KYC link submitted", `${docType} reference queued for verification.`);
      }
      await onDocumentsUpdated();
    } catch (err: any) {
      toast.error("Document upload failed", err.message || "Unable to upload KYC record.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-4 sm:py-6 space-y-6">
      <div
        className={`rounded-2xl border p-6 sm:p-7 space-y-4 ${
          isRejectedOrSuspended
            ? "bg-red-500/8 border-red-500/30"
            : "bg-surface border-subtle"
        }`}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div
              className={`w-12 h-12 rounded-2xl border flex items-center justify-center shrink-0 ${
                isRejectedOrSuspended
                  ? "bg-red-500/15 border-red-500/35 text-red-400"
                  : "bg-amber-500/15 border-amber-500/35 text-amber-300"
              }`}
            >
              {isRejectedOrSuspended ? (
                <ShieldAlert className="w-6 h-6" />
              ) : (
                <Clock className="w-6 h-6" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="font-display text-xl sm:text-2xl font-bold text-primary">
                  {partnerProfile.business_name}
                </h1>
                <StatusBadge status={partnerProfile.status} />
                <StatusBadge status={partnerProfile.partner_type} dot={false} />
              </div>
              <p className="text-sm text-secondary mt-1.5 leading-relaxed">
                {isSuspended
                  ? "This partner establishment is currently suspended by platform compliance. Live bookings and catalog mutations are paused. Contact partner-support@gobeyond.in for account review."
                  : statusUpper === "REJECTED"
                  ? "Your previous onboarding application was rejected during KYC verification. You may submit corrected GST/PAN/License documents below to request re-verification."
                  : "Your partner application is under Super Admin compliance review. Upload your required KYC documents below to expedite verification."}
              </p>
            </div>
          </div>
        </div>

        {/* 4-step Onboarding Stepper */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-2">
          {ONBOARDING_STEPS.map((step) => {
            const done =
              step.id === 1 || (step.id === 2 && documents.length > 0);
            const active =
              (!done && step.id === 2) ||
              (documents.length > 0 && step.id === 3 && !isRejectedOrSuspended);
            return (
              <div
                key={step.id}
                className={`rounded-xl border p-3 ${
                  done
                    ? "bg-emerald-500/10 border-emerald-500/30"
                    : active
                    ? "bg-console-500/12 border-console-500/35"
                    : "bg-surface-2/60 border-subtle"
                }`}
              >
                <div className="flex items-center justify-between gap-1 text-[11px] font-bold">
                  <span
                    className={
                      done
                        ? "text-emerald-300"
                        : active
                        ? "text-console-300"
                        : "text-muted"
                    }
                  >
                    {step.id}. {step.title}
                  </span>
                  {done && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />}
                </div>
                <div className="text-[11px] text-secondary mt-1">{step.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Document Upload & List Card (not shown as editable action if suspended, show compliance summary only) */}
      {!isSuspended ? (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3 rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div>
                <h2 className="font-display text-base font-bold text-primary flex items-center gap-2">
                  <FileUp className="w-4 h-4 text-console-400" />
                  <span>Submit KYC Document</span>
                </h2>
                <p className="text-xs text-muted mt-0.5">
                  Accepted formats: PDF, JPG, JPEG, PNG (max 5 MB) or secure reference URL.
                </p>
              </div>
              <div className="inline-flex rounded-lg bg-surface-2 border border-subtle p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setUploadMode("file")}
                  className={`px-2.5 py-1 rounded-md font-medium flex items-center gap-1.5 ${
                    uploadMode === "file"
                      ? "bg-console-600 text-white"
                      : "text-secondary hover:text-primary"
                  }`}
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>File Upload</span>
                </button>
                <button
                  type="button"
                  onClick={() => setUploadMode("url")}
                  className={`px-2.5 py-1 rounded-md font-medium flex items-center gap-1.5 ${
                    uploadMode === "url"
                      ? "bg-console-600 text-white"
                      : "text-secondary hover:text-primary"
                  }`}
                >
                  <Link2 className="w-3.5 h-3.5" />
                  <span>Document URL</span>
                </button>
              </div>
            </div>

            <form onSubmit={handleSubmitKyc} className="space-y-4">
              <Select
                label="Document Type"
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
              >
                <option value="GST">GST Certificate</option>
                <option value="PAN">Business PAN Card</option>
                <option value="FSSAI">FSSAI License</option>
                <option value="TRADE_LICENSE">Trade License</option>
                <option value="ID_PROOF">Signatory ID Proof</option>
              </Select>

              {uploadMode === "file" ? (
                <div className="space-y-2">
                  <label className="block text-xs font-semibold text-secondary uppercase tracking-wider">
                    Select PDF or Image File
                  </label>
                  <label className="flex flex-col items-center justify-center rounded-xl border border-dashed border-strong bg-surface-2/60 hover:bg-surface-2 p-5 cursor-pointer transition-colors text-center">
                    <Upload className="w-6 h-6 text-console-400 mb-2" />
                    <span className="text-xs font-semibold text-primary">
                      {selectedFile
                        ? selectedFile.name
                        : "Choose KYC file from device"}
                    </span>
                    <span className="text-[11px] text-muted mt-1">
                      {selectedFile
                        ? `${(selectedFile.size / 1024).toFixed(1)} KB`
                        : "Validated via binary header check (.pdf, .png, .jpg)"}
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
                </div>
              ) : (
                <Input
                  label="Verification Document URL"
                  placeholder="https://docs.gobeyond.in/kyc/gst-certificate.pdf"
                  value={docUrl}
                  onChange={(e) => setDocUrl(e.target.value)}
                />
              )}

              <Button
                type="submit"
                variant="console"
                fullWidth
                isLoading={uploading}
              >
                {uploadMode === "file"
                  ? "Upload KYC File"
                  : "Submit KYC Document Link"}
              </Button>
            </form>
          </div>

          <div className="lg:col-span-2 rounded-2xl bg-surface border border-subtle p-5 sm:p-6 space-y-4">
            <h2 className="font-display text-base font-bold text-primary flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Submitted KYC Ledger ({documents.length})</span>
            </h2>

            {documents.length === 0 ? (
              <div className="rounded-xl border border-dashed border-subtle bg-surface-2/40 p-6 text-center text-xs text-muted">
                No compliance documents uploaded yet. Upload GST or PAN to start verification.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-72 overflow-y-auto">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="rounded-xl bg-surface-2 border border-subtle p-3 flex items-center justify-between gap-2 text-xs"
                  >
                    <div className="min-w-0">
                      <div className="font-semibold text-primary">
                        {doc.document_type}
                      </div>
                      <div className="text-[11px] text-muted font-mono truncate">
                        {doc.document_url}
                      </div>
                    </div>
                    <StatusBadge status={doc.status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="rounded-2xl bg-surface border border-subtle p-6 flex items-start gap-3 text-sm text-secondary">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-primary">
              Compliance Escalation Required
            </p>
            <p className="text-xs text-muted mt-1">
              Registered Contact: {partnerProfile.contact_email} ·{" "}
              {partnerProfile.contact_phone} · Contract Rate:{" "}
              {(partnerProfile.commission_rate * 100).toFixed(2)}%
            </p>
          </div>
        </div>
      )}
    </div>
  );
}


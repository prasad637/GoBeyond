"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Camera,
  CameraOff,
  CheckCircle2,
  QrCode,
  RotateCcw,
  ShieldAlert,
  Ticket,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { StatusBadge, useToast } from "@/components/dashboard";
import { QRVerificationResult } from "./partnerTypes";

export function PartnerQrScannerView({
  businessName,
  onVerified,
}: {
  businessName: string;
  onVerified?: () => Promise<void> | void;
}) {
  const toast = useToast();
  const [qrInput, setQrInput] = useState("");
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<QRVerificationResult | null>(null);
  const [history, setHistory] = useState<QRVerificationResult[]>([]);
  const [supportsCameraBarcode, setSupportsCameraBarcode] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const scanLoopRef = useRef<number | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
    const hasBarcodeDetector =
      typeof window !== "undefined" &&
      "BarcodeDetector" in window &&
      Boolean(navigator?.mediaDevices?.getUserMedia);
    setSupportsCameraBarcode(hasBarcodeDetector);

    return () => {
      stopCamera();
    };
  }, []);

  const stopCamera = () => {
    if (scanLoopRef.current !== null) {
      cancelAnimationFrame(scanLoopRef.current);
      scanLoopRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
  };

  const verifyToken = async (tokenValue: string) => {
    const clean = tokenValue.trim();
    if (!clean) return;
    setScanning(true);
    try {
      const res = await apiRequest<QRVerificationResult>("/partners/verify-qr-pass", {
        method: "POST",
        body: JSON.stringify({ qr_token: clean }),
      });
      const entry: QRVerificationResult = {
        ...res,
        scanned_at: new Date().toLocaleTimeString("en-IN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      };
      setResult(entry);
      setHistory((prev) => [entry, ...prev.slice(0, 9)]);
      if (entry.valid) {
        toast.success("Pass verified", `${entry.booking_reference} admitted.`);
        await onVerified?.();
      } else {
        toast.error("Verification denied", entry.message);
      }
    } catch (err: any) {
      toast.error("Verification failed", err.message || "Unable to verify pass.");
    } finally {
      setScanning(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await verifyToken(qrInput);
  };

  const startCameraScanner = async () => {
    try {
      const Detector = (window as any).BarcodeDetector;
      if (!Detector) return;
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      streamRef.current = stream;
      setCameraActive(true);

      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => {});
          const detector = new Detector({ formats: ["qr_code"] });
          const detectFrame = async () => {
            if (!videoRef.current || !streamRef.current) return;
            try {
              const codes = await detector.detect(videoRef.current);
              if (codes && codes.length > 0 && codes[0].rawValue) {
                const code = String(codes[0].rawValue).trim();
                stopCamera();
                setQrInput(code);
                await verifyToken(code);
                return;
              }
            } catch {
              // ignore transient video frame errors
            }
            scanLoopRef.current = requestAnimationFrame(detectFrame);
          };
          scanLoopRef.current = requestAnimationFrame(detectFrame);
        }
      }, 100);
    } catch (err: any) {
      toast.error(
        "Camera unavailable",
        err?.message || "Grant camera permissions or paste the QR pass token manually."
      );
      stopCamera();
    }
  };

  const handleReset = () => {
    setQrInput("");
    setResult(null);
    inputRef.current?.focus();
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Main Scanner Card */}
        <div className="lg:col-span-3 rounded-2xl bg-surface border border-subtle p-6 sm:p-8 shadow-surface space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="w-12 h-12 rounded-2xl bg-console-500/12 border border-console-500/30 flex items-center justify-center text-console-300 shrink-0">
                <QrCode className="w-6 h-6" />
              </div>
              <div>
                {/* E2E expects h3:has-text("Gate Admission QR Pass Scanner") */}
                <h3 className="font-display text-xl sm:text-2xl font-bold text-primary tracking-tight">
                  Gate Admission QR Pass Scanner
                </h3>
                <p className="text-xs sm:text-sm text-secondary mt-1">
                  Validate customer gate passes for <strong className="text-primary">{businessName}</strong>.
                  Cross-establishment passes are automatically rejected and logged.
                </p>
              </div>
            </div>

            {supportsCameraBarcode && (
              <Button
                type="button"
                variant={cameraActive ? "danger" : "secondary"}
                size="sm"
                leftIcon={
                  cameraActive ? (
                    <CameraOff className="w-4 h-4" />
                  ) : (
                    <Camera className="w-4 h-4" />
                  )
                }
                onClick={cameraActive ? stopCamera : startCameraScanner}
              >
                {cameraActive ? "Stop Camera" : "Camera Scan"}
              </Button>
            )}
          </div>

          {cameraActive && (
            <div className="rounded-xl overflow-hidden border border-console-500/40 bg-black relative">
              <video
                ref={videoRef}
                muted
                playsInline
                className="w-full max-h-64 object-cover"
              />
              <div className="px-3 py-2 bg-surface-2/90 text-[11px] text-secondary flex items-center justify-between">
                <span>Point device camera at customer QR gate pass...</span>
                <span className="font-mono text-console-300">LIVE SCANNING</span>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="flex flex-col sm:flex-row gap-3">
              {/* E2E expects input[placeholder*="Enter QR token"] */}
              <input
                ref={inputRef}
                type="text"
                required
                placeholder="Enter QR token (e.g. GB-PASS-...) or Booking Reference (GB-2026-...)"
                value={qrInput}
                onChange={(e) => setQrInput(e.target.value)}
                className="flex-1 h-11 px-4 rounded-xl bg-surface-2 border border-subtle focus:outline-none focus:border-console-500 focus:ring-2 focus:ring-console-500/20 font-mono text-sm text-primary placeholder:text-muted"
              />
              <div className="flex items-center gap-2 shrink-0">
                {/* E2E expects button[type="submit"]:has-text("Validate") */}
                <Button
                  type="submit"
                  variant="console"
                  size="lg"
                  isLoading={scanning}
                  className="flex-1 sm:flex-initial"
                >
                  Validate
                </Button>
                {(qrInput || result) && (
                  <Button
                    type="button"
                    variant="secondary"
                    size="lg"
                    onClick={handleReset}
                    aria-label="Reset scanner"
                    leftIcon={<RotateCcw className="w-4 h-4" />}
                  >
                    Next Scan
                  </Button>
                )}
              </div>
            </div>
          </form>

          {/* Real API Result Banner */}
          {result && (
            <div
              className={`rounded-2xl border p-5 sm:p-6 space-y-4 animate-fadeIn ${
                result.valid
                  ? "bg-emerald-500/10 border-emerald-500/35"
                  : "bg-red-500/10 border-red-500/35"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  {result.valid ? (
                    <CheckCircle2 className="w-7 h-7 text-emerald-400 shrink-0 mt-0.5" />
                  ) : (
                    <ShieldAlert className="w-7 h-7 text-red-400 shrink-0 mt-0.5" />
                  )}
                  <div>
                    <div className="font-display font-bold text-lg text-primary">
                      {result.valid ? "ENTRY GRANTED" : "ACCESS DENIED"}
                    </div>
                    <p className="text-sm text-secondary mt-0.5">{result.message}</p>
                  </div>
                </div>
                <StatusBadge status={result.status} />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 rounded-xl bg-surface/80 border border-subtle text-xs">
                <div>
                  <span className="text-muted block">Booking Reference</span>
                  <span className="font-mono font-bold text-primary mt-0.5 block">
                    {result.booking_reference}
                  </span>
                </div>
                <div>
                  <span className="text-muted block">Customer</span>
                  <span className="font-semibold text-primary mt-0.5 block">
                    {result.customer_name}
                  </span>
                </div>
                <div>
                  <span className="text-muted block">Vertical</span>
                  <span className="font-semibold text-primary mt-0.5 block">
                    {result.booking_type}
                  </span>
                </div>
              </div>

              {result.items && result.items.length > 0 && (
                <div className="space-y-1.5">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
                    Admitted Pass Items
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {result.items.map((item, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-2 border border-subtle text-xs font-medium text-primary"
                      >
                        <Ticket className="w-3.5 h-3.5 text-console-400" />
                        <span>
                          {item.quantity}x {item.name}
                        </span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* E2E expects text=Admitted & logged to append-only audit trail */}
              <div className="pt-2 border-t border-subtle flex items-center justify-between text-[11px] text-secondary">
                <span>
                  {result.valid
                    ? "Admitted & logged to append-only audit trail"
                    : "Denial recorded with tenant isolation policy"}
                </span>
                {result.scanned_at && (
                  <span className="font-mono text-muted">{result.scanned_at}</span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Shift Scan History */}
        <div className="lg:col-span-2 rounded-2xl bg-surface border border-subtle p-5 sm:p-6 flex flex-col justify-between gap-4">
          <div className="space-y-4">
            <div>
              <h4 className="font-display text-base font-bold text-primary">
                Session Scan Log
              </h4>
              <p className="text-xs text-muted mt-0.5">
                Live verification responses recorded during this console session
              </p>
            </div>

            {history.length === 0 ? (
              <div className="rounded-xl border border-dashed border-subtle bg-surface-2/40 p-8 text-center text-xs text-muted">
                No passes scanned yet in this session. Scan or paste a booking token to begin.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[420px] overflow-y-auto pr-1">
                {history.map((item, idx) => (
                  <div
                    key={`${item.booking_reference}-${idx}`}
                    className="rounded-xl bg-surface-2 border border-subtle p-3 space-y-1.5 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono font-bold text-primary truncate">
                        {item.booking_reference}
                      </span>
                      <StatusBadge status={item.status} />
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-secondary">
                      <span className="truncate">{item.customer_name}</span>
                      <span className="font-mono text-muted shrink-0">
                        {item.scanned_at}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-xl bg-surface-2/60 border border-subtle p-3.5 text-[11px] text-secondary leading-relaxed">
            <strong className="text-primary">Security Guarantee:</strong> Every verified
            entry writes an immutable <code className="font-mono text-console-300">QR_PASS_SCANNED</code> event to Super Admin audit logs.
          </div>
        </div>
      </div>
    </div>
  );
}


"use client";

import React, { useEffect, useState } from "react";
import { AlertTriangle, ShieldAlert } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Input";
import { cn } from "@/lib/cn";

export interface ConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (notes: string) => Promise<void> | void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "console";
  requireNotes?: boolean;
  showNotesInput?: boolean;
  notesLabel?: string;
  notesPlaceholder?: string;
  initialNotes?: string;
}

export function ConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "danger",
  requireNotes = false,
  showNotesInput = false,
  notesLabel = "Audit Justification / Notes",
  notesPlaceholder = "Enter reason or compliance notes...",
  initialNotes = "",
}: ConfirmationModalProps) {
  const [notes, setNotes] = useState(initialNotes);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setNotes(initialNotes);
      setError(null);
      setLoading(false);
    }
  }, [isOpen, initialNotes]);

  const handleConfirm = async () => {
    if (requireNotes && notes.trim().length < 3) {
      setError("Please enter a valid justification (minimum 3 characters).");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await onConfirm(notes.trim());
    } catch (err: any) {
      setError(err?.message || "Action failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const iconTone =
    variant === "danger"
      ? "bg-red-500/12 border-red-500/30 text-red-400"
      : variant === "warning"
      ? "bg-amber-500/12 border-amber-500/30 text-amber-300"
      : "bg-console-500/12 border-console-500/30 text-console-300";

  return (
    <Modal
      isOpen={isOpen}
      onClose={loading ? () => {} : onClose}
      size="sm"
      title={title}
      footer={
        <>
          <Button
            variant="secondary"
            size="sm"
            onClick={onClose}
            disabled={loading}
          >
            {cancelLabel}
          </Button>
          <Button
            variant={variant === "danger" ? "danger" : "console"}
            size="sm"
            isLoading={loading}
            onClick={handleConfirm}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="flex items-start gap-3.5">
          <div
            className={cn(
              "w-10 h-10 rounded-xl border flex items-center justify-center shrink-0",
              iconTone
            )}
          >
            {variant === "danger" ? (
              <ShieldAlert className="w-5 h-5" />
            ) : (
              <AlertTriangle className="w-5 h-5" />
            )}
          </div>
          <p className="text-sm text-secondary leading-relaxed">{description}</p>
        </div>

        {(showNotesInput || requireNotes) && (
          <Textarea
            label={notesLabel}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={notesPlaceholder}
            rows={3}
            error={error || undefined}
          />
        )}

        {error && !showNotesInput && !requireNotes && (
          <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}


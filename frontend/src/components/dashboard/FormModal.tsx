"use client";

import React from "react";
import { AlertCircle } from "lucide-react";
import { Modal, ModalSize } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";

export interface FormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (e: React.FormEvent) => void;
  title: string;
  description?: string;
  submitLabel?: string;
  cancelLabel?: string;
  loading?: boolean;
  error?: string | null;
  size?: ModalSize;
  children: React.ReactNode;
}

export function FormModal({
  isOpen,
  onClose,
  onSubmit,
  title,
  description,
  submitLabel = "Save Changes",
  cancelLabel = "Cancel",
  loading = false,
  error,
  size = "md",
  children,
}: FormModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={loading ? () => {} : onClose}
      title={title}
      description={description}
      size={size}
    >
      <form onSubmit={onSubmit} className="space-y-4">
        {error && (
          <div
            role="alert"
            className="p-3 rounded-xl bg-red-500/10 border border-red-500/25 text-red-400 text-xs flex items-start gap-2"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <div className="space-y-4">{children}</div>

        <div className="pt-4 border-t border-subtle flex items-center justify-end gap-2.5">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onClose}
            disabled={loading}
          >
            {cancelLabel}
          </Button>
          <Button
            type="submit"
            variant="console"
            size="sm"
            isLoading={loading}
          >
            {submitLabel}
          </Button>
        </div>
      </form>
    </Modal>
  );
}


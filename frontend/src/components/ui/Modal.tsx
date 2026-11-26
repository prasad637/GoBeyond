"use client";

import React, { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

export type ModalSize = "sm" | "md" | "lg" | "xl" | "full";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: ModalSize;
  showCloseButton?: boolean;
  closeOnBackdrop?: boolean;
  closeOnEscape?: boolean;
  className?: string;
  bodyClassName?: string;
}

const sizeClasses: Record<ModalSize, string> = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
  full: "max-w-6xl",
};

export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
  showCloseButton = true,
  closeOnBackdrop = true,
  closeOnEscape = true,
  className,
  bodyClassName,
}: ModalProps) {
  const [mounted, setMounted] = useState(false);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!isOpen) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (closeOnEscape && event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, closeOnEscape, onClose]);

  if (!mounted || !isOpen) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-4 bg-black/80 backdrop-blur-md animate-fadeIn"
      role="presentation"
      onMouseDown={(event) => {
        if (closeOnBackdrop && event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descriptionId : undefined}
        className={cn(
          "relative w-full bg-surface border border-strong text-primary shadow-modal overflow-hidden flex flex-col max-h-[90vh]",
          "rounded-t-2xl sm:rounded-2xl animate-scaleUp",
          sizeClasses[size],
          className
        )}
      >
        {(title || description || showCloseButton) && (
          <div className="flex items-start justify-between gap-4 px-5 sm:px-6 py-4 border-b border-subtle bg-surface-2/60 shrink-0">
            <div className="min-w-0">
              {title ? (
                <h2
                  id={titleId}
                  className="font-display text-base sm:text-lg font-bold text-primary tracking-tight"
                >
                  {title}
                </h2>
              ) : null}
              {description ? (
                <p id={descriptionId} className="mt-0.5 text-xs sm:text-sm text-secondary">
                  {description}
                </p>
              ) : null}
            </div>

            {showCloseButton ? (
              <button
                type="button"
                onClick={onClose}
                aria-label="Close modal"
                className="p-2 -mr-1 rounded-lg text-secondary hover:text-primary hover:bg-surface-3 transition-colors shrink-0"
              >
                <X className="w-4 h-4" aria-hidden="true" />
              </button>
            ) : null}
          </div>
        )}

        <div className={cn("p-5 sm:p-6 overflow-y-auto flex-1", bodyClassName)}>
          {children}
        </div>

        {footer ? (
          <div className="px-5 sm:px-6 py-4 border-t border-subtle bg-surface-2/40 flex items-center justify-end gap-3 shrink-0">
            {footer}
          </div>
        ) : null}
      </div>
    </div>,
    document.body
  );
}


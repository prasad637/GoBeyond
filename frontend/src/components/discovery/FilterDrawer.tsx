"use client";

import React from "react";
import { RotateCcw } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";

export interface FilterDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  activeFilterCount?: number;
  onReset?: () => void;
  children: React.ReactNode;
}

export function FilterDrawer({
  isOpen,
  onClose,
  title = "Filter & Sort",
  description = "Refine results to find the right experience",
  activeFilterCount = 0,
  onReset,
  children,
}: FilterDrawerProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      description={description}
      size="sm"
      footer={
        <div className="flex items-center justify-between w-full gap-3">
          {onReset ? (
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
              disabled={activeFilterCount === 0}
              onClick={onReset}
            >
              Reset{activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
            </Button>
          ) : (
            <div />
          )}
          <Button variant="primary" size="sm" onClick={onClose}>
            Show Results
          </Button>
        </div>
      }
    >
      <div className="space-y-5">{children}</div>
    </Modal>
  );
}


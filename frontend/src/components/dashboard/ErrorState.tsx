import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

export interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  retryLabel?: string;
}

export function ErrorState({
  title = "Unable to load console data",
  description = "We could not reach the backend service cleanly. Please retry in a moment.",
  onRetry,
  retryLabel = "Retry Request",
}: ErrorStateProps) {
  return (
    <EmptyState
      variant="error"
      icon={<AlertTriangle className="w-6 h-6" />}
      title={title}
      description={description}
      action={
        onRetry ? (
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<RefreshCw className="w-4 h-4" />}
            onClick={onRetry}
          >
            {retryLabel}
          </Button>
        ) : undefined
      }
    />
  );
}


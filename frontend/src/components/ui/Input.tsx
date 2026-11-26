"use client";

import React, { useId } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  leftIcon?: React.ReactNode;
  rightElement?: React.ReactNode;
  containerClassName?: string;
  fullWidth?: boolean;
}

const baseFieldStyles =
  "w-full bg-surface-2 text-primary placeholder:text-muted border border-subtle rounded-lg transition-colors duration-150 " +
  "text-base md:text-sm focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

const errorFieldStyles =
  "border-red-500/60 focus:border-red-500 focus:ring-red-500/20";

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      containerClassName,
      label,
      hint,
      error,
      leftIcon,
      rightElement,
      fullWidth = true,
      id,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const fieldId = id || generatedId;
    const hintId = hint ? `${fieldId}-hint` : undefined;
    const errorId = error ? `${fieldId}-error` : undefined;
    const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;

    return (
      <div className={cn(fullWidth ? "w-full" : "inline-block", containerClassName)}>
        {label ? (
          <label
            htmlFor={fieldId}
            className="block text-xs font-semibold text-secondary uppercase tracking-wider mb-1.5"
          >
            {label}
          </label>
        ) : null}

        <div className="relative flex items-center">
          {leftIcon ? (
            <span
              className="pointer-events-none absolute left-3.5 flex items-center text-muted"
              aria-hidden="true"
            >
              {leftIcon}
            </span>
          ) : null}

          <input
            ref={ref}
            id={fieldId}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className={cn(
              baseFieldStyles,
              "h-11 md:h-10 px-3.5",
              leftIcon && "pl-10",
              rightElement && "pr-11",
              error && errorFieldStyles,
              className
            )}
            {...props}
          />

          {rightElement ? (
            <div className="absolute right-2.5 flex items-center">{rightElement}</div>
          ) : null}
        </div>

        {error ? (
          <p id={errorId} className="mt-1.5 text-xs text-red-400" role="alert">
            {error}
          </p>
        ) : hint ? (
          <p id={hintId} className="mt-1.5 text-xs text-muted">
            {hint}
          </p>
        ) : null}
      </div>
    );
  }
);

Input.displayName = "Input";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
  error?: string;
  containerClassName?: string;
  fullWidth?: boolean;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      className,
      containerClassName,
      label,
      hint,
      error,
      fullWidth = true,
      id,
      rows = 3,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const fieldId = id || generatedId;
    const hintId = hint ? `${fieldId}-hint` : undefined;
    const errorId = error ? `${fieldId}-error` : undefined;
    const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;

    return (
      <div className={cn(fullWidth ? "w-full" : "inline-block", containerClassName)}>
        {label ? (
          <label
            htmlFor={fieldId}
            className="block text-xs font-semibold text-secondary uppercase tracking-wider mb-1.5"
          >
            {label}
          </label>
        ) : null}

        <textarea
          ref={ref}
          id={fieldId}
          rows={rows}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(
            baseFieldStyles,
            "py-2.5 px-3.5 min-h-[88px]",
            error && errorFieldStyles,
            className
          )}
          {...props}
        />

        {error ? (
          <p id={errorId} className="mt-1.5 text-xs text-red-400" role="alert">
            {error}
          </p>
        ) : hint ? (
          <p id={hintId} className="mt-1.5 text-xs text-muted">
            {hint}
          </p>
        ) : null}
      </div>
    );
  }
);

Textarea.displayName = "Textarea";

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
  error?: string;
  containerClassName?: string;
  fullWidth?: boolean;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      className,
      containerClassName,
      label,
      hint,
      error,
      fullWidth = true,
      id,
      children,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const fieldId = id || generatedId;
    const hintId = hint ? `${fieldId}-hint` : undefined;
    const errorId = error ? `${fieldId}-error` : undefined;
    const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;

    return (
      <div className={cn(fullWidth ? "w-full" : "inline-block", containerClassName)}>
        {label ? (
          <label
            htmlFor={fieldId}
            className="block text-xs font-semibold text-secondary uppercase tracking-wider mb-1.5"
          >
            {label}
          </label>
        ) : null}

        <div className="relative flex items-center">
          <select
            ref={ref}
            id={fieldId}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className={cn(
              baseFieldStyles,
              "appearance-none h-11 md:h-10 pl-3.5 pr-9",
              error && errorFieldStyles,
              className
            )}
            {...props}
          >
            {children}
          </select>
          <ChevronDown
            className="pointer-events-none absolute right-3 w-4 h-4 text-muted"
            aria-hidden="true"
          />
        </div>

        {error ? (
          <p id={errorId} className="mt-1.5 text-xs text-red-400" role="alert">
            {error}
          </p>
        ) : hint ? (
          <p id={hintId} className="mt-1.5 text-xs text-muted">
            {hint}
          </p>
        ) : null}
      </div>
    );
  }
);

Select.displayName = "Select";


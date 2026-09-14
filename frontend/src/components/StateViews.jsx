import React from "react";
import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export function CardSkeleton({ className = "", height = 120 }) {
  return <div className={`skeleton ${className}`} style={{ height }} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-6" data-testid="page-skeleton">
      <div className="skeleton h-8 w-64" />
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="skeleton h-28" />
        ))}
      </div>
      <div className="skeleton h-72 w-full" />
    </div>
  );
}

export function EmptyState({ title, description, action, testId = "empty-state" }) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[#2D334B] bg-[#0F111A] px-6 py-16 text-center"
      data-testid={testId}
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#161926] text-[#64748B]">
        <Inbox size={26} />
      </div>
      <h3 className="font-display text-lg font-bold text-[#F8FAFC]">{title}</h3>
      <p className="mt-2 max-w-md text-sm text-[#94A3B8]">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({ onRetry, message = "We couldn't load this data.", testId = "error-state" }) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-2xl border border-rose-900/40 bg-rose-950/10 px-6 py-14 text-center"
      data-testid={testId}
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-950/40 text-rose-400">
        <AlertTriangle size={26} />
      </div>
      <h3 className="font-display text-lg font-bold text-[#F8FAFC]">Something went wrong</h3>
      <p className="mt-2 max-w-md text-sm text-[#94A3B8]">{message}</p>
      {onRetry && (
        <Button
          onClick={onRetry}
          variant="outline"
          className="mt-5 border-[#2D334B] bg-transparent text-[#F8FAFC] hover:bg-[#161926]"
          data-testid="error-retry-btn"
        >
          <RefreshCw size={15} className="mr-2" /> Try again
        </Button>
      )}
    </div>
  );
}

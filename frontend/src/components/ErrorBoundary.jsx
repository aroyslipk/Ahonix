import React from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import { Button } from "@/components/ui/button";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          className="flex flex-col items-center justify-center rounded-2xl border border-[#16221B] bg-[#0B110E] p-8 sm:p-12 text-center max-w-xl mx-auto my-12 shadow-xl"
          data-testid="error-boundary-view"
        >
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-amber-500/20 bg-amber-500/10 text-amber-400">
            <AlertTriangle size={28} />
          </div>
          <h2 className="font-display text-xl font-bold text-[#F8FAFC]">
            Unable to display this view
          </h2>
          <p className="mt-2 text-xs text-[#94A3B8] leading-relaxed max-w-md">
            An unexpected error occurred while loading this section. Your workspace data is safe.
          </p>
          {this.state.error?.message && (
            <p className="mt-3 rounded-lg border border-[#16221B] bg-[#070C0A] px-3 py-1.5 font-mono text-[11px] text-[#64748B] max-w-full overflow-hidden text-ellipsis">
              {this.state.error.message}
            </p>
          )}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Button
              onClick={this.handleReset}
              variant="outline"
              className="border-[#16221B] bg-[#070C0A] text-xs text-[#CBD5E1] hover:bg-[#121A16]"
            >
              <RefreshCw size={13} className="mr-1.5" /> Try again
            </Button>
            <Button
              onClick={() => {
                window.location.href = "/app/overview";
              }}
              className="bg-emerald-500 text-xs font-semibold text-emerald-950 hover:bg-emerald-400"
            >
              <Home size={13} className="mr-1.5" /> Go to Overview
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

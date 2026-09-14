import React from "react";

export function Logo({ size = 28, showText = true, className = "" }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`} data-testid="ahonix-logo">
      <div
        className="relative flex items-center justify-center rounded-lg"
        style={{
          width: size,
          height: size,
          background: "linear-gradient(135deg, #10B981 0%, #06B6D4 100%)",
          boxShadow: "0 0 18px rgba(16,185,129,0.35)",
        }}
      >
        <svg width={size * 0.62} height={size * 0.62} viewBox="0 0 24 24" fill="none">
          <path
            d="M12 2 L20 20 H15.5 L12 11 L8.5 20 H4 Z"
            fill="#04120c"
            stroke="#04120c"
            strokeWidth="0.5"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      {showText && (
        <div className="leading-none">
          <span className="font-display font-extrabold tracking-tight text-[#F8FAFC]" style={{ fontSize: size * 0.62 }}>
            AHONIX
          </span>
        </div>
      )}
    </div>
  );
}

export function Sparkle({ className = "" }) {
  return <span className={`text-emerald-400 ${className}`}>✦</span>;
}

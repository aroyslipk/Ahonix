import React from "react";

export function Logo({ size = 28, showText = true, className = "" }) {
  return (
    <div className={`flex items-center gap-3 ${className}`} data-testid="ahonix-logo">
      {/* 3D Sculptural Emblem Icon */}
      <div
        className="relative flex shrink-0 items-center justify-center rounded-lg"
        style={{
          width: size,
          height: size,
        }}
      >
        <svg
          width={size}
          height={size}
          viewBox="0 0 32 32"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="emeraldChrome" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00E599" />
              <stop offset="45%" stopColor="#008060" />
              <stop offset="85%" stopColor="#042F22" />
              <stop offset="100%" stopColor="#00E599" />
            </linearGradient>
            <linearGradient id="goldEdge" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#F5E08C" />
              <stop offset="50%" stopColor="#D4AF37" />
              <stop offset="100%" stopColor="#8C6E18" />
            </linearGradient>
          </defs>
          {/* Base A Silhouette */}
          <path
            d="M16 2.5L29 28.5H22L16 16.5L10 28.5H3L16 2.5Z"
            fill="url(#emeraldChrome)"
            stroke="url(#goldEdge)"
            strokeWidth="0.8"
            strokeLinejoin="round"
          />
          {/* Inner cutout triangle */}
          <polygon
            points="16,9.5 20.5,19 11.5,19"
            fill="#050807"
            stroke="url(#goldEdge)"
            strokeWidth="0.5"
          />
        </svg>
      </div>
      {showText && (
        <span
          className="font-display font-bold tracking-[0.2em] text-[#F8FAFC]"
          style={{ fontSize: size * 0.58 }}
        >
          AHONIX
        </span>
      )}
    </div>
  );
}

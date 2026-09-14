import React, { useState, useRef, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, Search, Bell, ChevronDown, Menu, ArrowRight } from "lucide-react";
import { Logo } from "@/components/Logo";
import { useUI } from "@/context/UIContext";
import { useWorkspace } from "@/context/WorkspaceContext";
import {
  Sheet, SheetContent, SheetTrigger,
} from "@/components/ui/sheet";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { NAV } from "@/components/Sidebar";
import { NavLink } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

// --- Global Search -----------------------------------------------------------
// Searches across pages (sidebar nav) and products (from cached query data).
// No backend endpoint needed — uses existing NAV and TanStack Query cache.

const SEARCH_PAGES = NAV.map((item) => ({
  type: "page",
  name: item.name,
  path: item.path,
  keywords: item.name.toLowerCase(),
}));

function useProductsFromCache() {
  const qc = useQueryClient();
  return useMemo(() => {
    const cached = qc.getQueryData(["products"]);
    if (!cached?.products) return [];
    return cached.products.map((p) => ({
      type: "product",
      name: p.name,
      id: p.id,
      category: p.category,
      path: `/app/products/${p.id}`,
      keywords: `${p.name} ${p.category}`.toLowerCase(),
    }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qc.getQueryData(["products"])]);
}

function SearchDropdown({ query, results, onSelect, onClose }) {
  if (!query.trim()) return null;

  return (
    <div className="absolute left-0 right-0 top-full mt-1.5 z-50 overflow-hidden rounded-xl border border-[#2D334B] bg-[#0B0D14] shadow-2xl">
      {results.length === 0 ? (
        <div className="px-4 py-5 text-center text-sm text-[#64748B]">
          No results for "<span className="text-[#94A3B8]">{query}</span>"
        </div>
      ) : (
        <div className="max-h-72 overflow-y-auto py-1">
          {results.map((r) => (
            <button
              key={r.path}
              onClick={() => onSelect(r.path)}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors hover:bg-[#161926]"
              data-testid={`search-result-${r.type}`}
            >
              <span className="shrink-0 rounded bg-[#161926] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#64748B]">
                {r.type === "product" ? "Product" : "Page"}
              </span>
              <span className="flex-1 truncate text-[#F8FAFC]">{r.name}</span>
              {r.category && (
                <span className="text-xs text-[#475569]">{r.category}</span>
              )}
              <ArrowRight size={12} className="shrink-0 text-[#475569]" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// --- TopBar ------------------------------------------------------------------

export function TopBar() {
  const { openAsk } = useUI();
  const { workspace } = useWorkspace();
  const navigate = useNavigate();

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef(null);
  const products = useProductsFromCache();

  const searchResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];
    const all = [...SEARCH_PAGES, ...products];
    return all.filter((item) => item.keywords.includes(q)).slice(0, 10);
  }, [searchQuery, products]);

  // Close search on outside click
  useEffect(() => {
    function handleClick(e) {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setSearchOpen(false);
      }
    }
    if (searchOpen) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [searchOpen]);

  const handleSearchSelect = (path) => {
    setSearchOpen(false);
    setSearchQuery("");
    navigate(path);
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-[#1E2235] bg-[#08090E]/90 px-4 backdrop-blur-md sm:px-6">
      {/* mobile menu */}
      <Sheet>
        <SheetTrigger asChild>
          <button className="rounded-lg p-2 text-[#94A3B8] hover:bg-[#161926] md:hidden" data-testid="mobile-menu-btn">
            <Menu size={20} />
          </button>
        </SheetTrigger>
        <SheetContent side="left" className="w-72 border-[#1E2235] bg-[#0B0D14] p-0">
          <div className="flex h-16 items-center px-5">
            <Logo size={24} />
          </div>
          <nav className="space-y-1 px-3">
            {NAV.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                data-testid={`m-${item.testid}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium ${
                    isActive ? "bg-emerald-500/10 text-emerald-300" : "text-[#94A3B8]"
                  }`
                }
              >
                <item.icon size={18} />
                {item.name}
              </NavLink>
            ))}
          </nav>
        </SheetContent>
      </Sheet>

      <div className="md:hidden">
        <Logo size={22} showText={false} />
      </div>

      {/* store selector */}
      <button
        onClick={() => navigate("/app/settings")}
        className="hidden items-center gap-2 rounded-lg border border-[#1E2235] bg-[#0F111A] px-3 py-1.5 text-sm text-[#F8FAFC] hover:border-[#2D334B] sm:flex"
        data-testid="demo-store-selector"
      >
        <span className="flex h-5 w-5 items-center justify-center rounded bg-gradient-to-br from-emerald-500 to-cyan-500 text-[10px] font-bold text-emerald-950">
          {(workspace?.name || "N").slice(0, 1)}
        </span>
        <span className="font-medium">{workspace?.name || "Workspace"}</span>
        {workspace?.is_demo && (
          <span className="rounded bg-[#161926] px-1.5 py-0.5 text-[10px] text-[#94A3B8]">Demo</span>
        )}
        <ChevronDown size={14} className="text-[#64748B]" />
      </button>

      <div className="ml-auto flex items-center gap-2">
        {/* Search */}
        <div className="relative hidden lg:block" ref={searchRef}>
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#475569]" />
          <input
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setSearchOpen(true);
            }}
            onFocus={() => setSearchOpen(true)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setSearchOpen(false);
                e.target.blur();
              }
              if (e.key === "Enter" && searchResults.length > 0) {
                handleSearchSelect(searchResults[0].path);
              }
            }}
            placeholder="Search pages, products…"
            className="w-56 rounded-lg border border-[#1E2235] bg-[#0F111A] py-1.5 pl-9 pr-3 text-sm text-[#F8FAFC] outline-none placeholder:text-[#475569] focus:border-emerald-500/40"
            data-testid="global-search"
          />
          {searchOpen && (
            <SearchDropdown
              query={searchQuery}
              results={searchResults}
              onSelect={handleSearchSelect}
              onClose={() => setSearchOpen(false)}
            />
          )}
        </div>

        <button
          onClick={() => openAsk()}
          className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-emerald-500 to-emerald-600 px-3 py-2 text-sm font-semibold text-emerald-950 shadow-lg shadow-emerald-500/20 transition-transform hover:scale-[1.03]"
          data-testid="global-ask-ahonix-btn"
        >
          <Sparkles size={15} />
          <span className="hidden sm:inline">Ask AHONIX</span>
          <span className="text-emerald-800">✦</span>
        </button>

        {/* Notifications */}
        <Popover>
          <PopoverTrigger asChild>
            <button className="relative rounded-lg p-2 text-[#94A3B8] hover:bg-[#161926]" data-testid="notifications-btn">
              <Bell size={18} />
            </button>
          </PopoverTrigger>
          <PopoverContent
            align="end"
            className="w-80 border-[#2D334B] bg-[#0B0D14] p-0"
          >
            <div className="border-b border-[#1E2235] px-4 py-3">
              <h3 className="text-sm font-semibold text-[#F8FAFC]">Notifications</h3>
            </div>
            <div className="px-4 py-6 text-center">
              <Bell size={24} className="mx-auto mb-2 text-[#334155]" />
              <p className="text-sm text-[#94A3B8]">You're all caught up</p>
              <p className="mt-1 text-xs text-[#475569]">
                Notifications will appear here when AI insights or action updates need your attention.
              </p>
            </div>
            <div className="border-t border-[#1E2235] px-4 py-2.5">
              <button
                onClick={() => navigate("/app/ai-intelligence")}
                className="flex w-full items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-medium text-emerald-400 hover:bg-[#161926]"
                data-testid="notifications-view-insights"
              >
                View AI Insights <ArrowRight size={12} />
              </button>
            </div>
          </PopoverContent>
        </Popover>
      </div>
    </header>
  );
}

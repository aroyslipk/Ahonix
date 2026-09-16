import React, { useState, useRef, useEffect, useMemo } from "react";
import { useNavigate, NavLink } from "react-router-dom";
import {
  Search, Bell, ChevronDown, Menu, ArrowRight, MessageSquare
} from "lucide-react";
import { Logo } from "@/components/Logo";
import { useUI } from "@/context/UIContext";
import { useWorkspace } from "@/context/WorkspaceContext";
import {
  Sheet, SheetContent, SheetTrigger,
} from "@/components/ui/sheet";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { NAV } from "@/components/Sidebar";
import { useQueryClient } from "@tanstack/react-query";

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
    <div className="absolute left-0 right-0 top-full mt-1.5 z-50 overflow-hidden rounded-xl border border-white/10 bg-[#0B110E] shadow-2xl">
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
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors hover:bg-[#121A16]"
              data-testid={`search-result-${r.type}`}
            >
              <span className="shrink-0 rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#64748B]">
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

export function TopBar() {
  const { openAsk } = useUI();
  const { workspace } = useWorkspace();
  const navigate = useNavigate();

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

  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-white/[0.06] bg-[#050807]/95 px-4 backdrop-blur-md sm:px-6">
      {/* Mobile Menu Drawer */}
      <Sheet open={mobileDrawerOpen} onOpenChange={setMobileDrawerOpen}>
        <SheetTrigger asChild>
          <button
            className="rounded-lg p-2 text-[#94A3B8] transition-colors hover:bg-white/10 md:hidden"
            data-testid="mobile-menu-btn"
          >
            <Menu size={20} />
          </button>
        </SheetTrigger>
        <SheetContent side="left" className="w-72 border-r border-white/[0.06] bg-[#070C0A] p-0">
          <div className="flex h-16 items-center px-6 border-b border-white/[0.04]">
            <Logo size={24} />
          </div>
          <nav className="space-y-1 px-3 py-3 overflow-y-auto">
            {NAV.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setMobileDrawerOpen(false)}
                data-testid={`m-${item.testid}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors ${
                    isActive ? "bg-[#0B1612] text-[#00E599]" : "text-[#94A3B8]"
                  }`
                }
              >
                <item.icon size={17} />
                {item.name}
              </NavLink>
            ))}
          </nav>
        </SheetContent>
      </Sheet>

      <div className="md:hidden">
        <Logo size={22} showText={false} />
      </div>

      {/* Store Selector */}
      <button
        onClick={() => navigate("/app/settings")}
        className="hidden items-center gap-2.5 rounded-xl border border-white/[0.08] bg-[#0B110E] px-3.5 py-1.5 text-sm text-[#F8FAFC] transition-all hover:border-white/15 sm:flex"
        data-testid="demo-store-selector"
      >
        <span className="flex h-5 w-5 items-center justify-center rounded bg-[#008060] text-[10px] font-bold text-white">
          {(workspace?.name || "N").slice(0, 1)}
        </span>
        <span className="font-medium text-xs">{workspace?.name || "Workspace"}</span>
        {workspace?.is_demo && (
          <span className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[9px] font-semibold text-[#94A3B8] uppercase">
            Demo
          </span>
        )}
        <ChevronDown size={13} className="text-[#64748B]" />
      </button>

      <div className="ml-auto flex items-center gap-3">
        {/* Global Search */}
        <div className="relative hidden lg:block" ref={searchRef}>
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B]" />
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
            className="w-56 rounded-xl border border-white/[0.08] bg-[#0B110E] py-1.5 pl-8 pr-8 text-xs text-[#F8FAFC] outline-none placeholder:text-[#475569] focus:border-[#00E599]/40 focus:w-64 transition-all"
            data-testid="global-search"
          />
          <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-white/10 bg-white/[0.04] px-1 py-0.2 text-[9px] font-mono text-[#64748B]">
            /
          </span>
          {searchOpen && (
            <SearchDropdown
              query={searchQuery}
              results={searchResults}
              onSelect={handleSearchSelect}
              onClose={() => setSearchOpen(false)}
            />
          )}
        </div>

        {/* Ask AHONIX Button */}
        <button
          onClick={() => openAsk()}
          className="flex items-center gap-2 rounded-xl bg-[#00E599] px-3.5 py-2 text-xs font-bold text-[#041F16] shadow-md shadow-[#00E599]/10 transition-all hover:bg-[#20ffb0] hover:scale-[1.02]"
          data-testid="global-ask-ahonix-btn"
        >
          <MessageSquare size={14} className="fill-[#041F16]" />
          <span className="hidden sm:inline">Ask AHONIX</span>
        </button>

        {/* Notifications */}
        <Popover>
          <PopoverTrigger asChild>
            <button
              className="relative rounded-xl border border-white/[0.08] bg-[#0B110E] p-2 text-[#94A3B8] transition-colors hover:bg-white/10 hover:text-white"
              data-testid="notifications-btn"
            >
              <Bell size={16} />
            </button>
          </PopoverTrigger>
          <PopoverContent
            align="end"
            className="w-80 border border-white/10 bg-[#0B110E] p-0 shadow-2xl"
          >
            <div className="border-b border-white/[0.06] px-4 py-3">
              <p className="font-display text-xs font-bold uppercase tracking-wider text-[#F8FAFC]">
                Notifications
              </p>
            </div>
            <div className="p-4 text-center text-xs text-[#64748B]">
              All systems operational. No active anomalies.
            </div>
          </PopoverContent>
        </Popover>
      </div>
    </header>
  );
}

import React, { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { motion, useScroll, useTransform, useSpring, useMotionValue, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  Play,
  TrendingUp,
  ShieldCheck,
  CheckCircle2,
  Lock,
  BarChart3,
  Database,
  Layers,
  X,
  Compass,
  Menu,
  ChevronDown,
  Check,
  Zap,
  Sparkles,
  HelpCircle,
  Activity,
  FileText,
  Cpu,
  ArrowUpRight,
} from "lucide-react";
import { Logo } from "@/components/Logo";
import { Hero3DScene } from "@/components/3d/Hero3DScene";

const NAV_LINKS = [
  { id: "home", name: "Home", href: "#home" },
  { id: "loop", name: "Optimization Loop", href: "#loop" },
  { id: "features", name: "Features", href: "#features" },
  { id: "integrations", name: "Integrations", href: "#integrations" },
  { id: "pricing", name: "Pricing", href: "#pricing" },
  { id: "resources", name: "Resources", href: "#resources" },
];

const LOOP_STAGES = [
  {
    step: "01",
    name: "Connect",
    sub: "Unified Ingestion",
    desc: "Direct REST & Graph API ingestion from Shopify, Meta Ads, Google Ads, and payment gateways with zero webhook lag.",
    tag: "Native REST / OAuth",
    icon: Database,
  },
  {
    step: "02",
    name: "Understand",
    sub: "Unit Reconciliation",
    desc: "Reconciles variant-level COGS, pick & pack fees, return postage, and localized tax to compute baseline unit net profit.",
    tag: "Deterministic Math",
    icon: TrendingUp,
  },
  {
    step: "03",
    name: "Detect",
    sub: "Autonomous Signals",
    desc: "High-frequency algorithmic scans flag money leaks, ad fatigue, stockout cliffs, and sudden margin erosion.",
    tag: "Leak Sentinel",
    icon: Activity,
  },
  {
    step: "04",
    name: "Explain",
    sub: "Causal Attribution",
    desc: "Isolates the exact financial drivers behind performance swings. Zero guesswork or statistical hallucinations.",
    tag: "Root-Cause Analysis",
    icon: BarChart3,
  },
  {
    step: "05",
    name: "Simulate",
    sub: "Sandboxed Impact",
    desc: "Simulate SKU restock quantities and ad budget reallocations in an isolated digital sandbox before committing real cash.",
    tag: "Risk-Free Modeling",
    icon: Cpu,
  },
  {
    step: "06",
    name: "Recommend",
    sub: "Prescriptive Directives",
    desc: "Surfaces high-confidence, prioritized actions with projected dollar impact, timing urgency, and risk profiles.",
    tag: "Actionable Directives",
    icon: Sparkles,
  },
  {
    step: "07",
    name: "Approve",
    sub: "Executive Authorization",
    desc: "Human-in-the-loop validation gate ensures store founders maintain sovereign control over every live modification.",
    tag: "Human-In-The-Loop",
    icon: Lock,
  },
  {
    step: "08",
    name: "Execute",
    sub: "Synchronized Dispatch",
    desc: "Dispatches approved actions to channel APIs with transactional compare-and-swap auditability.",
    tag: "Atomic API Sync",
    icon: Zap,
  },
  {
    step: "09",
    name: "Measure",
    sub: "Feedback Verification",
    desc: "Audits realized net profit gains against simulated projections, continuously refining future predictive accuracy.",
    tag: "Closed Loop",
    icon: CheckCircle2,
  },
];

const PILLARS = [
  {
    icon: TrendingUp,
    badge: "Financial Truth",
    title: "True Profit Architecture",
    description:
      "Gross revenue reconciled against product COGS, variant overrides, return postage, platform fees, and real attributed advertising spend. Zero guessed metrics.",
  },
  {
    icon: BarChart3,
    badge: "Autonomous Signals",
    title: "Growth & Leak Detection",
    description:
      "Continuous algorithmic scans identify ROAS paradoxes, stockout cliffs, and margin leaks with projected revenue impact and deterministic confidence scoring.",
  },
  {
    icon: Database,
    badge: "Executive Intelligence",
    title: "Ask AHONIX Analyst",
    description:
      "An embedded commerce analyst, not a generic chatbot. Grounded exclusively in verified store snapshots with structured answers, citations, and next-step actions.",
  },
  {
    icon: Layers,
    badge: "Controlled Execution",
    title: "Sandboxed Action Center",
    description:
      "Transition recommendations from proposed to approved and simulated execution. Full compare-and-swap auditability before touching live channels.",
  },
];

const INTEGRATIONS = [
  { name: "Shopify", status: "Native 2026-07 REST API", badge: "Live Sync" },
  { name: "Meta Ads", status: "Graph API v21.0 OAuth", badge: "Attribution" },
  { name: "Google Ads", status: "API v19 OAuth", badge: "Real-Time ROAS" },
  { name: "MongoDB Atlas", status: "Encrypted Isolated DB", badge: "AES-256" },
  { name: "Groq Cloud", status: "Ultra Low-Latency LPU", badge: "Zero-Fabrication" },
];

const FAQS = [
  {
    q: "How does AHONIX calculate True Profit differently from Shopify Analytics?",
    a: "Shopify reports top-line sales without factoring in variant-specific landed COGS, merchant payment gateway interchange fees, return shipping, and synchronized ad platform spend. AHONIX reconciles all 14 unit variables into deterministic net profit.",
  },
  {
    q: "Does AHONIX require write permissions to my live Shopify store?",
    a: "No. By default, all AHONIX integrations operate under strict read-only scopes. Write actions in the Sandboxed Action Center require explicit manual approval from authorized administrators.",
  },
  {
    q: "How does the Ask AHONIX AI Analyst ensure zero fabrication?",
    a: "The AI analyst is grounded strictly in deterministic JSON snapshot tables computed from your actual store data. It is programmatically prevented from guessing unverified numbers and cites exact timestamped sources for every metric.",
  },
  {
    q: "Can I test AHONIX without connecting my production store?",
    a: "Yes! Every new account can immediately launch the pre-populated 'Northstar Goods' benchmark workspace with complete sales, ad spend, and inventory history.",
  },
];

export default function Landing() {
  const [demoModalOpen, setDemoModalOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeNav, setActiveNav] = useState("home");
  const [annualBilling, setAnnualBilling] = useState(true);
  const [expandedFaq, setExpandedFaq] = useState(null);

  const heroRef = useRef(null);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mq.matches);
    const handler = (e) => setPrefersReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Scroll Spy for Navigation Active Underline
  useEffect(() => {
    const sections = ["home", "loop", "features", "integrations", "pricing", "resources"];
    const handleScroll = () => {
      const scrollPos = window.scrollY + 140;
      for (let i = sections.length - 1; i >= 0; i--) {
        const el = document.getElementById(sections[i]);
        if (el && el.offsetTop <= scrollPos) {
          setActiveNav(sections[i]);
          break;
        }
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (e, id) => {
    e.preventDefault();
    setActiveNav(id);
    setMobileMenuOpen(false);

    if (id === "home") {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }

    const element = document.getElementById(id);
    if (element) {
      const yOffset = -80; // offset for fixed header
      const y = element.getBoundingClientRect().top + window.pageYOffset + yOffset;
      window.scrollTo({ top: y, behavior: "smooth" });
    }
  };

  // Scroll Reactivity
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });

  const scrollWordmarkY = useTransform(scrollYProgress, [0, 1], [0, -120]);
  const scrollCopyY = useTransform(scrollYProgress, [0, 1], [0, -40]);
  const scrollCopyOpacity = useTransform(scrollYProgress, [0, 0.75], [1, 0.35]);

  // Mouse Parallax for Background Wordmark and Copy
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const springConfig = { damping: 32, stiffness: 90, mass: 0.6 };
  const smoothMouseX = useSpring(mouseX, springConfig);
  const smoothMouseY = useSpring(mouseY, springConfig);

  const wordmarkParallaxX = useTransform(smoothMouseX, [-0.5, 0.5], [14, -14]);
  const wordmarkParallaxY = useTransform(smoothMouseY, [-0.5, 0.5], [8, -8]);
  const copyParallaxX = useTransform(smoothMouseX, [-0.5, 0.5], [-6, 6]);

  const handleHeroMouseMove = (e) => {
    if (prefersReducedMotion || !heroRef.current) return;
    const rect = heroRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    mouseX.set(x);
    mouseY.set(y);
  };

  const handleHeroMouseLeave = () => {
    mouseX.set(0);
    mouseY.set(0);
  };

  return (
    <div className="min-h-screen bg-[#040706] text-[#F8FAFC] selection:bg-[#00E599]/30">
      {/* 1. Master Navigation Header */}
      <header className="fixed top-0 inset-x-0 z-50 border-b border-[#16221B]/80 bg-[#040706]/90 backdrop-blur-md">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          {/* Brand Logo */}
          <div onClick={(e) => scrollToSection(e, "home")} className="cursor-pointer">
            <Logo size={28} />
          </div>

          {/* Desktop Navigation Links with animated sliding underline */}
          <nav className="hidden items-center gap-7 md:flex">
            {NAV_LINKS.map((link) => {
              const isActive = activeNav === link.id;
              return (
                <a
                  key={link.id}
                  href={link.href}
                  onClick={(e) => scrollToSection(e, link.id)}
                  className={`relative py-1.5 text-sm font-medium transition-colors ${
                    isActive ? "text-[#F8FAFC]" : "text-[#94A3B8] hover:text-[#F8FAFC]"
                  }`}
                  data-testid={`nav-link-${link.id}`}
                >
                  {link.name}
                  {isActive && (
                    <motion.span
                      layoutId="activeLandingNavIndicator"
                      className="absolute -bottom-2 left-0 right-0 h-[2px] rounded-full bg-[#00E599] shadow-[0_0_10px_rgba(0,229,153,0.8)]"
                      transition={{ type: "spring", stiffness: 380, damping: 30 }}
                    />
                  )}
                </a>
              );
            })}
          </nav>

          {/* Auth Actions */}
          <div className="hidden items-center gap-3 sm:flex">
            <Link
              to="/login"
              className="text-sm font-medium text-[#94A3B8] transition-colors hover:text-[#F8FAFC] px-3 py-2"
              data-testid="landing-login"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="flex items-center gap-2 rounded-full bg-[#00E599] px-5 py-2.5 text-xs font-bold text-[#040706] shadow-lg shadow-[#00E599]/15 transition-all duration-200 hover:bg-[#00c984] hover:scale-[1.02]"
              data-testid="landing-get-started"
            >
              Get Started <ArrowRight size={13} />
            </Link>
          </div>

          {/* Mobile Hamburger Button */}
          <div className="flex items-center gap-2 md:hidden">
            <Link
              to="/register"
              className="rounded-full bg-[#00E599] px-3.5 py-1.5 text-xs font-bold text-[#040706]"
            >
              Start
            </Link>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="rounded-xl border border-[#16221B] bg-[#070C0A] p-2 text-[#94A3B8] hover:text-[#F8FAFC]"
              aria-label="Toggle Navigation"
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="border-b border-[#16221B] bg-[#070C0A] px-6 py-5 md:hidden"
            >
              <div className="flex flex-col space-y-3">
                {NAV_LINKS.map((link) => (
                  <a
                    key={link.id}
                    href={link.href}
                    onClick={(e) => scrollToSection(e, link.id)}
                    className={`flex items-center justify-between rounded-xl px-4 py-3 text-sm font-medium transition-colors ${
                      activeNav === link.id
                        ? "bg-[#0B1410] text-[#00E599] font-bold border border-[#00E599]/20"
                        : "text-[#94A3B8] hover:bg-[#0B110E] hover:text-[#F8FAFC]"
                    }`}
                  >
                    <span>{link.name}</span>
                    {activeNav === link.id && <span className="h-1.5 w-1.5 rounded-full bg-[#00E599]" />}
                  </a>
                ))}
                <div className="mt-4 flex flex-col gap-2 pt-3 border-t border-[#16221B]">
                  <Link
                    to="/login"
                    className="flex w-full items-center justify-center rounded-xl border border-[#16221B] bg-[#0B110E] py-3 text-xs font-semibold text-[#F8FAFC]"
                  >
                    Sign In to Workspace
                  </Link>
                  <Link
                    to="/register"
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#00E599] py-3 text-xs font-bold text-[#040706]"
                  >
                    Create Free Workspace <ArrowRight size={13} />
                  </Link>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* 2. Hero Section: ADAPTIVE DUAL-VIEWPORT CANVAS */}
      <section
        id="home"
        ref={heroRef}
        onMouseMove={handleHeroMouseMove}
        onMouseLeave={handleHeroMouseLeave}
        className="relative w-full overflow-hidden bg-[#040706] pt-24 pb-14 sm:pt-28 sm:pb-20 lg:py-0 lg:h-screen lg:min-h-[740px] lg:max-h-[1050px] lg:flex lg:items-center"
      >
        {/* Layer 1: Volumetric Spotlight Beam from top-right */}
        <div
          className="pointer-events-none absolute -right-[10vw] -top-32 h-[800px] w-[80vw] opacity-35 mix-blend-screen transition-opacity duration-700"
          style={{
            background:
              "linear-gradient(215deg, rgba(0, 229, 153, 0.22) 0%, rgba(13, 30, 22, 0.12) 45%, transparent 75%)",
            filter: "blur(60px)",
          }}
          aria-hidden="true"
        />

        {/* Layer 2: Polished Floor Reflection Horizon */}
        <div
          className="pointer-events-none absolute bottom-0 left-0 right-0 h-44 opacity-80"
          style={{
            background:
              "radial-gradient(ellipse at 50% 100%, rgba(0, 229, 153, 0.12) 0%, rgba(7, 12, 10, 0.9) 55%, transparent 85%)",
          }}
          aria-hidden="true"
        />

        {/* Layer 3: Giant Architectural Real HTML Wordmark: A H O N I X */}
        <motion.div
          style={{
            x: prefersReducedMotion ? 0 : wordmarkParallaxX,
            y: prefersReducedMotion ? 0 : wordmarkParallaxY,
            translateY: prefersReducedMotion ? 0 : scrollWordmarkY,
          }}
          className="pointer-events-none absolute inset-x-0 top-[20%] sm:top-[24%] lg:top-[38%] -translate-y-1/2 z-10 text-center select-none overflow-hidden"
          aria-hidden="true"
        >
          <span
            className="font-display block text-[21vw] sm:text-[19vw] lg:text-[18vw] font-black tracking-[0.16em] select-none text-transparent leading-none"
            style={{
              WebkitTextStroke: "1px rgba(255, 255, 255, 0.08)",
              background:
                "linear-gradient(180deg, rgba(255, 255, 255, 0.16) 0%, rgba(0, 229, 153, 0.07) 35%, rgba(4, 7, 6, 0.01) 100%)",
              WebkitBackgroundClip: "text",
              filter: "drop-shadow(0 20px 40px rgba(0,0,0,0.95))",
            }}
          >
            AHONIX
          </span>
        </motion.div>

        {/* Layer 4: Desktop Integrated 3D Sculptural "A" Emblem */}
        <div className="pointer-events-none absolute right-[1vw] sm:right-[4vw] lg:right-[8vw] xl:right-[11vw] bottom-[-20px] sm:bottom-0 lg:bottom-[2vh] w-[290px] sm:w-[440px] md:w-[540px] lg:w-[680px] xl:w-[780px] z-20 opacity-80 sm:opacity-95 lg:opacity-100 hidden lg:block">
          <Hero3DScene scrollYProgress={scrollYProgress} />
        </div>

        {/* Layer 5: Foreground Editorial Content & Mobile Composition */}
        <div className="relative z-30 mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            style={{
              x: prefersReducedMotion ? 0 : copyParallaxX,
              y: prefersReducedMotion ? 0 : scrollCopyY,
              opacity: prefersReducedMotion ? 1 : scrollCopyOpacity,
            }}
            className="max-w-xl lg:max-w-2xl"
          >
            {/* Eyebrow badge with clean emerald dash */}
            <div className="mb-4 sm:mb-6 inline-flex items-center gap-2.5 sm:gap-3">
              <span className="font-mono text-[11px] sm:text-xs font-semibold tracking-[0.2em] text-[#94A3B8] uppercase">
                AI COMMERCE OS
              </span>
              <span className="h-[2px] w-6 sm:w-8 rounded-full bg-[#00E599]" />
            </div>

            {/* Main Headline */}
            <h1 className="font-display text-3xl sm:text-5xl lg:text-[3.75rem] font-extrabold tracking-tight text-[#F8FAFC] leading-[1.15] lg:leading-[1.1]">
              Turn Your Commerce <br />
              Into <span className="text-[#00E599]">Real Profit</span>
            </h1>

            {/* Supporting Copy */}
            <p className="mt-3 sm:mt-5 max-w-lg text-xs sm:text-base leading-relaxed text-[#94A3B8] lg:text-lg">
              AHONIX is your AI-powered commerce operating system. Connect your
              data, get real insights, and take action — all in one place.
            </p>

            {/* Real CTA Action Buttons */}
            <div className="mt-6 sm:mt-8 flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4">
              <Link
                to="/register"
                className="flex items-center justify-center gap-2.5 rounded-full bg-[#00E599] px-6 sm:px-7 py-3.5 text-xs font-bold text-[#040706] shadow-xl shadow-[#00E599]/20 transition-all duration-200 hover:bg-[#00c984] hover:scale-[1.02]"
                data-testid="hero-cta"
              >
                Explore AHONIX <ArrowRight size={14} />
              </Link>
              <button
                onClick={() => setDemoModalOpen(true)}
                className="flex items-center justify-center gap-2.5 rounded-full border border-[#16221B] bg-[#070C0A] px-5 sm:px-6 py-3.5 text-xs font-semibold text-[#F8FAFC] transition-all duration-200 hover:border-[#1F3327] hover:bg-[#0B110E]"
                data-testid="hero-demo-btn"
              >
                <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[#00E599]/15 text-[#00E599]">
                  <Play size={9} className="ml-0.5 fill-[#00E599]" />
                </div>
                Watch Demo
              </button>
            </div>

            {/* Trust micro-badges */}
            <div className="mt-6 sm:mt-10 flex flex-wrap items-center gap-4 sm:gap-6 border-t border-[#16221B] pt-4 sm:pt-6 text-[11px] sm:text-xs text-[#64748B]">
              <span className="flex items-center gap-1.5">
                <CheckCircle2 size={13} className="text-[#00E599]" /> No credit card needed
              </span>
              <span className="flex items-center gap-1.5">
                <ShieldCheck size={13} className="text-[#00E599]" /> Read-only sync security
              </span>
            </div>
          </motion.div>

          {/* Layer 4b: Mobile Sculptural 3D Showcase (Centered & Volumetric) */}
          <div className="relative mt-8 sm:mt-10 mx-auto flex flex-col items-center justify-center lg:hidden">
            <div className="pointer-events-none absolute h-60 w-60 rounded-full bg-[#00E599]/15 blur-3xl" />
            <div className="relative w-[260px] sm:w-[340px]">
              <Hero3DScene scrollYProgress={scrollYProgress} />
            </div>
            {/* Live Telemetry Badge below 3D Emblem on Mobile */}
            <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-[#16221B] bg-[#070C0A]/90 px-3.5 py-1.5 shadow-xl backdrop-blur-md">
              <span className="h-2 w-2 rounded-full bg-[#00E599] animate-pulse" />
              <span className="font-mono text-[10px] font-medium text-[#CBD5E1]">
                99.9% Margin Accuracy · Real Telemetry
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* 3. The 9-Stage Continuous Closed-Loop Optimization — 3D SCROLL REVEAL */}
      <section id="loop" className="relative border-y border-[#16221B] bg-[#070C0A] py-14 sm:py-24 overflow-hidden scroll-mt-20">
        {/* Ambient background glow */}
        <div
          className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-[500px] w-[800px] rounded-full opacity-15"
          style={{
            background: "radial-gradient(circle, #00E599 0%, transparent 70%)",
            filter: "blur(90px)",
          }}
          aria-hidden="true"
        />

        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {/* Section Header */}
          <div className="text-center max-w-3xl mx-auto mb-10 sm:mb-16">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#16221B] bg-[#0B1410] px-3.5 sm:px-4 py-1.5 text-[11px] sm:text-xs font-semibold text-[#00E599] mb-3 sm:mb-4">
              <Sparkles size={13} />
              <span>CONTINUOUS CLOSED-LOOP OPTIMIZATION</span>
            </div>
            <h2 className="font-display text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-[#F8FAFC]">
              9 Synchronized Stages. <br className="hidden sm:inline" />
              <span className="text-[#00E599]">Zero Financial Guesswork.</span>
            </h2>
            <p className="mt-3 sm:mt-4 text-xs sm:text-base text-[#94A3B8] leading-relaxed">
              AHONIX doesn't just present passive reporting. Every transaction, order, and ad impression
              flows continuously through our deterministic closed-loop operating sequence.
            </p>
          </div>

          {/* 3D Staggered Cascade Grid with Perspective */}
          <div className="[perspective:1200px] grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-7">
            {LOOP_STAGES.map((stage, idx) => {
              const Icon = stage.icon;
              return (
                <motion.div
                  key={stage.step}
                  initial={{ opacity: 0, y: 35, rotateX: 14, scale: 0.96 }}
                  whileInView={{ opacity: 1, y: 0, rotateX: 0, scale: 1 }}
                  viewport={{ once: true, amount: 0.1 }}
                  transition={{
                    duration: 0.5,
                    delay: (idx % 3) * 0.08,
                    ease: [0.16, 1, 0.3, 1],
                  }}
                  className="group relative flex flex-col justify-between rounded-2xl border border-[#16221B] bg-gradient-to-b from-[#0B130F] to-[#070C0A] p-5 sm:p-7 shadow-xl shadow-black/40 transition-all duration-300 hover:border-[#00E599]/50 hover:shadow-[0_20px_35px_-10px_rgba(0,229,153,0.15)] hover:-translate-y-1"
                >
                  {/* Subtle top reflection rim */}
                  <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#00E599]/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

                  <div>
                    {/* Top Header with Step Badge and Tag */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#00E599]/30 bg-[#00E599]/10 font-mono text-xs font-bold text-[#00E599] shadow-inner">
                          {stage.step}
                        </span>
                        <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#16221B] bg-[#040706] text-[#94A3B8] transition-colors group-hover:text-[#00E599]">
                          <Icon size={16} />
                        </div>
                      </div>
                      <span className="font-mono text-[10px] font-semibold tracking-wider text-[#64748B] uppercase">
                        {stage.tag}
                      </span>
                    </div>

                    {/* Step Title & Subtitle */}
                    <div className="mt-5">
                      <span className="text-xs font-semibold text-[#00E599]">
                        {stage.sub}
                      </span>
                      <h3 className="mt-1 font-display text-lg sm:text-xl font-bold text-[#F8FAFC] group-hover:text-white transition-colors">
                        {stage.name}
                      </h3>
                      <p className="mt-2 text-xs leading-relaxed text-[#94A3B8]">
                        {stage.desc}
                      </p>
                    </div>
                  </div>

                  {/* Bottom Connection Arrow / Indicator */}
                  <div className="mt-5 sm:mt-6 flex items-center justify-between border-t border-[#16221B] pt-3.5 sm:pt-4 text-xs text-[#64748B]">
                    <span className="font-mono text-[11px] text-[#475569]">
                      Stage {idx + 1} of 9
                    </span>
                    {idx < LOOP_STAGES.length - 1 ? (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-[#00E599]/80 group-hover:text-[#00E599] transition-colors">
                        To {LOOP_STAGES[idx + 1].name} →
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-[#00E599]">
                        Loop Closes ↺
                      </span>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* 4. Core Pillars / Architecture */}
      <section id="features" className="py-14 sm:py-24 relative scroll-mt-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl">
            <span className="font-mono text-[11px] sm:text-xs font-semibold tracking-[0.25em] text-[#00E599] uppercase">
              Engineered For Financial Clarity
            </span>
            <h2 className="mt-2 sm:mt-3 font-display text-2xl sm:text-4xl font-extrabold tracking-tight text-[#F8FAFC]">
              Precision Systems. Not Speculation.
            </h2>
            <p className="mt-3 sm:mt-4 text-xs sm:text-base text-[#94A3B8]">
              Modern commerce tech stacks fragment your numbers. AHONIX delivers
              single-pane deterministic reconciliation.
            </p>
          </div>

          <div className="mt-10 sm:mt-16 grid gap-4 sm:gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {PILLARS.map((pillar) => {
              const Icon = pillar.icon;
              return (
                <div
                  key={pillar.title}
                  className="group relative rounded-2xl border border-[#16221B] bg-[#070C0A] p-5 sm:p-7 transition-all duration-300 hover:border-[#1F3327] hover:bg-[#0B110E]"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex h-10 w-10 sm:h-11 sm:w-11 items-center justify-center rounded-xl border border-[#00E599]/25 bg-[#00E599]/10 text-[#00E599] transition-transform duration-300 group-hover:scale-105">
                      <Icon size={18} />
                    </div>
                    <span className="font-mono text-[10px] font-semibold tracking-wider text-[#64748B] uppercase">
                      {pillar.badge}
                    </span>
                  </div>

                  <h3 className="mt-5 sm:mt-6 font-display text-base sm:text-lg font-bold text-[#F8FAFC]">
                    {pillar.title}
                  </h3>
                  <p className="mt-2 sm:mt-3 text-xs leading-relaxed text-[#94A3B8]">
                    {pillar.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* 5. Enterprise Integrations Strip */}
      <section
        id="integrations"
        className="border-t border-[#16221B] bg-[#070C0A] py-12 sm:py-16 relative scroll-mt-20"
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-start justify-between gap-4 md:flex-row md:items-center">
            <div>
              <p className="font-mono text-[11px] sm:text-xs font-semibold tracking-[0.2em] text-[#00E599] uppercase">
                Zero-Fabrication Data Connectors
              </p>
              <h3 className="mt-1 font-display text-xl sm:text-2xl font-bold text-[#F8FAFC]">
                Native API Ingestion. Cryptographic Isolation.
              </h3>
            </div>
            <Link
              to="/settings"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#00E599] hover:underline"
            >
              View Connector Architecture <ArrowRight size={13} />
            </Link>
          </div>

          <div className="mt-6 sm:mt-8 grid grid-cols-2 gap-3 sm:gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {INTEGRATIONS.map((it) => (
              <div
                key={it.name}
                className="flex flex-col rounded-xl border border-[#16221B] bg-[#0B110E] p-3.5 sm:p-4 transition-colors hover:border-[#1F3327]"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs sm:text-sm font-bold text-[#F8FAFC]">
                    {it.name}
                  </span>
                  <span className="rounded-md bg-[#00E599]/10 px-1.5 py-0.5 font-mono text-[9px] font-semibold text-[#00E599]">
                    {it.badge}
                  </span>
                </div>
                <span className="mt-2 font-mono text-[10px] sm:text-[11px] text-[#64748B]">
                  {it.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 6. Pricing Section */}
      <section id="pricing" className="border-t border-[#16221B] bg-[#040706] py-14 sm:py-24 relative scroll-mt-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {/* Section Header */}
          <div className="text-center max-w-3xl mx-auto">
            <span className="font-mono text-[11px] sm:text-xs font-semibold tracking-[0.25em] text-[#00E599] uppercase">
              Predictable Commerce Economics
            </span>
            <h2 className="mt-2 sm:mt-3 font-display text-2xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-[#F8FAFC]">
              Transparent Investment. <br />
              <span className="text-[#00E599]">Exponential Real Profit.</span>
            </h2>
            <p className="mt-3 sm:mt-4 text-xs sm:text-base text-[#94A3B8]">
              No percentage take-rates on your GMV. Zero hidden connector surcharge fees.
              Pay only for continuous algorithmic optimization.
            </p>

            {/* Monthly / Annual Switch */}
            <div className="mt-6 sm:mt-8 inline-flex items-center rounded-full border border-[#16221B] bg-[#070C0A] p-1">
              <button
                onClick={() => setAnnualBilling(false)}
                className={`rounded-full px-4 sm:px-5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold transition-colors ${
                  !annualBilling
                    ? "bg-[#00E599] text-[#040706] shadow-sm"
                    : "text-[#94A3B8] hover:text-white"
                }`}
              >
                Monthly Billing
              </button>
              <button
                onClick={() => setAnnualBilling(true)}
                className={`flex items-center gap-1.5 sm:gap-2 rounded-full px-4 sm:px-5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold transition-colors ${
                  annualBilling
                    ? "bg-[#00E599] text-[#040706] shadow-sm"
                    : "text-[#94A3B8] hover:text-white"
                }`}
              >
                <span>Annual Billing</span>
                <span className="rounded-full bg-[#070C0A] px-1.5 sm:px-2 py-0.5 font-mono text-[9px] text-[#00E599]">
                  SAVE 20%
                </span>
              </button>
            </div>
          </div>

          {/* Pricing Cards Grid */}
          <div className="mt-10 sm:mt-16 grid grid-cols-1 gap-6 sm:gap-8 lg:grid-cols-3">
            {/* Starter Tier */}
            <div className="flex flex-col justify-between rounded-2xl sm:rounded-3xl border border-[#16221B] bg-[#070C0A] p-6 sm:p-8 transition-all hover:border-[#1F3327]">
              <div>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold uppercase text-[#94A3B8]">
                    Starter
                  </span>
                  <span className="rounded-full border border-[#16221B] bg-[#0B110E] px-3 py-1 font-mono text-[10px] text-[#94A3B8]">
                    Growing Brands
                  </span>
                </div>
                <h3 className="mt-4 font-display text-xl sm:text-2xl font-bold text-[#F8FAFC]">
                  Direct-to-Consumer
                </h3>
                <p className="mt-2 text-xs text-[#94A3B8]">
                  For emerging brands scaling past $20k monthly GMV seeking true net profit visibility.
                </p>

                <div className="mt-5 sm:mt-6 flex items-baseline gap-1">
                  <span className="font-display text-3xl sm:text-4xl font-extrabold text-[#F8FAFC]">
                    ${annualBilling ? "39" : "49"}
                  </span>
                  <span className="text-xs text-[#64748B]">/ month</span>
                </div>

                <div className="mt-6 sm:mt-8 space-y-3 border-t border-[#16221B] pt-5 sm:pt-6">
                  {[
                    "1 Shopify Store Connection",
                    "Daily True Profit & Unit Margin Sync",
                    "Meta & Google Ads Sync",
                    "Core Margin Leak Sentinel",
                    "Email & Discord Alerts",
                    "Standard 24h Response SLA",
                  ].map((feat) => (
                    <div key={feat} className="flex items-center gap-2.5 text-xs text-[#CBD5E1]">
                      <Check size={14} className="text-[#00E599] shrink-0" />
                      <span>{feat}</span>
                    </div>
                  ))}
                </div>
              </div>

              <Link
                to="/register"
                className="mt-6 sm:mt-8 block w-full rounded-full border border-[#16221B] bg-[#0B110E] py-3 text-center text-xs font-bold text-[#F8FAFC] transition-colors hover:border-[#00E599]/40 hover:bg-[#0F1A14]"
              >
                Start 14-Day Free Trial
              </Link>
            </div>

            {/* Growth Tier (Featured) */}
            <div className="relative flex flex-col justify-between rounded-2xl sm:rounded-3xl border-2 border-[#00E599] bg-[#08120D] p-6 sm:p-8 shadow-2xl shadow-[#00E599]/10">
              <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-[#00E599] px-4 py-1 text-[10px] font-black uppercase tracking-wider text-[#040706]">
                Most Popular
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold uppercase text-[#00E599]">
                    Growth
                  </span>
                  <span className="rounded-full bg-[#00E599]/15 px-3 py-1 font-mono text-[10px] font-bold text-[#00E599]">
                    Scale Operators
                  </span>
                </div>
                <h3 className="mt-4 font-display text-xl sm:text-2xl font-bold text-[#F8FAFC]">
                  Commerce Scale
                </h3>
                <p className="mt-2 text-xs text-[#CBD5E1]">
                  For high-growth omnichannel brands managing up to $500k monthly GMV.
                </p>

                <div className="mt-5 sm:mt-6 flex items-baseline gap-1">
                  <span className="font-display text-3xl sm:text-4xl font-extrabold text-[#F8FAFC]">
                    ${annualBilling ? "159" : "199"}
                  </span>
                  <span className="text-xs text-[#94A3B8]">/ month</span>
                </div>

                <div className="mt-6 sm:mt-8 space-y-3 border-t border-[#16221B] pt-5 sm:pt-6">
                  {[
                    "Up to 3 Stores / Multi-Brand Support",
                    "Real-Time Hourly True Profit Telemetry",
                    "Sandboxed Action Center & Simulation",
                    "Ask AHONIX AI Commerce Analyst (Groq)",
                    "SKU-Level Unit Margin & COGS Overrides",
                    "Multi-Touch Ad Attribution Modeling",
                    "Priority Engineering Support",
                  ].map((feat) => (
                    <div key={feat} className="flex items-center gap-2.5 text-xs text-[#F8FAFC]">
                      <Check size={14} className="text-[#00E599] shrink-0" />
                      <span className="font-medium">{feat}</span>
                    </div>
                  ))}
                </div>
              </div>

              <Link
                to="/register"
                className="mt-6 sm:mt-8 block w-full rounded-full bg-[#00E599] py-3.5 text-center text-xs font-bold text-[#040706] shadow-lg shadow-[#00E599]/20 transition-all hover:bg-[#00c984] hover:scale-[1.02]"
              >
                Start 14-Day Free Trial →
              </Link>
            </div>

            {/* Enterprise Tier */}
            <div className="flex flex-col justify-between rounded-2xl sm:rounded-3xl border border-[#16221B] bg-[#070C0A] p-6 sm:p-8 transition-all hover:border-[#1F3327]">
              <div>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold uppercase text-[#94A3B8]">
                    Enterprise
                  </span>
                  <span className="rounded-full border border-[#16221B] bg-[#0B110E] px-3 py-1 font-mono text-[10px] text-[#94A3B8]">
                    Conglomerates
                  </span>
                </div>
                <h3 className="mt-4 font-display text-xl sm:text-2xl font-bold text-[#F8FAFC]">
                  High Volume Operations
                </h3>
                <p className="mt-2 text-xs text-[#94A3B8]">
                  For high-scale multi-brand conglomerates requiring custom ERP ingestion and dedicated SLAs.
                </p>

                <div className="mt-5 sm:mt-6 flex items-baseline gap-1">
                  <span className="font-display text-3xl sm:text-4xl font-extrabold text-[#F8FAFC]">
                    ${annualBilling ? "399" : "499"}
                  </span>
                  <span className="text-xs text-[#64748B]">/ month</span>
                </div>

                <div className="mt-6 sm:mt-8 space-y-3 border-t border-[#16221B] pt-5 sm:pt-6">
                  {[
                    "Unlimited Stores & Custom Warehouses",
                    "Sub-Minute Real-Time Streaming Ingestion",
                    "Custom ERP, WMS & 3PL Ingestion Connectors",
                    "Dedicated Private LLM Inference Instance",
                    "Predictive Simulation Algorithm Custom Tuning",
                    "Dedicated Solutions Architect & SLA",
                    "SOC-2 Type II Compliance Export",
                  ].map((feat) => (
                    <div key={feat} className="flex items-center gap-2.5 text-xs text-[#CBD5E1]">
                      <Check size={14} className="text-[#00E599] shrink-0" />
                      <span>{feat}</span>
                    </div>
                  ))}
                </div>
              </div>

              <Link
                to="/register"
                className="mt-6 sm:mt-8 block w-full rounded-full border border-[#16221B] bg-[#0B110E] py-3 text-center text-xs font-bold text-[#F8FAFC] transition-colors hover:border-[#00E599]/40 hover:bg-[#0F1A14]"
              >
                Launch Enterprise Sandbox
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 7. Resources & FAQ Section */}
      <section id="resources" className="border-t border-[#16221B] bg-[#070C0A] py-14 sm:py-24 relative scroll-mt-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl">
            <span className="font-mono text-[11px] sm:text-xs font-semibold tracking-[0.25em] text-[#00E599] uppercase">
              Knowledge Base & Architecture
            </span>
            <h2 className="mt-2 sm:mt-3 font-display text-2xl sm:text-4xl font-extrabold tracking-tight text-[#F8FAFC]">
              Everything You Need to Master Commerce Operations
            </h2>
            <p className="mt-3 sm:mt-4 text-xs sm:text-base text-[#94A3B8]">
              Deep-dive documentation, verified case benchmarks, and architectural technical whitepapers.
            </p>
          </div>

          {/* 4 Resource Cards */}
          <div className="mt-8 sm:mt-12 grid grid-cols-1 gap-4 sm:gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-[#16221B] bg-[#0B110E] p-5 sm:p-6 transition-colors hover:border-[#00E599]/40">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#00E599]/10 text-[#00E599] border border-[#00E599]/20">
                <FileText size={18} />
              </div>
              <h4 className="mt-4 font-display text-sm sm:text-base font-bold text-[#F8FAFC]">
                API & Connector Docs
              </h4>
              <p className="mt-2 text-xs leading-relaxed text-[#94A3B8]">
                Technical specifications for Shopify REST, Meta Graph API v21, and isolated token vaults.
              </p>
              <Link to="/settings" className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-[#00E599] hover:underline">
                Explore docs <ArrowUpRight size={13} />
              </Link>
            </div>

            <div className="rounded-2xl border border-[#16221B] bg-[#0B110E] p-5 sm:p-6 transition-colors hover:border-[#00E599]/40">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#00E599]/10 text-[#00E599] border border-[#00E599]/20">
                <TrendingUp size={18} />
              </div>
              <h4 className="mt-4 font-display text-sm sm:text-base font-bold text-[#F8FAFC]">
                The True Profit Playbook
              </h4>
              <p className="mt-2 text-xs leading-relaxed text-[#94A3B8]">
                Why ROAS is misleading modern merchants, and how contribution margin 3 reclaims net EBITDA.
              </p>
              <Link to="/register" className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-[#00E599] hover:underline">
                Read methodology <ArrowUpRight size={13} />
              </Link>
            </div>

            <div className="rounded-2xl border border-[#16221B] bg-[#0B110E] p-5 sm:p-6 transition-colors hover:border-[#00E599]/40">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#00E599]/10 text-[#00E599] border border-[#00E599]/20">
                <Cpu size={18} />
              </div>
              <h4 className="mt-4 font-display text-sm sm:text-base font-bold text-[#F8FAFC]">
                Groq LPU Reasoning
              </h4>
              <p className="mt-2 text-xs leading-relaxed text-[#94A3B8]">
                How zero-fabrication architecture and low-latency token streaming power Ask AHONIX.
              </p>
              <Link to="/register" className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-[#00E599] hover:underline">
                Whitepaper <ArrowUpRight size={13} />
              </Link>
            </div>

            <div className="rounded-2xl border border-[#16221B] bg-[#0B110E] p-5 sm:p-6 transition-colors hover:border-[#00E599]/40">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#00E599]/10 text-[#00E599] border border-[#00E599]/20">
                <Compass size={18} />
              </div>
              <h4 className="mt-4 font-display text-sm sm:text-base font-bold text-[#F8FAFC]">
                Northstar Goods Demo
              </h4>
              <p className="mt-2 text-xs leading-relaxed text-[#94A3B8]">
                Instant exploratory access pre-loaded with realistic DTC orders, ad attribution, and stock alerts.
              </p>
              <Link to="/register" className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-[#00E599] hover:underline">
                Launch sandbox <ArrowUpRight size={13} />
              </Link>
            </div>
          </div>

          {/* Interactive FAQ Accordion */}
          <div className="mt-12 sm:mt-16 max-w-3xl">
            <h3 className="font-display text-lg sm:text-xl font-bold text-[#F8FAFC] mb-4 sm:mb-6 flex items-center gap-2">
              <HelpCircle size={18} className="text-[#00E599]" />
              Frequently Asked Questions
            </h3>
            <div className="space-y-2.5 sm:space-y-3">
              {FAQS.map((faq, i) => (
                <div
                  key={faq.q}
                  className="rounded-xl sm:rounded-2xl border border-[#16221B] bg-[#0B110E] overflow-hidden transition-colors hover:border-[#1F3327]"
                >
                  <button
                    onClick={() => setExpandedFaq(expandedFaq === i ? null : i)}
                    className="flex w-full items-center justify-between p-4 sm:p-5 text-left text-xs sm:text-sm font-semibold text-[#F8FAFC]"
                  >
                    <span>{faq.q}</span>
                    <ChevronDown
                      size={16}
                      className={`shrink-0 ml-2 text-[#94A3B8] transition-transform duration-200 ${
                        expandedFaq === i ? "rotate-180 text-[#00E599]" : ""
                      }`}
                    />
                  </button>
                  {expandedFaq === i && (
                    <div className="px-4 sm:px-5 pb-4 sm:pb-5 pt-1 text-xs leading-relaxed text-[#94A3B8] border-t border-[#16221B]/50">
                      {faq.a}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* 8. Sandbox Demo Evaluation Banner */}
      <section className="border-t border-[#16221B] py-14 sm:py-20">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 text-center lg:px-8">
          <div className="rounded-2xl sm:rounded-3xl border border-[#16221B] bg-[#070C0A] p-6 sm:p-14 relative overflow-hidden">
            <div
              className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full opacity-20"
              style={{
                background: "radial-gradient(circle, #00E599 0%, transparent 70%)",
              }}
              aria-hidden="true"
            />
            <span className="font-mono text-[11px] sm:text-xs font-semibold tracking-[0.25em] text-[#00E599] uppercase">
              Immediate Evaluation
            </span>
            <h2 className="mt-2 sm:mt-3 font-display text-xl sm:text-3xl lg:text-4xl font-extrabold text-[#F8FAFC]">
              Experience AHONIX With Real Benchmark Data
            </h2>
            <p className="mx-auto mt-3 sm:mt-4 max-w-xl text-xs sm:text-sm leading-relaxed text-[#94A3B8]">
              No integrations or store credentials needed. Launch into our pre-loaded
              Northstar Goods workspace and test True Profit reconciliation live.
            </p>
            <div className="mt-6 sm:mt-8 flex flex-col sm:flex-row justify-center gap-3 sm:gap-4">
              <Link
                to="/register"
                className="rounded-full bg-[#00E599] px-7 py-3.5 text-xs font-bold text-[#040706] shadow-lg shadow-[#00E599]/20 transition-all hover:bg-[#00c984] hover:scale-[1.02]"
              >
                Launch Demo Workspace →
              </Link>
              <Link
                to="/login"
                className="rounded-full border border-[#16221B] bg-[#0B110E] px-7 py-3.5 text-xs font-semibold text-[#F8FAFC] transition-all hover:border-[#1F3327]"
              >
                Sign In to Existing Tenant
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 9. Refined Editorial Footer */}
      <footer className="border-t border-[#16221B] bg-[#040706] py-10 sm:py-12 text-xs text-[#64748B]">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-5 sm:gap-6 px-4 sm:px-6 sm:flex-row lg:px-8">
          <Logo size={24} />
          <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6">
            <a href="#features" onClick={(e) => scrollToSection(e, "features")} className="hover:text-[#F8FAFC] transition-colors">
              Features
            </a>
            <a href="#integrations" onClick={(e) => scrollToSection(e, "integrations")} className="hover:text-[#F8FAFC] transition-colors">
              Integrations
            </a>
            <a href="#pricing" onClick={(e) => scrollToSection(e, "pricing")} className="hover:text-[#F8FAFC] transition-colors">
              Pricing
            </a>
            <a href="#resources" onClick={(e) => scrollToSection(e, "resources")} className="hover:text-[#F8FAFC] transition-colors">
              Resources
            </a>
            <Link to="/privacy" className="hover:text-[#F8FAFC] transition-colors">
              Privacy Policy
            </Link>
            <Link to="/terms" className="hover:text-[#F8FAFC] transition-colors">
              Terms of Service
            </Link>
          </div>
          <p>© 2026 AHONIX. The AI Commerce Operating System.</p>
        </div>
      </footer>

      {/* 10. Interactive Demo Walkthrough Modal */}
      {demoModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in"
          onClick={() => setDemoModalOpen(false)}
        >
          <div
            className="relative w-full max-w-2xl rounded-2xl border border-[#16221B] bg-[#070C0A] p-6 sm:p-8 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setDemoModalOpen(false)}
              className="absolute right-5 top-5 rounded-lg border border-[#16221B] bg-[#0B110E] p-1.5 text-[#94A3B8] hover:text-white"
              aria-label="Close demo modal"
            >
              <X size={16} />
            </button>

            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#00E599]/15 text-[#00E599] border border-[#00E599]/30">
                <Compass size={18} />
              </span>
              <div>
                <h3 className="font-display text-lg font-bold text-[#F8FAFC]">
                  AHONIX Interactive Product Walkthrough
                </h3>
                <p className="text-xs text-[#94A3B8]">
                  Explore the unified command center with simulated merchant data.
                </p>
              </div>
            </div>

            <div className="mt-6 space-y-3">
              <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#F8FAFC]">
                    1. True Net Profit Terminal
                  </span>
                  <span className="text-[10px] text-[#00E599] font-mono">
                    Zero Guessed Numbers
                  </span>
                </div>
                <p className="mt-1.5 text-xs text-[#94A3B8]">
                  Reconciles Shopify order GMV against product-level COGS, payment gateway fees, and Meta / Google Ads spend in real-time.
                </p>
              </div>

              <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#F8FAFC]">
                    2. Sandboxed Action Center
                  </span>
                  <span className="text-[10px] text-[#D4AF37] font-mono">
                    Safe Simulations
                  </span>
                </div>
                <p className="mt-1.5 text-xs text-[#94A3B8]">
                  Audit and simulate the exact financial impact of restocking or budget reallocations before committing live capital.
                </p>
              </div>

              <div className="rounded-xl border border-[#16221B] bg-[#0B110E] p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#F8FAFC]">
                    3. Ask AHONIX Commerce Analyst
                  </span>
                  <span className="text-[10px] text-sky-400 font-mono">
                    Groq Low-Latency Reasoning
                  </span>
                </div>
                <p className="mt-1.5 text-xs text-[#94A3B8]">
                  An embedded institutional analyst grounded strictly in store snapshots with structured citations and verifiable telemetry.
                </p>
              </div>
            </div>

            <div className="mt-8 flex items-center justify-end gap-3 border-t border-[#16221B] pt-5">
              <button
                onClick={() => setDemoModalOpen(false)}
                className="rounded-xl border border-[#16221B] bg-[#0B110E] px-4 py-2 text-xs font-medium text-[#94A3B8] hover:text-[#F8FAFC]"
              >
                Close
              </button>
              <Link
                to="/register"
                className="rounded-xl bg-[#00E599] px-5 py-2 text-xs font-bold text-[#040706] hover:bg-[#00c984] shadow-md shadow-[#00E599]/20"
              >
                Enter Demo Workspace →
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

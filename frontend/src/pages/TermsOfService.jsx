import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import {
  FileText,
  ArrowLeft,
  ShieldAlert,
  HelpCircle,
  TrendingUp,
  Layers,
  Lock,
  Mail,
  CheckCircle2,
} from "lucide-react";
import { Logo } from "@/components/Logo";

export default function TermsOfService() {
  useEffect(() => {
    document.title = "Terms of Service — AHONIX | The AI Commerce OS";
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="min-h-screen bg-[#040706] text-[#F8FAFC]">
      {/* Top Navigation */}
      <header className="sticky top-0 z-30 border-b border-[#16221B] bg-[#040706]/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
          <Link to="/" className="flex items-center gap-3 transition-opacity hover:opacity-90">
            <Logo size={24} />
          </Link>
          <div className="flex items-center gap-4">
            <Link
              to="/privacy"
              className="text-xs font-medium text-[#94A3B8] transition-colors hover:text-[#F8FAFC]"
            >
              Privacy Policy
            </Link>
            <Link
              to="/login"
              className="flex items-center gap-1.5 rounded-lg border border-[#16221B] bg-[#070C0A] px-3.5 py-1.5 text-xs font-semibold text-[#F8FAFC] transition-colors hover:bg-[#0B110E]"
            >
              Sign In
            </Link>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="mx-auto max-w-4xl px-6 py-12 sm:py-16">
        {/* Back link */}
        <Link
          to="/"
          className="mb-8 inline-flex items-center gap-2 text-xs font-medium text-[#64748B] transition-colors hover:text-[#00E599]"
        >
          <ArrowLeft size={14} /> Back to AHONIX Home
        </Link>

        {/* Title Header */}
        <div className="mb-12 border-b border-[#16221B] pb-8">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3.5 py-1 text-xs font-medium text-[#00E599]">
            <FileText size={14} /> Merchant Terms & Agreement
          </div>
          <h1 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl text-[#F8FAFC]">
            Terms of Service
          </h1>
          <p className="mt-3 text-sm text-[#94A3B8]">
            Effective Date: <span className="font-medium text-[#F8FAFC]">September 14, 2026</span> · Version 2.1
          </p>
          <p className="mt-4 text-base leading-relaxed text-[#CBD5E1]">
            These Terms of Service ("Terms") constitute a legally binding agreement between you (or the merchant entity you represent)
            and AHONIX ("AHONIX", "we", "our", or "us"). By creating an account, accessing, or using the AHONIX AI Commerce
            Operating System, you agree to be bound by these Terms.
          </p>
        </div>

        {/* Notice Callout */}
        <div className="mb-10 rounded-2xl border border-emerald-500/30 bg-emerald-950/20 p-5 sm:p-6">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-emerald-500/20 p-2 text-[#00E599]">
              <ShieldAlert size={22} />
            </div>
            <div>
              <h2 className="text-base font-bold text-emerald-300">
                Merchant Data Independence & Read-Only Access
              </h2>
              <p className="mt-1.5 text-sm leading-relaxed text-[#CBD5E1]">
                AHONIX operates exclusively via official read-only OAuth APIs (Shopify, Meta Ads, Google Ads). We do not modify your store products, alter pricing, place unconfirmed ad campaigns, or disrupt active checkouts.
              </p>
            </div>
          </div>
        </div>

        {/* Policy Sections */}
        <div className="space-y-12 text-[#CBD5E1]">
          {/* Section 1 */}
          <section id="services-description" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-[#00E599]">1.</span> Description of the Service
            </h2>
            <p className="text-sm leading-relaxed">
              AHONIX is a multi-channel commerce operating system designed to aggregate, analyze, and synthesize merchant financial and marketing telemetry. Capabilities include:
            </p>
            <ul className="space-y-1.5 text-xs text-[#94A3B8]">
              <li>• Multi-tenant workspace data ingestion and catalog synthesis</li>
              <li>• Unified True Profit waterfall modeling and Blended ROAS/CAC analytics</li>
              <li>• First-party UTM-based campaign attribution matching</li>
              <li>• Automated inventory reorder predictions and diagnostic anomaly detection</li>
            </ul>
          </section>

          {/* Section 2 */}
          <section id="eligibility-accounts" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-[#00E599]">2.</span> Eligibility & Account Responsibilities
            </h2>
            <p className="text-sm leading-relaxed">
              To use AHONIX, you must be at least 18 years of age (or the legal age of majority in your jurisdiction) and possess
              the legal authority to bind the merchant business entity on whose behalf you operate.
            </p>
            <p className="text-sm leading-relaxed">
              You are responsible for maintaining the confidentiality of your account credentials (email, password, session tokens)
              and for all activities that occur under your account. You agree to notify AHONIX immediately of any unauthorized use or
              security breach.
            </p>
          </section>

          {/* Section 3 */}
          <section id="merchant-authorization" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-[#00E599]">3.</span> Merchant Authorization & Third-Party Integrations
            </h2>
            <p className="text-sm leading-relaxed">
              By connecting your Shopify store, Meta Ads account, or Google Ads account to AHONIX:
            </p>
            <div className="space-y-3 rounded-xl border border-[#16221B] bg-[#070C0A] p-5 text-sm text-[#94A3B8]">
              <p>
                • <strong className="text-[#F8FAFC]">Authority:</strong> You represent and warrant that you own or have obtained all necessary licenses, permissions, and administrative rights to grant AHONIX access to the connected channels.
              </p>
              <p>
                • <strong className="text-[#F8FAFC]">Third-Party Terms:</strong> You agree to comply with the applicable terms of service of each connected third-party platform, including the Shopify API License and Terms of Use, Meta Platform Terms, and Google Ads Terms and Policies.
              </p>
              <p>
                • <strong className="text-[#F8FAFC]">Independence:</strong> AHONIX is an independent software application and is not endorsed, certified, sponsored, or affiliated with Shopify Inc., Meta Platforms, Inc., or Google LLC.
              </p>
              <p>
                • <strong className="text-[#F8FAFC]">API Availability:</strong> You acknowledge that AHONIX's ability to ingest data depends upon the continued availability and operational status of third-party APIs. We are not liable for delays, rate limits, schema deprecations, or outages caused by third-party platforms.
              </p>
            </div>
          </section>

          {/* Section 4 */}
          <section id="acceptable-use" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-[#00E599]">4.</span> Acceptable Use
            </h2>
            <p className="text-sm leading-relaxed">
              You agree not to use the service to:
            </p>
            <ul className="space-y-1.5 text-xs text-[#94A3B8]">
              <li>• Violate any applicable local, national, or international commerce, privacy, or consumer protection law.</li>
              <li>• Reverse-engineer, decompile, disassemble, or derive the source code of AHONIX or its algorithms.</li>
              <li>• Interfere with, disrupt, or attack our server infrastructure, database, or rate-limiting safeguards.</li>
              <li>• Access another merchant's workspace data without authorization.</li>
              <li>• Fabricate, inject, or manipulate advertising metrics or sales records for deceptive purposes.</li>
            </ul>
          </section>

          {/* Section 5 */}
          <section id="financial-disclaimer" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-[#00E599]">5.</span> Financial Analytics & AI Recommendation Disclaimers
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-[#16221B] bg-[#070C0A] p-5">
                <div className="flex items-center gap-2 text-sm font-bold text-[#F8FAFC]">
                  <TrendingUp size={16} className="text-[#00E599]" /> True Profit & ROAS Analytics
                </div>
                <p className="mt-2 text-xs text-[#94A3B8] leading-relaxed">
                  Financial outputs are calculated mathematically from ingested records and merchant-entered costs. They are decision-support indicators. Actual business profitability may be influenced by unrecorded overheads, payment processing fees, shipping variances, taxes, and operational expenses not connected to the platform.
                </p>
              </div>

              <div className="rounded-xl border border-[#16221B] bg-[#070C0A] p-5">
                <div className="flex items-center gap-2 text-sm font-bold text-[#F8FAFC]">
                  <Layers size={16} className="text-[#00E599]" /> Decision Support & Scenario Simulations
                </div>
                <p className="mt-2 text-xs text-[#94A3B8] leading-relaxed">
                  Insights generated by Ask AHONIX, Action Center recommendations, and scenario simulations are probabilistic projections based on historical patterns. They do not guarantee specific sales lift, profit increases, or inventory performance.
                </p>
              </div>
            </div>
          </section>

          {/* Section 6 */}
          <section id="data-ownership" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-[#00E599]">6.</span> Data Ownership & Intellectual Property
            </h2>
            <p className="text-sm leading-relaxed">
              <strong className="text-[#F8FAFC]">Your Data:</strong> As between you and AHONIX, you retain all ownership, title, and intellectual property rights in your raw store data, products, sales transactions, and advertising records. You grant AHONIX a limited, revocable license solely to process and analyze this data to provide the service to you.
            </p>
            <p className="text-sm leading-relaxed">
              <strong className="text-[#F8FAFC]">AHONIX Platform:</strong> AHONIX retains all rights, title, and interest in and to the platform, user interface designs, mathematical calculation models, software code, logos, trademarks, and documentation.
            </p>
          </section>

          {/* Section 7 */}
          <section id="disconnection-termination" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-[#00E599]">7.</span> Disconnection, Cancellation & Termination
            </h2>
            <p className="text-sm leading-relaxed">
              You may disconnect any connected channel (Shopify, Meta Ads, Google Ads) at any time through the platform Settings interface. Disconnecting an integration immediately revokes stored credentials and purges the synced platform data for that workspace.
            </p>
            <p className="text-sm leading-relaxed">
              You may terminate your account at any time. AHONIX reserves the right to suspend or terminate accounts that violate these Terms or pose a security risk to the infrastructure.
            </p>
          </section>

          {/* Section 8 */}
          <section id="limitation-of-liability" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-[#00E599]">8.</span> Limitation of Liability
            </h2>
            <div className="rounded-xl border border-[#16221B] bg-[#070C0A] p-5 text-xs text-[#94A3B8] leading-relaxed space-y-2">
              <p>
                TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, AHONIX AND ITS OFFICERS, DIRECTORS, EMPLOYEES, AND AGENTS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING WITHOUT LIMITATION, LOSS OF PROFITS, DATA, BUSINESS OPPORTUNITIES, OR GOODWILL, ARISING OUT OF OR IN CONNECTION WITH YOUR ACCESS TO OR USE OF (OR INABILITY TO USE) THE SERVICE.
              </p>
              <p>
                IN NO EVENT SHALL OUR TOTAL AGGREGATE LIABILITY ARISING OUT OF OR RELATING TO THESE TERMS OR THE SERVICE EXCEED THE AMOUNT PAID BY YOU TO AHONIX IN THE TWELVE (12) MONTHS PRECEDING THE EVENT GIVING RISE TO LIABILITY.
              </p>
            </div>
          </section>

          {/* Section 9 */}
          <section id="changes-governing" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-[#00E599]">9.</span> Changes to Terms & Contact Information
            </h2>
            <p className="text-sm leading-relaxed">
              We may modify these Terms from time to time. If a revision is material, we will provide at least 15 days notice before the new terms take effect. By continuing to use the service after revisions become effective, you agree to be bound by the updated Terms.
            </p>
            <div className="mt-4 flex flex-col gap-3 rounded-xl border border-[#16221B] bg-[#070C0A] p-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-bold text-[#F8FAFC]">Legal & Regulatory Inquiries</p>
                <p className="text-xs text-[#94A3B8]">Reach out to our legal and operational team.</p>
              </div>
              <a
                href="mailto:legal@ahonix.com"
                className="inline-flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2 text-xs font-semibold text-[#00E599] hover:bg-emerald-500/20"
              >
                <Mail size={14} /> legal@ahonix.com
              </a>
            </div>
          </section>
        </div>

        {/* Bottom Footer Navigation */}
        <div className="mt-16 border-t border-[#16221B] pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#64748B]">
          <p>© 2026 AHONIX · The AI Commerce OS. All rights reserved.</p>
          <div className="flex items-center gap-4">
            <Link to="/privacy" className="hover:text-[#94A3B8] transition-colors">
              Privacy Policy
            </Link>
            <Link to="/login" className="hover:text-[#94A3B8] transition-colors">
              Sign In
            </Link>
            <Link to="/register" className="hover:text-[#94A3B8] transition-colors">
              Create Account
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

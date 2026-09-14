import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import {
  ShieldCheck,
  ArrowLeft,
  Lock,
  Database,
  EyeOff,
  RefreshCw,
  Trash2,
  Mail,
  CheckCircle2,
} from "lucide-react";
import { Logo } from "@/components/Logo";

export default function PrivacyPolicy() {
  useEffect(() => {
    document.title = "Privacy Policy — AHONIX | The AI Commerce OS";
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="min-h-screen bg-[#08090E] text-[#F8FAFC]">
      {/* Top Navigation */}
      <header className="sticky top-0 z-30 border-b border-[#1E2235] bg-[#08090E]/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
          <Link to="/" className="flex items-center gap-3 transition-opacity hover:opacity-90">
            <Logo size={24} />
          </Link>
          <div className="flex items-center gap-4">
            <Link
              to="/terms"
              className="text-xs font-medium text-[#94A3B8] transition-colors hover:text-[#F8FAFC]"
            >
              Terms of Service
            </Link>
            <Link
              to="/login"
              className="flex items-center gap-1.5 rounded-lg border border-[#2D334B] bg-[#0F111A] px-3.5 py-1.5 text-xs font-semibold text-[#F8FAFC] transition-colors hover:bg-[#161926]"
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
          className="mb-8 inline-flex items-center gap-2 text-xs font-medium text-[#64748B] transition-colors hover:text-emerald-400"
        >
          <ArrowLeft size={14} /> Back to AHONIX Home
        </Link>

        {/* Title Header */}
        <div className="mb-12 border-b border-[#1E2235] pb-8">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3.5 py-1 text-xs font-medium text-emerald-400">
            <ShieldCheck size={14} /> Official Legal Documentation
          </div>
          <h1 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl text-[#F8FAFC]">
            Privacy Policy
          </h1>
          <p className="mt-3 text-sm text-[#94A3B8]">
            Effective Date: <span className="font-medium text-[#F8FAFC]">September 14, 2026</span> · Version 2.1
          </p>
          <p className="mt-4 text-base leading-relaxed text-[#CBD5E1]">
            This Privacy Policy explains how AHONIX ("AHONIX", "we", "our", or "us") collects, uses, protects,
            and discloses information when merchants and business operators use the AHONIX AI Commerce Operating
            System, software platform, and integrated application services.
          </p>
        </div>

        {/* Core Notice Banner: No Sale of Merchant Data */}
        <div className="mb-10 rounded-2xl border border-emerald-500/30 bg-emerald-950/20 p-5 sm:p-6">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-emerald-500/20 p-2 text-emerald-400">
              <EyeOff size={22} />
            </div>
            <div>
              <h2 className="text-base font-bold text-emerald-300">
                Core Guarantee: We Never Sell Your Data
              </h2>
              <p className="mt-1.5 text-sm leading-relaxed text-[#CBD5E1]">
                AHONIX is a software analytics tool, not a data broker. We do <strong className="text-emerald-200">not</strong> sell,
                rent, monetize, trade, or share your proprietary commerce, order, or advertising data with any third-party advertisers,
                data brokers, or competing brands under any circumstances.
              </p>
            </div>
          </div>
        </div>

        {/* Policy Sections */}
        <div className="space-y-12 text-[#CBD5E1]">
          {/* Section 1 */}
          <section id="who-we-are" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-emerald-400">1.</span> Who We Are & Scope
            </h2>
            <p className="text-sm leading-relaxed">
              AHONIX provides an operating system for modern e-commerce brands. Our platform connects directly with merchant
              sales channels and advertising networks to compute unified financial truth, including true net profit, real cost of
              goods sold (COGS), return on ad spend (ROAS), customer acquisition cost (CAC), inventory health, and marketing
              attribution.
            </p>
            <p className="text-sm leading-relaxed">
              This policy applies to all data processed through the AHONIX web platform, APIs, application integrations, and
              account management interfaces.
            </p>
          </section>

          {/* Section 2 */}
          <section id="data-collected" className="space-y-4">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-emerald-400">2.</span> Information We Collect
            </h2>
            <p className="text-sm leading-relaxed">
              We collect only the minimum business data necessary to provide analytical calculations and decision support. We do not
              collect personal consumer profiles or unnecessary personally identifiable information (PII).
            </p>

            <div className="grid gap-4 sm:grid-cols-2">
              {/* Shopify Store Data */}
              <div className="rounded-xl border border-[#1E2235] bg-[#0F111A] p-5">
                <div className="flex items-center gap-2 text-sm font-bold text-[#F8FAFC]">
                  <Database size={16} className="text-emerald-400" /> Shopify Store Data
                </div>
                <ul className="mt-3 space-y-1.5 text-xs text-[#94A3B8]">
                  <li>• Store domain, name, and default currency</li>
                  <li>• Product catalogs, variant IDs, prices, SKUs, and stock quantities</li>
                  <li>• Order identifiers, timestamps, line items, order totals, and fulfillment status</li>
                  <li>• Discount codes, discount amounts, and refund transactions</li>
                  <li>• Shipping geography (city and country only; no street addresses)</li>
                  <li>• First-party UTM parameters from customer journey summaries</li>
                  <li className="pt-1 text-emerald-400/90 font-medium">
                    ✓ We do NOT receive or store credit card numbers or payment credentials.
                  </li>
                </ul>
              </div>

              {/* Meta Ads Data */}
              <div className="rounded-xl border border-[#1E2235] bg-[#0F111A] p-5">
                <div className="flex items-center gap-2 text-sm font-bold text-[#F8FAFC]">
                  <Database size={16} className="text-emerald-400" /> Meta Ads Data
                </div>
                <ul className="mt-3 space-y-1.5 text-xs text-[#94A3B8]">
                  <li>• Ad account identifiers and account names</li>
                  <li>• Account currency (used for currency match validation)</li>
                  <li>• Campaign IDs, campaign names, status, and objectives</li>
                  <li>• Daily aggregated spend, impressions, and clicks</li>
                  <li>• Platform-reported conversion counts and conversion values</li>
                  <li className="pt-1 text-emerald-400/90 font-medium">
                    ✓ Imported as reference metrics only; never added to revenue.
                  </li>
                </ul>
              </div>

              {/* Google Ads Data */}
              <div className="rounded-xl border border-[#1E2235] bg-[#0F111A] p-5">
                <div className="flex items-center gap-2 text-sm font-bold text-[#F8FAFC]">
                  <Database size={16} className="text-emerald-400" /> Google Ads Data
                </div>
                <ul className="mt-3 space-y-1.5 text-xs text-[#94A3B8]">
                  <li>• Customer IDs (normalized without hyphens) and account names</li>
                  <li>• Manager account / login-customer-id relationships</li>
                  <li>• Account currency (used for currency match validation)</li>
                  <li>• Campaign IDs, campaign names, and campaign status</li>
                  <li>• Daily aggregated cost (converted from cost_micros), impressions, and clicks</li>
                  <li>• Platform-reported conversions and conversion values</li>
                </ul>
              </div>

              {/* Account & Authentication Data */}
              <div className="rounded-xl border border-[#1E2235] bg-[#0F111A] p-5">
                <div className="flex items-center gap-2 text-sm font-bold text-[#F8FAFC]">
                  <Lock size={16} className="text-emerald-400" /> Account & Security Data
                </div>
                <ul className="mt-3 space-y-1.5 text-xs text-[#94A3B8]">
                  <li>• Merchant contact email address and display name</li>
                  <li>• Cryptographic password hashes (salted using bcrypt; plain text is never stored)</li>
                  <li>• Encrypted OAuth tokens (AES-128 via Fernet)</li>
                  <li>• Ephemeral OAuth state nonces (15-minute expiration)</li>
                  <li>• Authentication security logs (IP address and timestamp for brute-force rate limiting)</li>
                </ul>
              </div>
            </div>
          </section>

          {/* Section 3 */}
          <section id="how-data-is-used" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-emerald-400">3.</span> How We Use Your Data
            </h2>
            <p className="text-sm leading-relaxed">
              We process data strictly to provide and maintain the analytical capabilities of the platform:
            </p>
            <ul className="space-y-2 text-sm">
              <li className="flex items-start gap-2">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-400" />
                <span>
                  <strong className="text-[#F8FAFC]">True Profit Computation:</strong> Calculating real net operating profit by deducting
                  merchant COGS, discounts, refunds, and eligible advertising spend from verified Shopify gross revenue.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-400" />
                <span>
                  <strong className="text-[#F8FAFC]">Marketing Blending (ROAS & CAC):</strong> Merging eligible ad spend across Meta Ads
                  and Google Ads against total Shopify order volume to compute Blended ROAS and Blended CAC without double-counting.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-400" />
                <span>
                  <strong className="text-[#F8FAFC]">First-Party UTM Attribution:</strong> Matching customer journey UTM parameters
                  directly to ad campaign records to identify which specific campaigns generated Shopify sales.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-400" />
                <span>
                  <strong className="text-[#F8FAFC]">Product Margin & Inventory Insights:</strong> Analyzing unit costs and stock-out
                  trajectories to alert merchants to stock risks and margin erosion.
                </span>
              </li>
            </ul>
          </section>

          {/* Section 4 */}
          <section id="security" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-emerald-400">4.</span> Security Measures & Encryption
            </h2>
            <p className="text-sm leading-relaxed">
              We apply defense-in-depth technical measures to safeguard your information:
            </p>
            <div className="space-y-2.5 rounded-xl border border-[#1E2235] bg-[#0F111A] p-5 text-sm text-[#94A3B8]">
              <p>
                • <strong className="text-[#F8FAFC]">Encryption at Rest:</strong> All third-party OAuth tokens (Shopify offline access tokens, Meta access tokens, and Google Ads refresh tokens) are encrypted before writing to the database using AES-128 via Fernet encryption keys derived from environment secrets.
              </p>
              <p>
                • <strong className="text-[#F8FAFC]">Encryption in Transit:</strong> All communications between your browser, our servers, and third-party APIs use TLS 1.3 encryption (HTTPS).
              </p>
              <p>
                • <strong className="text-[#F8FAFC]">Workspace Isolation:</strong> All database queries, caches, and analytics pipelines enforce multi-tenant isolation scoped strictly by authenticated <code className="rounded bg-[#1E2235] px-1 text-xs text-emerald-400">workspace_id</code>.
              </p>
              <p>
                • <strong className="text-[#F8FAFC]">Credential Sanitization:</strong> API responses strictly sanitize tokens; access tokens, refresh tokens, app secrets, and developer tokens are never serialized or returned to the client browser.
              </p>
              <p>
                • <strong className="text-[#F8FAFC]">Secure Cookies & Headers:</strong> Authentication cookies use <code className="rounded bg-[#1E2235] px-1 text-xs text-emerald-400">HttpOnly</code>, <code className="rounded bg-[#1E2235] px-1 text-xs text-emerald-400">Secure</code>, and strict <code className="rounded bg-[#1E2235] px-1 text-xs text-emerald-400">SameSite</code> settings, alongside anti-clickjacking and content security headers.
              </p>
            </div>
          </section>

          {/* Section 5 */}
          <section id="data-retention-deletion" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-emerald-400">5.</span> Data Retention & Disconnection
            </h2>
            <p className="text-sm leading-relaxed">
              You maintain full control over your connected data at all times:
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-[#1E2235] bg-[#0F111A] p-4 text-xs">
                <div className="flex items-center gap-2 font-bold text-[#F8FAFC]">
                  <RefreshCw size={14} className="text-emerald-400" /> Disconnecting an Integration
                </div>
                <p className="mt-2 text-[#94A3B8] leading-relaxed">
                  You can disconnect Shopify, Meta Ads, or Google Ads at any time in Settings. Disconnecting permanently deletes stored OAuth credentials and purges synced records for that platform.
                </p>
              </div>
              <div className="rounded-xl border border-[#1E2235] bg-[#0F111A] p-4 text-xs">
                <div className="flex items-center gap-2 font-bold text-[#F8FAFC]">
                  <Trash2 size={14} className="text-rose-400" /> Account & Data Deletion
                </div>
                <p className="mt-2 text-[#94A3B8] leading-relaxed">
                  Upon account termination or verified deletion request, all associated workspace data, credentials, and analytical records are purged from active production databases.
                </p>
              </div>
            </div>
          </section>

          {/* Section 6 */}
          <section id="third-party-services" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-emerald-400">6.</span> Third-Party Service Providers
            </h2>
            <p className="text-sm leading-relaxed">
              AHONIX interacts with authorized platform APIs to fetch your authorized business metrics. We do not provide these platforms with your proprietary data from other channels:
            </p>
            <ul className="space-y-1.5 text-xs text-[#94A3B8]">
              <li>
                • <strong className="text-[#F8FAFC]">Shopify:</strong> Admin REST and GraphQL APIs for product catalog, inventory, order details, and webhooks.
              </li>
              <li>
                • <strong className="text-[#F8FAFC]">Meta Platforms:</strong> Meta Graph and Marketing APIs for ad account discovery and campaign insights.
              </li>
              <li>
                • <strong className="text-[#F8FAFC]">Google LLC:</strong> Google Ads API for customer account discovery, campaign metrics, and conversion values.
              </li>
              <li>
                • <strong className="text-[#F8FAFC]">Database Infrastructure:</strong> MongoDB Atlas cloud database with encrypted storage at rest.
              </li>
            </ul>
          </section>

          {/* Section 7 */}
          <section id="cookies" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-emerald-400">7.</span> Cookies & Session Management
            </h2>
            <p className="text-sm leading-relaxed">
              We use strictly necessary first-party cookies to manage authentication sessions:
            </p>
            <ul className="space-y-1 text-xs text-[#94A3B8]">
              <li>• <code className="text-emerald-400">access_token</code>: Authenticates API requests (1-hour lifespan, HttpOnly).</li>
              <li>• <code className="text-emerald-400">refresh_token</code>: Renews expired access tokens (7-day lifespan, HttpOnly).</li>
              <li>• We do <strong className="text-[#F8FAFC]">not</strong> use third-party advertising tracking cookies or behavioral tracking pixels.</li>
            </ul>
          </section>

          {/* Section 8 */}
          <section id="contact-updates" className="space-y-3">
            <h2 className="font-display text-xl font-bold text-[#F8FAFC] flex items-center gap-2">
              <span className="text-emerald-400">8.</span> Contact Information & Policy Updates
            </h2>
            <p className="text-sm leading-relaxed">
              We may update this Privacy Policy periodically to reflect new features or platform requirements. If material changes are made, we will notify registered merchants via email or in-app notice prior to the changes becoming effective.
            </p>
            <div className="mt-4 flex flex-col gap-3 rounded-xl border border-[#1E2235] bg-[#0F111A] p-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-bold text-[#F8FAFC]">Privacy & Data Governance Inquiries</p>
                <p className="text-xs text-[#94A3B8]">Contact our compliance and security team directly.</p>
              </div>
              <a
                href="mailto:privacy@ahonix.com"
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-500/10 px-4 py-2 text-xs font-semibold text-emerald-400 hover:bg-emerald-500/20"
              >
                <Mail size={14} /> privacy@ahonix.com
              </a>
            </div>
          </section>
        </div>

        {/* Bottom Footer Navigation */}
        <div className="mt-16 border-t border-[#1E2235] pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#64748B]">
          <p>© 2026 AHONIX · The AI Commerce OS. All rights reserved.</p>
          <div className="flex items-center gap-4">
            <Link to="/terms" className="hover:text-[#94A3B8] transition-colors">
              Terms of Service
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

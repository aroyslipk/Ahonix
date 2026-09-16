import React from "react";
import {
  Area, AreaChart, Bar, BarChart, ResponsiveContainer, Tooltip,
  XAxis, YAxis, Cell, PieChart, Pie, LineChart, Line,
} from "recharts";
import { fmtCurrency, fmtNumber } from "@/lib/api";

const EMERALD = "#00E599";
const CYAN = "#38BDF8";

const AXIS = { stroke: "#24332A", fill: "#64748B", fontSize: 11, tickLine: false, axisLine: false };

function ChartTip({ active, payload, label, currency, prefix }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[#16221B] bg-[#070C0A] px-3.5 py-2.5 shadow-2xl backdrop-blur-md">
      <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-[#64748B]">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="font-metric text-sm font-bold text-[#F8FAFC]">
          {prefix === "currency" ? fmtCurrency(p.value, currency) : fmtNumber(p.value)}
        </p>
      ))}
    </div>
  );
}

export function Sparkline({ data = [], color = EMERALD, height = 40 }) {
  const chartData = data.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={chartData} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
        <defs>
          <linearGradient id={`spark-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="v" stroke={color} strokeWidth={2} fill={`url(#spark-${color})`} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function TrendArea({ data, dataKey = "revenue", xKey = "week", currency = "USD", height = 280, color = EMERALD }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <defs>
          <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.25} />
            <stop offset="100%" stopColor={color} stopOpacity={0.01} />
          </linearGradient>
        </defs>
        <XAxis dataKey={xKey} {...AXIS} />
        <YAxis {...AXIS} width={48} tickFormatter={(v) => fmtNumber(v, true)} />
        <Tooltip content={<ChartTip currency={currency} prefix="currency" />} cursor={{ stroke: "rgba(0, 229, 153, 0.2)" }} />
        <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2.5} fill="url(#areaFill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function DualLine({ data, xKey = "week", height = 280, currency = "USD" }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <XAxis dataKey={xKey} {...AXIS} />
        <YAxis {...AXIS} width={48} tickFormatter={(v) => fmtNumber(v, true)} />
        <Tooltip content={<ChartTip currency={currency} prefix="currency" />} cursor={{ stroke: "rgba(255,255,255,0.1)" }} />
        <Line type="monotone" dataKey="revenue" stroke={CYAN} strokeWidth={2.5} dot={false} />
        <Line type="monotone" dataKey="profit" stroke={EMERALD} strokeWidth={2.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function BarSeries({ data, dataKey, xKey, currency = "USD", height = 280, color = EMERALD, prefix = "currency" }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <XAxis dataKey={xKey} {...AXIS} interval={0} />
        <YAxis {...AXIS} width={48} tickFormatter={(v) => fmtNumber(v, true)} />
        <Tooltip content={<ChartTip currency={currency} prefix={prefix} />} cursor={{ fill: "rgba(0, 229, 153, 0.05)" }} />
        <Bar dataKey={dataKey} radius={[6, 6, 0, 0]} maxBarSize={46}>
          {data.map((_, i) => (
            <Cell key={i} fill={color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

const DONUT_COLORS = [EMERALD, "#008060", CYAN, "#8B5CF6", "#F59E0B", "#F43F5E"];

export function Donut({ data, dataKey = "share", nameKey = "name", height = 220 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey={dataKey} nameKey={nameKey} innerRadius={54} outerRadius={80} paddingAngle={3} stroke="none">
          {data.map((_, i) => (
            <Cell key={i} fill={DONUT_COLORS[i % DONUT_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: "#070C0A", border: "1px solid #16221B", borderRadius: 8, fontSize: 12 }}
          itemStyle={{ color: "#F8FAFC" }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

export { DONUT_COLORS };


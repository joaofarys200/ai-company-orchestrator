import React from 'react';
import type { LucideIcon } from 'lucide-react';

export type StatusTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger';

const TONE_CLASSES: Record<StatusTone, string> = {
  neutral: 'border-slate-700/70 bg-slate-900/70 text-slate-300',
  accent: 'border-sky-500/30 bg-sky-500/10 text-sky-300',
  success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  warning: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
  danger: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
};

export const StatusPill: React.FC<{
  tone?: StatusTone;
  children: React.ReactNode;
  className?: string;
}> = ({ tone = 'neutral', children, className = '' }) => (
  <span
    className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium ${TONE_CLASSES[tone]} ${className}`}
  >
    {children}
  </span>
);

export const InlineBanner: React.FC<{
  tone?: StatusTone;
  icon?: LucideIcon;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}> = ({ tone = 'accent', icon: Icon, title, description, actions, className = '' }) => (
  <div
    className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3.5 py-2.5 text-xs ${TONE_CLASSES[tone]} ${className}`}
  >
    <div className="flex min-w-0 items-start gap-2.5">
      {Icon && <Icon className="mt-0.5 h-4 w-4 shrink-0" />}
      <div className="min-w-0">
        <div className="font-semibold">{title}</div>
        {description && <p className="mt-0.5 opacity-85 leading-relaxed">{description}</p>}
      </div>
    </div>
    {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
  </div>
);

export const PanelEmptyState: React.FC<{
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}> = ({ icon: Icon, title, description, action }) => (
  <div className="flex h-full flex-col items-center justify-center px-6 py-12 text-center">
    <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-slate-800 bg-[#0f1722] text-slate-400">
      <Icon className="h-5 w-5" />
    </div>
    <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
    {description && <p className="mt-1.5 max-w-md text-xs leading-relaxed text-slate-400">{description}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);


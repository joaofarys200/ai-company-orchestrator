import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Lock,
  Clock,
  Terminal,
  RefreshCw,
  X,
  CheckCircle,
  HelpCircle,
} from 'lucide-react';
import { usePermissionStore } from './PermissionStore';
import { useWebSocket } from '../../context/WebSocketContext';
import type { PermissionRiskLevel } from '../../protocol/websocket';

export const PermissionApprovalModal: React.FC = () => {
  const { currentRequest, modalOpen, setModalOpen, markApproved, markDenied } = usePermissionStore();
  const { approvePermissionRequest, denyPermissionRequest } = useWebSocket();
  const [submitting, setSubmitting] = useState(false);

  if (!modalOpen || !currentRequest) {
    return null;
  }

  const isBlockedByPolicy =
    currentRequest.status === 'BLOCKED_BY_POLICY' ||
    currentRequest.risk_level === 'CRITICAL_MUTATION';

  const isAdminRequired = currentRequest.status === 'ADMIN_PRIVILEGE_REQUIRED';
  const isInstallationRequired = currentRequest.status === 'INSTALLATION_REQUIRED';

  const handleApprove = async () => {
    if (submitting || isBlockedByPolicy) return;
    setSubmitting(true);
    const reqId = currentRequest.request_id;
    try {
      approvePermissionRequest(
        reqId,
        currentRequest.project_id || undefined,
        currentRequest.mission_id || undefined
      );
    } finally {
      setTimeout(() => {
        setSubmitting(false);
        markApproved(reqId);
      }, 500);
    }
  };

  const handleDeny = async () => {
    if (submitting) return;
    setSubmitting(true);
    const reqId = currentRequest.request_id;
    try {
      denyPermissionRequest(
        reqId,
        'Recusado pelo operador humano',
        currentRequest.project_id || undefined,
        currentRequest.mission_id || undefined
      );
    } finally {
      setTimeout(() => {
        setSubmitting(false);
        markDenied(reqId);
      }, 500);
    }
  };

  const getRiskBadge = (risk: PermissionRiskLevel) => {
    switch (risk) {
      case 'READ_ONLY':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <ShieldCheck className="w-3.5 h-3.5" />
            READ ONLY
          </span>
        );
      case 'LOW_RISK_MUTATION':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <HelpCircle className="w-3.5 h-3.5" />
            LOW RISK
          </span>
        );
      case 'HIGH_RISK_MUTATION':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertTriangle className="w-3.5 h-3.5" />
            HIGH RISK
          </span>
        );
      case 'CRITICAL_MUTATION':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <Lock className="w-3.5 h-3.5" />
            CRITICAL
          </span>
        );
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
        {/* Backdrop escuro com blur */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 bg-black/80 backdrop-blur-md"
          onClick={() => {
            if (isBlockedByPolicy) setModalOpen(false);
          }}
        />

        {/* Modal centralizado */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 12 }}
          transition={{ type: 'spring', damping: 26, stiffness: 240 }}
          className="relative w-full max-w-xl bg-[#0d0f17] border border-white/10 rounded-xl shadow-[0_25px_80px_rgba(0,0,0,0.85)] text-stone-200 overflow-hidden z-10 font-sans"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4.5 border-b border-white/10 bg-white/[0.02]">
            <div className="flex items-center gap-3">
              <div
                className={`w-9 h-9 rounded-lg flex items-center justify-center border ${
                  isBlockedByPolicy
                    ? 'bg-rose-500/15 border-rose-500/30 text-rose-300'
                    : 'bg-amber-500/15 border-amber-500/30 text-amber-300'
                }`}
              >
                {isBlockedByPolicy ? (
                  <ShieldAlert className="w-5 h-5" />
                ) : (
                  <AlertTriangle className="w-5 h-5" />
                )}
              </div>
              <div>
                <h3 className="text-base font-semibold text-white tracking-tight">
                  JARVIS precisa da tua autorização
                </h3>
                <div className="flex items-center gap-2 text-xs text-stone-400 font-mono mt-0.5">
                  <span>ID: {currentRequest.request_id}</span>
                  {currentRequest.project_id && (
                    <>
                      <span>•</span>
                      <span>Projeto: {currentRequest.project_id}</span>
                    </>
                  )}
                  {currentRequest.mission_id && (
                    <>
                      <span>•</span>
                      <span>Missão: {currentRequest.mission_id}</span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {isBlockedByPolicy && (
              <button
                onClick={() => setModalOpen(false)}
                className="text-stone-400 hover:text-white p-1 rounded-md hover:bg-white/5 transition-colors"
                title="Fechar"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Body */}
          <div className="p-6 space-y-4.5 text-xs sm:text-sm">
            {/* Aviso de Bloqueio por Política */}
            {isBlockedByPolicy && (
              <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-200 text-xs flex items-start gap-3">
                <Lock className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-semibold text-rose-300">
                    Esta operação está bloqueada pela política de segurança atual.
                  </div>
                  <p className="text-rose-200/90 leading-relaxed font-sans">
                    {currentRequest.policy_reason ||
                      'Mutações críticas ou comandos com impacto estrutural no anfitrião não são permitidos pelo JARVIS Sentinel.'}
                  </p>
                </div>
              </div>
            )}

            {/* Aviso de Requisito de Administrador do Windows */}
            {isAdminRequired && (
              <div className="p-3.5 rounded-lg bg-amber-500/15 border border-amber-500/35 text-amber-200 text-xs flex items-start gap-3">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-amber-300">
                    É necessária autorização administrativa do Windows.
                  </div>
                  <p className="text-amber-200/80 leading-relaxed font-sans">
                    A ferramenta requer privilégios elevados no sistema anfitrião. A aprovação
                    humana foi registada, mas o processo deve ser iniciado como Administrador.
                  </p>
                </div>
              </div>
            )}

            {/* Aviso de Instalação Necessária */}
            {isInstallationRequired && (
              <div className="p-3.5 rounded-lg bg-cyan-500/15 border border-cyan-500/35 text-cyan-200 text-xs flex items-start gap-3">
                <Terminal className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-cyan-300">
                    Instalação de Dependência Necessária
                  </div>
                  <p className="text-cyan-200/80 leading-relaxed font-sans">
                    A ferramenta não foi encontrada localmente. É necessário proceder à instalação
                    controlada e auditada antes da execução.
                  </p>
                </div>
              </div>
            )}

            {/* Tabela de Dados Estruturados */}
            <div className="bg-black/40 rounded-lg border border-white/8 p-4 space-y-3.5 text-xs font-mono">
              <div className="flex items-center justify-between">
                <span className="text-stone-400">Ferramenta:</span>
                <span className="text-white font-semibold text-sm">
                  {currentRequest.tool_name}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-stone-400">Risco:</span>
                <div>{getRiskBadge(currentRequest.risk_level)}</div>
              </div>

              <div>
                <span className="text-stone-400 block mb-1">Motivo:</span>
                <p className="text-stone-200 font-sans text-xs bg-white/[0.03] p-2.5 rounded border border-white/5 leading-relaxed">
                  {currentRequest.reason}
                </p>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-stone-400">Privilégios Necessários:</span>
                <span className="text-stone-300 font-semibold">
                  {currentRequest.required_privileges}
                </span>
              </div>

              <div>
                <span className="text-stone-400 block mb-1">Impacto / Recursos Afetados:</span>
                <div className="text-stone-300 font-sans text-xs bg-white/[0.03] p-2 rounded border border-white/5">
                  {currentRequest.affected_resources.length > 0
                    ? currentRequest.affected_resources.join(', ')
                    : 'Sistema local de desenvolvimento'}
                  {currentRequest.installation_required && (
                    <span className="text-amber-400 block mt-1">
                      • Requer instalação de binário / dependência externa.
                    </span>
                  )}
                  {currentRequest.rollback_available && (
                    <span className="text-emerald-400 block mt-0.5">
                      • Reversão automática suportada.
                    </span>
                  )}
                </div>
              </div>

              {currentRequest.alternative_available && (
                <div className="pt-2 border-t border-white/8">
                  <span className="text-stone-400 block mb-1">Alternativa Disponível (Fallback):</span>
                  <div className="p-2.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 font-sans text-xs flex items-center gap-2">
                    <CheckCircle className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
                    <span>{currentRequest.fallback_description}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Scope / Expiration Footer */}
            <div className="flex items-center justify-between text-[11px] text-stone-400 px-1">
              <span className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-stone-400" />
                <span>Autorização com escopo específico e temporário</span>
              </span>
              <span>Expira em: 5 minutos</span>
            </div>
          </div>

          {/* Actions / Buttons */}
          <div className="px-6 py-4 border-t border-white/10 bg-white/[0.02] flex items-center justify-end gap-3">
            {isBlockedByPolicy ? (
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-white/10 hover:bg-white/15 text-white transition-all cursor-pointer"
              >
                Compreendido
              </button>
            ) : (
              <>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={handleDeny}
                  className="px-4 py-2 text-xs font-semibold rounded-lg border border-white/10 bg-white/[0.04] hover:bg-white/[0.08] text-stone-300 hover:text-white transition-all disabled:opacity-50 cursor-pointer"
                >
                  Recusar
                </button>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={handleApprove}
                  className="px-5 py-2 text-xs font-semibold rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black shadow-[0_0_20px_rgba(6,182,212,0.35)] transition-all flex items-center gap-2 disabled:opacity-50 cursor-pointer"
                >
                  {submitting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>Autorizar</span>
                </button>
              </>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

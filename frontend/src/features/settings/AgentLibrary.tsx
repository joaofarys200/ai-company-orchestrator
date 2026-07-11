import React from 'react';
import { useWebSocket } from '../../context/WebSocketContext';
import { motion } from 'framer-motion';
import { BookOpen, Database, Sparkles, ShieldAlert, PenTool, X } from 'lucide-react';

interface AgentLibraryProps {
  isOpen: boolean;
  onClose: () => void;
}

const PRESET_AGENTS = [
  {
    name: 'Marta',
    title: 'Marta // SQL Expert',
    specialty: 'Especialista SQL',
    description: 'Criação e otimização de bases de dados relacionais e consultas avançadas.',
    task: 'Cria uma base de dados SQLite bem otimizada com tabelas de usuários, compras e produtos, e gera 3 queries de analise complexas com INNER JOINs.',
    icon: <Database className="w-5 h-5 text-cyan-400" />,
  },
  {
    name: 'Gustavo',
    title: 'Gustavo // CSS Animator',
    specialty: 'CSS Animator',
    description: 'Design de micro-animações, gradientes premium e efeitos de transição sci-fi.',
    task: 'Cria uma folha de estilos CSS extra com animações futuristas avançadas (glitch, matrix text, keyframe rotations para o canvas do Jarvis) e injecta no styles.css.',
    icon: <Sparkles className="w-5 h-5 text-pink-400" />,
  },
  {
    name: 'Duarte',
    title: 'Duarte // Security Auditor',
    specialty: 'Security Auditor',
    description: 'Análise de vulnerabilidades, auditoria de código OWASP e correções de segurança.',
    task: 'Realiza uma auditoria de segurança estática no código index.html, styles.css e app.js da sandbox. Procura vulnerabilidades XSS ou inputs não validados e sugere correções directas.',
    icon: <ShieldAlert className="w-5 h-5 text-red-400" />,
  },
  {
    name: 'Inês',
    title: 'Inês // SEO & Copywriter',
    specialty: 'SEO & Copywriter',
    description: 'Geração de conteúdo otimizado para motores de busca e copy persuasivo em PT-PT.',
    task: 'Escreve um copy irresistível em português de Portugal para as secções da landing page da sandbox e otimiza as meta-tags para SEO técnico (keywords, meta description).',
    icon: <PenTool className="w-5 h-5 text-yellow-400" />,
  },
];

export const AgentLibrary: React.FC<AgentLibraryProps> = ({ isOpen, onClose }) => {
  const { sendDirective } = useWebSocket();

  const handleSpawn = (agent: typeof PRESET_AGENTS[0]) => {
    const directive = `/spawn ${agent.name} | ${agent.specialty} | ${agent.task}`;
    sendDirective(directive);
    onClose();
  };

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: isOpen ? 0 : '100%' }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className="fixed inset-y-0 right-0 w-full md:w-[420px] bg-[#05070e]/96 border-l border-white/8 shadow-[-18px_0_70px_rgba(0,0,0,0.55)] z-50 flex flex-col backdrop-blur-2xl"
    >
      {/* Drawer Header */}
      <div className="flex items-center justify-between p-4 bg-white/[0.025] border-b border-white/8">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-md border border-cyan-300/20 bg-cyan-300/10 flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-cyan-200" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Biblioteca de subagentes</h3>
            <p className="text-xs text-gray-500">Perfis especializados</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-white h-9 w-9 rounded-md border border-white/8 bg-white/[0.035] hover:bg-white/[0.08] transition-colors cursor-pointer flex items-center justify-center"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Drawer Content */}
      <div className="flex-grow p-4 overflow-y-auto">
        <div className="space-y-3">
          {PRESET_AGENTS.map((agent) => (
            <div
              key={agent.name}
              className="p-3.5 rounded-md bg-white/[0.035] border border-white/8 hover:border-cyan-300/25 transition-all duration-300 flex flex-col gap-3 group"
            >
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-md bg-white/[0.04] group-hover:bg-cyan-300/10 transition-colors">
                  {agent.icon}
                </div>
                <div className="flex flex-col">
                  <h4 className="text-sm font-semibold text-white">{agent.title}</h4>
                  <span className="text-xs text-cyan-100/70 mt-0.5">
                    {agent.specialty}
                  </span>
                </div>
              </div>

              <p className="text-sm text-gray-400 leading-relaxed">
                {agent.description}
              </p>

              <button
                onClick={() => handleSpawn(agent)}
                className="mt-1 w-full py-2 text-xs font-semibold text-black bg-cyan-300 hover:bg-cyan-200 rounded-md cursor-pointer transition-all active:scale-98"
              >
                Ativar agente
              </button>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
};

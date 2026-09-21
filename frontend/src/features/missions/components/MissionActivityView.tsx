import React, { useState, useMemo } from 'react';
import {
  ChevronDown,
  Filter,
} from 'lucide-react';
import type { MissionControlEventData } from '../../../protocol/websocket';

interface MissionActivityViewProps {
  events: MissionControlEventData[];
}

export const MissionActivityView: React.FC<MissionActivityViewProps> = ({ events }) => {
  const [selectedActor, setSelectedActor] = useState<string>('ALL');
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  const actors = useMemo(() => {
    const set = new Set<string>();
    events.forEach((e) => {
      const actorName = (e as any).actor || e.agent;
      if (actorName) set.add(actorName);
    });
    return Array.from(set);
  }, [events]);

  const filteredEvents = useMemo(() => {
    if (selectedActor === 'ALL') return events;
    return events.filter((e) => ((e as any).actor || e.agent) === selectedActor);
  }, [events, selectedActor]);

  return (
    <div className="space-y-4 max-w-5xl mx-auto">
      {/* HEADER & FILTER ROW */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Histórico de Atividade</h2>
          <p className="text-xs text-gray-400">
            Registo cronológico das ações autónomas e intervenções do operador
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto">
          <Filter className="h-3.5 w-3.5 text-gray-500 mr-1" />
          <button
            onClick={() => setSelectedActor('ALL')}
            className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
              selectedActor === 'ALL'
                ? 'bg-cyan-500/15 text-cyan-200 border border-cyan-400/30'
                : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
            }`}
          >
            Todos ({events.length})
          </button>
          {actors.map((actor) => (
            <button
              key={actor}
              onClick={() => setSelectedActor(actor)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                selectedActor === actor
                  ? 'bg-cyan-500/15 text-cyan-200 border border-cyan-400/30'
                  : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
              }`}
            >
              {actor}
            </button>
          ))}
        </div>
      </div>

      {/* LINEAR TIMELINE */}
      <div className="relative border-l border-white/10 pl-4 ml-3 space-y-3">
        {filteredEvents.length === 0 ? (
          <div className="py-8 text-xs text-gray-500">Nenhum evento registado para este filtro.</div>
        ) : (
          filteredEvents.map((ev, idx) => {
            const isExpanded = expandedEventId === (ev.event_id || String(idx));
            const formattedTime = new Date(ev.timestamp * 1000).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            });

            return (
              <div key={ev.event_id || idx} className="relative group">
                {/* Node dot on the vertical line */}
                <div className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-[#091217] bg-cyan-400 group-hover:scale-125 transition-transform" />

                <div className="rounded-md border border-white/5 bg-white/[0.015] p-2.5 text-xs transition-colors hover:border-white/10 hover:bg-white/[0.03]">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-mono text-[11px] text-gray-500 shrink-0">
                        {formattedTime}
                      </span>
                      <span className="rounded bg-white/5 px-1.5 py-0.2 text-[10px] font-semibold text-gray-300">
                        {(ev as any).actor || ev.agent || 'Sistema'}
                      </span>
                      <span className="truncate text-gray-200 font-medium">
                        {(ev as any).summary || ev.title || ev.type}
                      </span>
                    </div>

                    {ev.payload && Object.keys(ev.payload).length > 0 && (
                      <button
                        onClick={() =>
                          setExpandedEventId(isExpanded ? null : ev.event_id || String(idx))
                        }
                        className="text-gray-500 hover:text-gray-300 p-0.5 transition-colors"
                        title="Ver detalhes do evento"
                      >
                        <ChevronDown
                          className={`h-3 w-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        />
                      </button>
                    )}
                  </div>

                  {/* Expanded event payload */}
                  {isExpanded && ev.payload && (
                    <div className="mt-2 pt-2 border-t border-white/5">
                      <pre className="text-[11px] font-mono text-gray-400 overflow-x-auto p-2 rounded bg-black/40">
                        {JSON.stringify(ev.payload, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default MissionActivityView;

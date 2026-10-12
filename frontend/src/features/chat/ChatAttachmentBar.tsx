import React, { useState } from 'react';
import { FileText, Image as ImageIcon, Code2, X, ZoomIn, FileCheck } from 'lucide-react';
import type { ChatAttachment } from './types';

interface ChatAttachmentBarProps {
  attachments: ChatAttachment[];
  onRemove?: (id: string) => void;
  readOnly?: boolean;
}

export const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const ChatAttachmentBar: React.FC<ChatAttachmentBarProps> = ({
  attachments,
  onRemove,
  readOnly = false,
}) => {
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  if (!attachments || attachments.length === 0) return null;

  const totalBytes = attachments.reduce((sum, a) => sum + a.size, 0);
  const totalTokens = attachments.reduce((sum, a) => sum + (a.tokenEstimate || Math.ceil(a.size / 4)), 0);

  const getFileIcon = (att: ChatAttachment) => {
    if (att.type === 'image') return <ImageIcon className="w-3.5 h-3.5 text-cyan-300" />;
    if (att.name.match(/\.(ts|tsx|js|jsx|py|rs|go|json|html|css)$/i)) {
      return <Code2 className="w-3.5 h-3.5 text-amber-300" />;
    }
    return <FileText className="w-3.5 h-3.5 text-violet-300" />;
  };

  return (
    <>
      <div className="flex flex-col gap-1.5 p-2 rounded-lg bg-black/40 border border-white/8 backdrop-blur-md">
        {/* Attachment preview items list */}
        <div className="flex flex-wrap items-center gap-2">
          {attachments.map((att) => {
            const isImage = att.type === 'image' && att.dataUrl;
            return (
              <div
                key={att.id}
                className="group relative flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-white/[0.04] border border-white/10 hover:border-cyan-300/30 transition-all text-xs"
              >
                {isImage ? (
                  <div
                    onClick={() => setPreviewImage(att.dataUrl || null)}
                    className="relative w-8 h-8 rounded overflow-hidden bg-black/50 border border-white/10 cursor-pointer shrink-0 hover:opacity-90"
                    title="Clique para ampliar"
                  >
                    <img
                      src={att.dataUrl}
                      alt={att.name}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                      <ZoomIn className="w-3 h-3 text-white" />
                    </div>
                  </div>
                ) : (
                  <div className="w-7 h-7 rounded bg-white/[0.05] border border-white/10 flex items-center justify-center shrink-0">
                    {getFileIcon(att)}
                  </div>
                )}

                <div className="flex flex-col min-w-0 pr-1">
                  <span className="font-mono text-[11px] text-gray-200 truncate max-w-[150px] sm:max-w-[190px]">
                    {att.name}
                  </span>
                  <div className="flex items-center gap-1.5 text-[9px] text-gray-500 font-mono">
                    <span>{formatFileSize(att.size)}</span>
                    <span>•</span>
                    <span className="text-cyan-300/80">~{att.tokenEstimate || Math.ceil(att.size / 4)} tok</span>
                  </div>
                </div>

                {!readOnly && onRemove && (
                  <button
                    onClick={() => onRemove(att.id)}
                    className="p-1 text-gray-400 hover:text-rose-300 hover:bg-rose-950/30 rounded transition-all cursor-pointer"
                    title="Remover anexo"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* Budget and context indicator */}
        <div className="flex items-center justify-between px-1 text-[10px] text-gray-500 font-mono">
          <div className="flex items-center gap-1.5 text-cyan-200/80">
            <FileCheck className="w-3 h-3 text-cyan-400" />
            <span>
              {attachments.length} {attachments.length === 1 ? 'anexo pronto' : 'anexos prontos'} ({formatFileSize(totalBytes)})
            </span>
          </div>
          <span className="text-gray-400">
            Estimativa de contexto: <span className="text-cyan-300 font-semibold">~{totalTokens} tokens</span>
          </span>
        </div>
      </div>

      {/* Image Zoom Modal */}
      {previewImage && (
        <div
          onClick={() => setPreviewImage(null)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 cursor-pointer"
        >
          <div className="relative max-w-4xl max-h-[90vh] rounded-lg overflow-hidden border border-white/20 bg-black/90 p-2">
            <button
              onClick={() => setPreviewImage(null)}
              className="absolute top-3 right-3 p-1.5 rounded-full bg-black/60 border border-white/20 text-white hover:bg-white/20 transition-all cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
            <img
              src={previewImage}
              alt="Visualização ampliada"
              className="max-w-full max-h-[82vh] object-contain rounded"
            />
          </div>
        </div>
      )}
    </>
  );
};
